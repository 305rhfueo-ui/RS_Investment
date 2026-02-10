
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# 1. 설정
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
JSON_FILE = 'service_account.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/17JU4KoC-Out5NqGy3qtN7LSunMUsH5xS2qJSk1fBDGQ/edit?gid=870712162#gid=870712162'

def test_connection():
    try:
        print("1. 구글 시트 연결 시도...")
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, SCOPE)
        client = gspread.authorize(creds)
        
        print("2. 스프레드시트 열기...")
        doc = client.open_by_url(SHEET_URL)
        print(f" -> 문서 제목: {doc.title}")
        
        print("3. 'tickers' 탭 읽기...")
        try:
            sheet = doc.worksheet('tickers')
        except:
            print(" -> 'tickers' 탭을 찾을 수 없어 첫 번째 탭을 읽습니다.")
            sheet = doc.sheet1
            
        data = sheet.get_all_values()
        df = pd.DataFrame(data)
        print("\n[데이터 미리보기]")
        print(df.head())
        
        print("\n✅ 연결 성공!")
        return True
        
    except Exception as e:
        print(f"\n❌ 연결 실패: {e}")
        return False

if __name__ == "__main__":
    test_connection()
