import pandas as pd
import requests
import yfinance as yf
import time
import io
import warnings
from concurrent.futures import ThreadPoolExecutor
import subprocess
# 경고 메시지 숨김 (Pyarrow 등)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import json
import os

# 전역 캐시 변수
SECTOR_CACHE_FILE = "static/sector_search.json"
SECTOR_CACHE = {}

ANALYSIS_CACHE_FILE = "static/analysis_cache.json"
ANALYSIS_CACHE = {}

def git_push():
    """
    변경된 데이터를 자동으로 GitHub에 업로드합니다.
    """
    try:
        print("\n[Git] GitHub 업데이트 시작...")
        
        # 1. 모든 변경사항 추가
        subprocess.run(["git", "add", "."], check=True)
        
        # 2. 커밋
        # datetime은 이미 import 되어있지 않으므로 time.strftime 사용
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(["git", "commit", "-m", f"Auto-update: {timestamp}"], check=False) 
        
        # 3. 푸시
        subprocess.run(["git", "push"], check=True)
        print("[Git] 업데이트 완료! (웹사이트에 곧 반영됩니다)")
        
    except Exception as e:
        print(f"[Git] 업데이트 실패: {e}")
        print("  -> 수동으로 '소스 제어' 탭에서 커밋 및 동기화를 해주세요.")



def sanitize_ticker_for_yf(ticker):
    """
    Yahoo Finance용 티커 포맷 변환:
    - 하이픈(-) 포함 시: '-' -> 'P' (예: BA-A -> BA-PA, QXO-B -> QXO-PB)
    - 점(.) 포함 시: '.' -> '-' (예: AGM.A -> AGM-A)
    """
    if '-' in ticker:
        # BA-A -> BA-PA, HL-B -> HL-PB
        return ticker.replace('-', '-P')
    elif '.' in ticker:
        # AGM.A -> AGM-A
        return ticker.replace('.', '-')
    return ticker

def load_sector_cache():
    global SECTOR_CACHE
    if os.path.exists(SECTOR_CACHE_FILE):
        try:
            with open(SECTOR_CACHE_FILE, 'r', encoding='utf-8') as f:
                SECTOR_CACHE = json.load(f)
            print(f"Sector Cache Loaded: {len(SECTOR_CACHE)} items")
        except Exception as e:
            print(f"Cache Load Error: {e}")
            SECTOR_CACHE = {}

