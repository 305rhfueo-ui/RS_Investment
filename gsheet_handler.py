
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import time

# 설정
JSON_FILE = 'service_account.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/17JU4KoC-Out5NqGy3qtN7LSunMUsH5xS2qJSk1fBDGQ/edit?gid=870712162#gid=870712162'
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
TARGET_TAB_NAME = 'RS_Estimate' # 사용자 요청에 따라 시트명 변경

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
        
        # 탭 확인 및 생성 (Robust Check)
        worksheets = doc.worksheets()
        # Case-insensitive match
        sheet = next((s for s in worksheets if s.title.lower() == TARGET_TAB_NAME.lower()), None)
        
        if sheet is None:
            print(f"[GSheet] '{TARGET_TAB_NAME}' 탭이 없어 생성합니다.")
            sheet = doc.add_worksheet(title=TARGET_TAB_NAME, rows=1000, cols=11) # cols adjusted
            # 헤더 추가
            headers = [
                'Ticker', 'WorkDate', 
                'CY_Current', 'CY_30Ago', 'CY_Trend', 
                'NY_Current', 'NY_30Ago', 'NY_Trend',
                'UP_Count', 'Down_Count', 'Up_Down_Ratio',
                'Target_Status'
            ]
            sheet.append_row(headers)
        else:
            print(f"[GSheet] '{TARGET_TAB_NAME}' 탭을 찾았습니다.")

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
            cy_est = item.get('CY_Current')
            cy_30 = item.get('CY_30Ago')
            ny_est = item.get('NY_Current')
            ny_30 = item.get('NY_30Ago')
            
            # Trend & Revision Data
            cy_trend = item.get('CY_Trend')
            ny_trend = item.get('NY_Trend')
            up_count = item.get('Up_Count')
            down_count = item.get('Down_Count')
            up_down_ratio = item.get('Up_Down_Ratio')
            target_status = item.get('Target_Status', 'NO')
            
            # Helper to handle NaN
            def sanitize(val):
                if val is None: return ''
                if isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf')): # Check for NaN/Inf
                    return ''
                return val

            # 구성 (User Request Order)
            # 1.Ticker, 2.WorkDate, 3.CY_Current, 4.CY_30Ago, 5.CY_Trend, 
            # 6.NY_Current, 7.NY_30Ago, 8.NY_Trend, 9.UP#, 10.DOWN#, 11.Ratio, 12.Target
            new_entry = {
                'Ticker': ticker,
                'WorkDate': today_str,
                'CY_Current': sanitize(cy_est),
                'CY_30Ago': sanitize(cy_30),
                'CY_Trend': sanitize(cy_trend),
                'NY_Current': sanitize(ny_est),
                'NY_30Ago': sanitize(ny_30),
                'NY_Trend': sanitize(ny_trend),
                'UP_Count': sanitize(up_count),
                'Down_Count': sanitize(down_count),
                'Up_Down_Ratio': sanitize(up_down_ratio),
                'Target_Status': target_status
            }
            
            # Check Last Entry
            last = last_entries.get(ticker)
            
            should_append = False
            if not last:
                should_append = True
            else:
                def to_str(v): return str(v).strip() if v is not None else ''
                
                last_date = str(last.get('WorkDate', '')).split(' ')[0]
                
                if last_date == today_str:
                    should_append = False 
                else:
                    # 값이 다른지 확인
                    check_keys = ['CY_Current', 'NY_Current', 'CY_Trend', 'NY_Trend', 'Target_Status']
                    is_diff = False
                    for k in check_keys:
                        if to_str(new_entry[k]) != to_str(last.get(k)):
                            is_diff = True
                            break
                    
                    if is_diff:
                        should_append = True
            
            if should_append:
                rows_to_append.append([
                    new_entry['Ticker'],
                    new_entry['WorkDate'],
                    new_entry['CY_Current'],
                    new_entry['CY_30Ago'],
                    new_entry['CY_Trend'],
                    new_entry['NY_Current'],
                    new_entry['NY_30Ago'],
                    new_entry['NY_Trend'],
                    new_entry['UP_Count'],
                    new_entry['Down_Count'],
                    new_entry['Up_Down_Ratio'],
                    new_entry['Target_Status']
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
