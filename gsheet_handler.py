
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import time

# 설정
JSON_FILE = 'service_account.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/17JU4KoC-Out5NqGy3qtN7LSunMUsH5xS2qJSk1fBDGQ/edit?gid=870712162#gid=870712162'
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
TARGET_TAB_NAME = 'Accumulated_Data' # 데이터 쌓을 탭 이름

def get_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"[GSheet] 인증 실패: {e}")
        return None

def update_sheet(data_list):
    """
    data_list: utils.py에서 반환된 딕셔너리 리스트 (Raw EPS 데이터 포함)
    """
    client = get_client()
    if not client: return

    try:
        doc = client.open_by_url(SHEET_URL)
        
        # 탭 확인 또는 생성
        try:
            sheet = doc.worksheet(TARGET_TAB_NAME)
        except:
            print(f"[GSheet] '{TARGET_TAB_NAME}' 탭이 없어 생성합니다.")
            sheet = doc.add_worksheet(title=TARGET_TAB_NAME, rows=1000, cols=10)
            # 헤더 추가
            sheet.append_row(['Ticker', 'WorkDate', 'CY_Current', 'CY_30Ago', 'NY_Current', 'NY_30Ago'])

        # 기존 데이터 읽기 (중복/변동 확인용)
        existing_data = sheet.get_all_records()
        existing_df = pd.DataFrame(existing_data)
        
        # DataFrame이 비어있을 경우 처리
        if existing_df.empty:
            last_entries = {}
        else:
            # 각 티커별 마지막 항목 저장 (Ticker -> {Date, CY_Current, ...})
            # 날짜순 정렬 후 처리
            if 'WorkDate' in existing_df.columns:
                existing_df['WorkDate'] = pd.to_datetime(existing_df['WorkDate'])
                existing_df = existing_df.sort_values(by='WorkDate')
            
            last_entries = {}
            for _, row in existing_df.iterrows():
                ticker = str(row.get('Ticker', '')).strip()
                if ticker:
                    last_entries[ticker] = row.to_dict()

        today_str = datetime.now().strftime("%Y-%m-%d")
        rows_to_append = []
        
        print(f"\n[GSheet] 데이터 적재 시작 (총 {len(data_list)}개 처리 예정)...")
        
        for item in data_list:
            ticker = item.get('Ticker')
            if not ticker: continue
            
            # Raw EPS Data
            cy_est = item.get('CY_Est')
            cy_30 = item.get('CY_30')
            ny_est = item.get('NY_Est')
            ny_30 = item.get('NY_30')
            
            # 값이 없는 경우(None)는 빈 문자열로 처리하거나 스킵?
            # 사용자 요청: "해당 티커의 값이 변동이 없거나 즉 업데이트가 되지 않았으면 스킵"
            # -> 이 말은 "이전 기록과 비교해서 값이 같으면 스킵"인 것 같음.
            # 하지만 "누적적으로 쌓는다"는 건 시계열 데이터를 의미하므로,
            # 값이 같더라도 "날짜가 다르면" (즉 3일 뒤면) 쌓는 게 일반적임.
            # 그러나 사용자가 "변동이 없으면 스킵"이라고 명시했으므로, 값 변화가 있을 때만 쌓는다.
            # 혹시 "값이 업데이트 되지 않았으면"이 "야후에서 값이 안 바뀐 경우"를 의미할 수도 있음.
            
            # 해석:
            # 1. 3일 전 데이터와 오늘 데이터가 완전히 똑같음 -> 스킵 (굳이 행 추가 안함)
            # 2. 3일 전 데이터와 오늘 데이터가 다름 -> 추가
            
            # 비교 대상 데이터 구성
            new_entry = {
                'Ticker': ticker,
                'WorkDate': today_str,
                'CY_Current': cy_est if cy_est is not None else '',
                'CY_30Ago': cy_30 if cy_30 is not None else '',
                'NY_Current': ny_est if ny_est is not None else '',
                'NY_30Ago': ny_30 if ny_30 is not None else ''
            }
            
            # Check Valid Data (적어도 Current 값은 있어야 함)
            if new_entry['CY_Current'] == '' and new_entry['NY_Current'] == '':
                continue

            # Check Last Entry
            last = last_entries.get(ticker)
            
            should_append = False
            if not last:
                should_append = True
            else:
                # 값 비교 (문자열/숫자 형변환 유의)
                # Google Sheet에서 읽어온 값은 숫자일수도, 문자일수도 있음.
                def to_str(v): return str(v).strip() if v is not None else ''
                
                # Compare
                # Date check: 만약 같은 날짜에 이미 돌렸으면 중복 추가 방지 (혹시 재실행 시)
                last_date = str(last.get('WorkDate', '')).split(' ')[0] # pandas Timestamp일 수 있으므로
                
                if last_date == today_str:
                    should_append = False # 오늘 이미 적재함
                else:
                    # 값이 다른지 확인
                    v1 = to_str(new_entry['CY_Current'])
                    v2 = to_str(last.get('CY_Current'))
                    v3 = to_str(new_entry['NY_Current'])
                    v4 = to_str(last.get('NY_Current'))
                    
                    if v1 != v2 or v3 != v4:
                        should_append = True
            
            if should_append:
                rows_to_append.append([
                    new_entry['Ticker'],
                    new_entry['WorkDate'],
                    new_entry['CY_Current'],
                    new_entry['CY_30Ago'],
                    new_entry['NY_Current'],
                    new_entry['NY_30Ago']
                ])
                
        if rows_to_append:
            # Batch Append
            sheet.append_rows(rows_to_append)
            print(f"[GSheet] {len(rows_to_append)}개 행 추가 완료.")
        else:
            print("[GSheet] 추가할 새로운 데이터(변동사항)가 없습니다.")
            
    except Exception as e:
        print(f"[GSheet] 업데이트 중 에러 발생: {e}")

if __name__ == "__main__":
    pass
