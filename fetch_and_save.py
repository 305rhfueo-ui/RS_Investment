
import pandas as pd
import json
import os
import pandas as pd
import json
import os
import time
import shutil
from datetime import datetime
# utils에 있는 강력한 병렬 처리 함수 가져오기
import utils

# 설정
# 기존 엑셀 대신 구글 시트 사용
GOOGLE_SHEET_ID = "17JU4KoC-Out5NqGy3qtN7LSunMUsH5xS2qJSk1fBDGQ"
GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv"

OUTPUT_FILE = "static/result.json"
HISTORY_DIR = "static/history"
HISTORY_INDEX = "static/history_index.json"

def backup_existing_data():
    """
    기존 result.json을 읽어서 날짜별로 history/ 폴더에 백업
    """
    if not os.path.exists(OUTPUT_FILE):
        print("  → 백업할 기존 데이터 없음 (첫 실행)")
        return None
    
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # last_updated에서 날짜 추출 (예: "2026-01-29 15:16:00 UTC" -> "2026-01-29")
        last_updated = old_data.get('last_updated', '')
        if last_updated:
            date_str = last_updated.split()[0]  # "2026-01-29"
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # history 폴더 생성
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)
        
        # 백업 파일명: result_2026-01-29.json
        backup_file = os.path.join(HISTORY_DIR, f"result_{date_str}.json")
        
        # 이미 같은 날짜 백업이 있으면 덮어쓰기
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, ensure_ascii=False, indent=2)
        
        print(f"  → 기존 데이터 백업: {backup_file}")
        return date_str
    
    except Exception as e:
        print(f"  ⚠️ 백업 실패: {e}")
        return None

def update_history_index():
    """
    history_index.json 업데이트 (날짜 목록)
    """
    if not os.path.exists(HISTORY_DIR):
        return
    
    # history 폴더에서 모든 JSON 파일 찾기
    history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith('result_') and f.endswith('.json')])
    
    # 날짜 추출 (result_2026-01-29.json -> 2026-01-29)
    dates = []
    for filename in history_files:
        date_part = filename.replace('result_', '').replace('.json', '')
        dates.append({
            "date": date_part,
            "filename": f"history/{filename}"
        })
    
    # 최신순 정렬
    dates.sort(key=lambda x: x['date'], reverse=True)
    
    index_data = {
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "total_history": len(dates),
        "dates": dates
    }
    
    with open(HISTORY_INDEX, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"  → 히스토리 인덱스 업데이트: {len(dates)}개 날짜")