def save_sector_cache():
    try:
        if not os.path.exists('static'):
            os.makedirs('static')
        with open(SECTOR_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(SECTOR_CACHE, f, ensure_ascii=False, indent=2)
        print(f"Sector Cache Saved: {len(SECTOR_CACHE)} items")
    except Exception as e:
        print(f"Cache Save Error: {e}")

def load_analysis_cache():
    global ANALYSIS_CACHE
    if os.path.exists(ANALYSIS_CACHE_FILE):
        try:
            with open(ANALYSIS_CACHE_FILE, 'r', encoding='utf-8') as f:
                ANALYSIS_CACHE = json.load(f)
            print(f"Analysis Cache Loaded: {len(ANALYSIS_CACHE)} items")
        except Exception as e:
            print(f"Analysis Cache Load Error: {e}")
            ANALYSIS_CACHE = {}

def save_analysis_cache():
    try:
        if not os.path.exists('static'):
            os.makedirs('static')
        with open(ANALYSIS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(ANALYSIS_CACHE, f, ensure_ascii=False, indent=2)
        print(f"Analysis Cache Saved: {len(ANALYSIS_CACHE)} items")
    except Exception as e:
        print(f"Analysis Cache Save Error: {e}")

# 초기 로드
load_sector_cache()
load_analysis_cache()

def calculate_percentile_rank(value, all_values):
    """
    퍼센타일 순위 계산 (값이 클수록 순위가 높음, top X% 반환)
    예: 10개 중 1등이면 10% (top 10%), 10등이면 100% (top 100%)
    """
    if value is None:
        return None
    sorted_desc = sorted([v for v in all_values if v is not None], reverse=True)
    if len(sorted_desc) == 0:
        return None
    try:
        rank = sorted_desc.index(value) + 1
        return round((rank / len(sorted_desc)) * 100, 2)
    except ValueError:
        return None

def get_market_condition_from_sheet():
    """
    구글 시트의 특정 셀(A1)에서 Market Condition 텍스트 읽기
    """
    try:
        # gid 파라미터를 포함한 CSV export URL
        url = "https://docs.google.com/spreadsheets/d/17JU4KoC-Out5NqGy3qtN7LSunMUsH5xS2qJSk1fBDGQ/export?format=csv&gid=1044365555"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # UTF-8 인코딩 명시 (한글 깨짐 방지)
        response.encoding = 'utf-8'
        
        # CSV 첫 줄, 첫 컬럼 읽기
        csv_data = io.StringIO(response.text)
        df = pd.read_csv(csv_data, header=None, encoding='utf-8')
        
        if not df.empty and len(df.columns) > 0:
            market_condition = str(df.iloc[0, 0]).strip()
            return market_condition if market_condition else "N/A"
        return "N/A"
    except Exception as e:
        print(f"Market Condition 로드 에러: {e}")
        return "N/A"

def get_tickers_from_google_sheet(url):
    """
    구글 시트 CSV URL에서 티커 목록을 가져옵니다.
    A열에 티커가 있다고 가정합니다.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # CSV 데이터를 pandas DataFrame으로 읽기 (헤더 없음 가정)
        # 만약 첫 줄이 티커라면 header=None을 써야 함.
        # 사용자가 "A 열에서 티커를 긁어다가"라고 했고, 확인 결과 첫 줄부터 티커임 (LRN)
        df = pd.read_csv(io.StringIO(response.text), header=None)
        
        # 첫 번째 컬럼을 티커로 간주
        if df.empty:
            return []
            
        ticker_column = df.columns[0] # 0번 인덱스
        tickers = df[ticker_column].dropna().unique().tolist()
        
        # fetch_and_save.py 호환성을 위해 딕셔너리 리스트로 변환
        # (기존 로직이 {'Ticker': 'AAPL', ...} 형태를 기대할 수 있음)
        ticker_info_list = [{'Ticker': str(t).strip().upper()} for t in tickers if str(t).strip()]
        
        return ticker_info_list
        
    except Exception as e:
        print(f"구글 시트 로드 중 에러: {e}")
        return []

def get_tickers_from_excel(file_path):
    """
    레거시 호환성을 위한 엑셀 읽기 함수 (현재는 사용되지 않을 수 있음)
    """
    try:
        df = pd.read_excel(file_path, sheet_name=0)
        tickers = df.iloc[:, 0].dropna().tolist() # 첫 번째 컬럼
        return [{'Ticker': str(t).strip().upper()} for t in tickers]
    except Exception as e:
        print(f"엑셀 로드 에러: {e}")
        return []

def get_market_cap_and_rs(ticker_info_list, batch_size=10):
    """
    티커 리스트를 받아 Market Cap과 RS를 계산합니다.
    20개씩 배치로 처리하여 yfinance 부하를 조절합니다.
    """
    results = []
    total_tickers = len(ticker_info_list)
    
    # QQQ 데이터 미리 확보 (벤치마크)
    print("벤치마크 (QQQ) 데이터 다운로드 중...")
    try:
        # 120영업일(6mo) 확보를 위해 1년치 데이터 요청
        qqq_data = yf.download("QQQ", period="1y", progress=False)
        if len(qqq_data) < 121:
            print("경고: QQQ 데이터가 충분하지 않아 RS 계산이 부정확할 수 있습니다.")
    except Exception as e:
        print(f"QQQ 다운로드 실패: {e}")
        qqq_data = pd.DataFrame()

    for i in range(0, total_tickers, batch_size):
        batch = ticker_info_list[i:i+batch_size]
        batch_tickers = [item['Ticker'] for item in batch]
        print(f"Processing batch {i} to {min(i+batch_size, total_tickers)}: {batch_tickers}")
        
        try:
            # 1. 주가 데이터 일괄 다운로드 (Price & RS용)
            # Yahoo Finance용 포맷으로 변환
            sanitized_batch_tickers = [sanitize_ticker_for_yf(t) for t in batch_tickers]
            
            # 6개월(120영업일) 데이터를 위해 1년치 가져옴
            data = yf.download(sanitized_batch_tickers, period="1y", progress=False, group_by='ticker')
            
            # 2. 각 티커별 정보 처리
            # 메타데이터(시총 등)는 별도 호출이 필요할 수 있으나, 
            # yfinance 최신 버전에서는 download로 시총을 못 가져오므로 Ticker.info 접근 필요
            # 속도를 위해 ThreadPool 사용
            
            # 병렬 처리 대신 순차 처리로 변경 (Rate Limit 방지)
            for ticker in batch_tickers:
                res = process_single_ticker(ticker, data, qqq_data)
                if res:
                    results.append(res)
                        
        except Exception as e:
            print(f"Batch 처리 중 에러: {e}")
            
        # 딜레이 (옵션)
        time.sleep(10)
    
    # --- Retry Logic (재시도) ---
    # 1. 실패하거나 RS가 NaN인 티커 식별
    # results에는 {Ticker, RS_6mo, ...} 딕셔너리가 들어있음.
    processed_tickers = set()
    for r in results:
        if r and 'Ticker' in r:
            # RS_6mo 기준 검증
            rs_val = r.get('RS_6mo')
            is_valid = False
            if rs_val is not None:
                try:
                    if str(rs_val).lower() != 'nan':
                        processed_tickers.add(r['Ticker'])
                except:
                    pass

    all_tickers = {item['Ticker'] for item in ticker_info_list}
    failed_tickers = list(all_tickers - processed_tickers)
    
    if failed_tickers:
        print(f"\n[Retry] RS 수집 실패/NaN {len(failed_tickers)}개 발견. 배치 재시도 중...")
        
        # 재시도도 배치로 처리
        retry_batch_size = 10
        for i in range(0, len(failed_tickers), retry_batch_size):
            batch = failed_tickers[i:i+retry_batch_size]
            print(f" -> Retry batch {batch}")
            
            try:
                # 배치 다운로드 (Sanitized Ticker 사용)
                sanitized_retry_batch = [sanitize_ticker_for_yf(t) for t in batch]
                data = yf.download(sanitized_retry_batch, period="1y", progress=False, group_by='ticker')
                
                # 순차 처리 (Retry)
                for t in batch:
                    res = process_single_ticker(t, data, qqq_data)
                    if res:
                        rs_res = res.get('RS_6mo')
                        if rs_res is not None and str(rs_res).lower() != 'nan':
                            # 성공 시 기존 결과 제거 후 추가
                            results = [r for r in results if r['Ticker'] != res['Ticker']]
                            results.append(res)
                            print(f"    -> {res['Ticker']} 복구 성공 (RS_6mo: {res['RS_6mo']})")
                        else:
                            print(f"    -> {res['Ticker']} 복구 실패")
                                
            except Exception as e:
                print(f"Retry Batch 에러: {e}")
            
            time.sleep(10) # 배치 간 딜레이

    # 작업 완료 후 캐시 저장
    save_sector_cache()
    save_analysis_cache()
    
    return results

def process_single_ticker(original_ticker, batch_data, qqq_data):
    """
    단일 티커에 대한 RS 계산 및 Info 처리를 수행합니다.
    """
    try:
        # Sanitize for API usage locally
        yf_ticker = sanitize_ticker_for_yf(original_ticker)
        
        # 데이터 추출 (MultiIndex 처리)
        if isinstance(batch_data.columns, pd.MultiIndex):
             # batch_data['Close'][ticker] 와 같은 형태로 접근
             if yf_ticker in batch_data.columns.levels[0]:
                 df = batch_data[yf_ticker]
             else:
                 # 티커가 하나뿐일 경우 구조가 다를 수 있음 처리
                 # download시 list로 넘겼으므로 보통 MultiIndex임.
                 # 데이터가 없는 경우
                 return None
        else:
            # 티커가 1개인 배치였을 경우
            df = batch_data
            
        # Close Price 확인
        if 'Close' not in df.columns or df.empty:
            return None
            
        hist = df['Close']
        
        # --- RS Calculation Logic Update ---
        # 기간: 
        # 1mo = 20영업일
        # 3mo = 60영업일
        # 6mo = 120영업일
        
        idx_latest = -1
        idx_1mo = -21
        idx_3mo = -61
        idx_6mo = -121
        
        # 데이터 길이 체크
        data_len = len(hist)
        qqq_len = len(qqq_data) if not qqq_data.empty else 0
        
        # Helper Inner Function
        def calc_return(series, idx_start, idx_end):
            try:
                if len(series) < abs(idx_start): return None
                curr = float(series.iloc[idx_end])
                prev = float(series.iloc[idx_start])
                if prev == 0: return 0
                return (curr - prev) / prev
            except:
                return None

        # 1. Calculate Returns
        stock_ret_1mo = calc_return(hist, idx_1mo, idx_latest)
        stock_ret_3mo = calc_return(hist, idx_3mo, idx_latest)
        stock_ret_6mo = calc_return(hist, idx_6mo, idx_latest)
        
        # 2. Benchmark Returns
        if qqq_len < 121:
            # QQQ 데이터 부족 시 0 처리 혹은 None
            qqq_ret_1mo = 0
            qqq_ret_3mo = 0
            qqq_ret_6mo = 0
        else:
            q_hist = qqq_data['Close']
            qqq_ret_1mo = calc_return(q_hist, idx_1mo, idx_latest) or 0
            qqq_ret_3mo = calc_return(q_hist, idx_3mo, idx_latest) or 0
            qqq_ret_6mo = calc_return(q_hist, idx_6mo, idx_latest) or 0

        # 3. RS Calculation (Difference)
        # RS = Stock_Return - QQQ_Return
        
        rs_1mo = (stock_ret_1mo - qqq_ret_1mo) if stock_ret_1mo is not None else 0
        rs_3mo = (stock_ret_3mo - qqq_ret_3mo) if stock_ret_3mo is not None else 0
        rs_6mo = (stock_ret_6mo - qqq_ret_6mo) if stock_ret_6mo is not None else 0
        
        latest_price = float(hist.iloc[-1]) if not hist.empty else 0
        
        # --- Order Calculation (Current Price > 50MA > 150MA > 200MA) ---
        ma50 = hist.rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else 0
        ma150 = hist.rolling(window=150).mean().iloc[-1] if len(hist) >= 150 else 0
        ma200 = hist.rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else 0
        
        is_order = (latest_price > ma50) and (ma50 > ma150) and (ma150 > ma200)
        order_val = "YES" if is_order else "NO"
        
        # 메타데이터 (Market Cap, Sector, Industry)
        # For Metadata, loop up using sanitied ticker
        t = yf.Ticker(yf_ticker)
        
        # 1. Sector/Industry (Cache Check) uses ORIGINAL ticker key usually, 
        # but for API fetch we must use yf_ticker.
        # Let's keep cache key as valid yf_ticker to avoid confusion, OR use original.
        # User list has original. Let's try to stick to original for cache key if possible, 
        # but the cached data implies 'what returns from API'.
        # Actually simplest is: Use ORIGINAL for UI/Result, use YF_TICKER for API.
        
        cached = SECTOR_CACHE.get(original_ticker) 
        sector = "N/A"
        industry = "N/A"
        
        # Check Cache
        if cached and cached.get('Sector') not in ['N/A', 'nan', 'NONE'] and cached.get('Industry') not in ['N/A', 'nan', 'NONE']:
            sector = cached['Sector']
            industry = cached['Industry']
        else:
            # Fetch Metadata
            if sector == "N/A" and industry == "N/A":
                try:
                    info = t.info 
                    
                    quote_type = info.get('quoteType', '').upper()
                    
                    if 'ETF' in quote_type:
                        sector = 'ETF'
                        industry = 'ETF' # User requested both to be ETF
                    elif 'ETN' in quote_type: 
                        sector = 'ETN'
                        industry = 'ETN' # User requested both to be ETN
                    else:
                        sector = info.get('sector', 'N/A')
                        industry = info.get('industry', 'N/A')

                    if not sector: sector = 'N/A'
                    if not industry: industry = 'N/A'
                        
                    # Save to Cache using ORIGINAL key for consistency
                    SECTOR_CACHE[original_ticker] = {'Sector': sector, 'Industry': industry}
                except:
                    sector = 'N/A'
                    industry = 'N/A'

        # 2. Market Cap (Fast Info)
        market_cap = 0
        try:
            market_cap = t.fast_info['market_cap']
        except:
            pass
        
        # 3. 50-day Moving Average Divergence (50DIV)
        div_50 = None
        try:
            if len(hist) >= 50:
                ma_50 = hist.iloc[-50:].mean()
                if ma_50 != 0:
                    div_50 = round(((latest_price - ma_50) / ma_50) * 100, 2)
        except Exception as e:
            print(f"50DIV 계산 에러 ({original_ticker}): {e}")

        # 4. RS Estimate Calculation with Caching (3 Days)
        cy_trend = None
        ny_trend = None
        up_count = None
        down_count = None
        up_down_ratio = None
        
        # Analysis Cache Start
        from datetime import datetime, timedelta
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        cache_item = ANALYSIS_CACHE.get(original_ticker)
        
        # Check if cache is valid (within 3 days)
        use_cache = False
        if cache_item and 'timestamp' in cache_item:
            try:
                cached_date = datetime.strptime(cache_item['timestamp'], "%Y-%m-%d")
                if (datetime.now() - cached_date).days < 3:
                    use_cache = True
            except:
                pass
        
        if use_cache:
            # Use Cached Data
            data = cache_item.get('data', {})
            cy_trend = data.get('CY_Trend')
            ny_trend = data.get('NY_Trend')
            up_count = data.get('Up_Count')
            down_count = data.get('Down_Count')
            up_down_ratio = data.get('Up_Down_Ratio')
            # print(f"Using Cache for {original_ticker}")
            
        else:
            # Fetch New Data
            try:
                # t = yf.Ticker(yf_ticker) # Already defined above
                
                # (A) EPS Trend
                eps_trend_df = t.eps_trend
                
                if eps_trend_df is not None and not eps_trend_df.empty:
                    # CY Trend
                    try:
                        if '0y' in eps_trend_df.index:
                            cy_est = eps_trend_df.loc['0y', 'current']
                            cy_30 = eps_trend_df.loc['0y', '30daysAgo']
                            if cy_30 and cy_30 != 0:
                                cy_trend = round(((cy_est / cy_30) - 1) * 100, 2)
                    except: pass

                    # NY Trend
                    try:
                        if '+1y' in eps_trend_df.index:
                            ny_est = eps_trend_df.loc['+1y', 'current']
                            ny_30 = eps_trend_df.loc['+1y', '30daysAgo']
                            if ny_30 and ny_30 != 0:
                                ny_trend = round(((ny_est / ny_30) - 1) * 100, 2)
                    except: pass

                # (B) EPS Revisions
                eps_rev_df = t.eps_revisions
                
                if eps_rev_df is not None and not eps_rev_df.empty:
                    try:
                        if 'upLast30days' in eps_rev_df.columns:
                            up_count = int(eps_rev_df['upLast30days'].sum())
                        if 'downLast30days' in eps_rev_df.columns:
                            down_count = int(eps_rev_df['downLast30days'].sum())
                            
                        if up_count is not None and down_count is not None:
                            total = up_count + down_count
                            if total > 0:
                                up_down_ratio = round((up_count / total) * 100, 2)
                            else:
                                up_down_ratio = 0.0
                    except: pass
                
                # Save to Cache
                ANALYSIS_CACHE[original_ticker] = {
                    "timestamp": today_str,
                    "data": {
                        "CY_Trend": cy_trend,
                        "NY_Trend": ny_trend,
                        "Up_Count": up_count,
                        "Down_Count": down_count,
                        'Up_Down_Ratio': up_down_ratio,
                        'Order': order_val
                    }
                }
                
            except Exception as e:
                # print(f"Analysis Fetch Error {original_ticker}: {e}")
                pass
            
        return {
            'Ticker': original_ticker, # Return original for UI
            'Price': float(latest_price),
            'Market Cap': f"{market_cap / 1e9:.2f}B" if market_cap else "N/A",
            'RS_6mo': float(rs_6mo),
            'RS_3mo': float(rs_3mo),
            'RS_1mo': float(rs_1mo),
            '50DIV': div_50,  # 50일 이동평균 괴리율
            'Sector': sector,
            'Industry': industry,
            # [Added] RS Estimate Columns
            'CY_Trend': cy_trend if 'cy_trend' in locals() else None,
            'NY_Trend': ny_trend if 'ny_trend' in locals() else None,
            'Up_Count': up_count if 'up_count' in locals() else None,
            'Down_Count': down_count if 'down_count' in locals() else None,
            'Up_Down_Ratio': up_down_ratio if 'up_down_ratio' in locals() else None
        }

    except Exception as e:
        print(f"Error processing {original_ticker}: {e}")
        return None