def main():
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # ===== 히스토리 백업 (기존 로직 제거 - 수집 후 즉시 저장으로 변경) =====
    # print(f"[{time.strftime('%X')}] 기존 데이터 백업 중...")
    # backup_existing_data()

    print(f"[{time.strftime('%X')}] 구글 시트 데이터 로드 중...")
    # Load Tickers
    print("구글 시트 데이터 로드 중...")
    ticker_info_list = utils.get_tickers_from_google_sheet(GOOGLE_SHEET_URL)
    
    # 2. 실패 시 Fallback
    if not ticker_info_list:
        print("⚠️ 구글 시트 로드 실패 (Fallback 모드)")
        # 주요 나스닥/S&P500 티커 Fallback
        ticker_info_list = [
            {"Ticker": "AAPL", "Sector": "Technology", "Industry": "Consumer Electronics"},
            {"Ticker": "MSFT", "Sector": "Technology", "Industry": "Software - Infrastructure"},
            {"Ticker": "NVDA", "Sector": "Technology", "Industry": "Semiconductors"},
            {"Ticker": "GOOGL", "Sector": "Communication Services", "Industry": "Internet Content & Information"},
            {"Ticker": "AMZN", "Sector": "Consumer Cyclical", "Industry": "Internet Retail"},
            {"Ticker": "TSLA", "Sector": "Consumer Cyclical", "Industry": "Auto Manufacturers"},
            {"Ticker": "META", "Sector": "Communication Services", "Industry": "Internet Content & Information"},
            {"Ticker": "AMD", "Sector": "Technology", "Industry": "Semiconductors"},
            {"Ticker": "NFLX", "Sector": "Communication Services", "Industry": "Entertainment"},
            {"Ticker": "PLTR", "Sector": "Technology", "Industry": "Software - Infrastructure"}
        ]
    else:
        print(f"[{time.strftime('%X')}] 대상 티커: {len(ticker_info_list)}개")
    
    start_time = time.time()
    
    # 병렬 처리 함수 실행 (20개씩 동시 작업)
    try:
        results = utils.get_market_cap_and_rs(ticker_info_list)
    except Exception as e:
        print(f"수집 중 에러 발생: {e}")
        results = []
    
    
    # Save Sector Cache (Persistence)
    utils.save_sector_cache()

    end_time = time.time()
    duration = end_time - start_time
    
    print(f"[{time.strftime('%X')}] 수집 완료! 소요 시간: {duration:.1f}초, 성공: {len(results)}개")

    # ===== 퍼센타일 순위 계산 =====
    print(f"[{time.strftime('%X')}] RS 퍼센타일 순위 계산 중...")
    
    # 개별 RS(6MO) 퍼센타일
    rs_6mo_values = [r['RS_6mo'] for r in results if r.get('RS_6mo') is not None]
    for item in results:
        rs_val = item.get('RS_6mo')
        item['RS_Rank_Pct'] = utils.calculate_percentile_rank(rs_val, rs_6mo_values)
    
    # WRS 계산을 위한 Sector/Industry 그룹핑
    from collections import defaultdict
    import statistics
    
    sector_groups = defaultdict(list)
    for item in results:
        if (item.get('Sector') and item['Sector'] not in ['N/A', 'nan'] and
            item.get('Industry') and item['Industry'] not in ['N/A', 'nan'] and
            item.get('RS_6mo') is not None):
            key = f"{item['Sector']}|{item['Industry']}"
            sector_groups[key].append(item['RS_6mo'])
    
    # WRS 데이터 생성 (중앙값 포함)
    wrs_data = []
    for key, rs_values in sector_groups.items():
        if len(rs_values) >= 1:  # 최소 1개 이상
            sector, industry = key.split('|')
            median_rs = statistics.median(rs_values)
            wrs_data.append({
                'Sector': sector,
                'Industry': industry,
                'Count': len(rs_values),
                'WRS_6mo_MD': round(median_rs, 4)
            })
    
    # WRS 중앙값 퍼센타일 계산
    wrs_md_values = [w['WRS_6mo_MD'] for w in wrs_data]
    for wrs_item in wrs_data:
        wrs_item['WRS_MD_Rank_Pct'] = utils.calculate_percentile_rank(wrs_item['WRS_6mo_MD'], wrs_md_values)
    
    # ===== Market Condition 가져오기 =====
    print(f"[{time.strftime('%X')}] Market Condition 가져오는 중...")
    market_condition = utils.get_market_condition_from_sheet()
    print(f"  → Market Condition: {market_condition}")

    output_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_count": len(results),
        "market_condition": market_condition,
        "wrs_data": wrs_data,
        "data": results
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"결과 파일 저장 완료: {OUTPUT_FILE}")
    
    # ===== 금일 데이터 히스토리 즉시 저장 =====
    try:
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)
        
        # 날짜 추출 (UTC 기준)
        today_str = datetime.utcnow().strftime("%Y-%m-%d") # UTC 기준 오늘 날짜
        history_file = os.path.join(HISTORY_DIR, f"result_{today_str}.json")
        
        shutil.copy(OUTPUT_FILE, history_file)
        print(f"[{time.strftime('%X')}] 히스토리 즉시 아카이빙 완료: {history_file}")
    except Exception as e:
        print(f"⚠️ 히스토리 저장 실패: {e}")
    
    # ===== 히스토리 인덱스 업데이트 =====
    print(f"[{time.strftime('%X')}] 히스토리 인덱스 업데이트 중...")
    update_history_index()
    print(f"[{time.strftime('%X')}] 모든 작업 완료!")

if __name__ == "__main__":
    main()
