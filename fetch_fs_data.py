import json
import math
import os
import time
import random
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# Headers specifically chosen to look like a normal user
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def fetch_url(url, session):
    max_retries = 5
    base_delay = 5
    
    # 5-8 seconds delay per request to avoid banning
    time.sleep(random.uniform(5, 8))
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=20, headers=headers)
            if response.status_code == 200:
                return response, None
            elif response.status_code in [403, 429]:
                wait_time = base_delay * (attempt + 1) + random.uniform(5, 10)
                print(f"Status {response.status_code}. Waiting {wait_time:.2f}s...")
                session.cookies.clear()
                time.sleep(wait_time)
                continue
            else:
                return None, f"Status: {response.status_code}"
        except Exception as e:
            if attempt == max_retries - 1:
                return None, str(e)
            time.sleep(base_delay)
            
    return None, "Max retries reached"

def _parse_original_data(response):
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        data = None
        for script in scripts:
            if script.string and 'originalData' in script.string:
                match = re.search(r'var originalData = (\[.*?\]);', script.string)
                if match:
                    data = json.loads(match.group(1))
                    break
        
        if not data:
            return None, "originalData not found"
            
        df = pd.DataFrame(data)
        if df.empty: return None, "Empty data"
        
        df['field_name'] = df['field_name'].apply(lambda x: BeautifulSoup(x, 'html.parser').get_text())
        df.set_index('field_name', inplace=True)
        if 'popup_icon' in df.columns:
            df.drop(columns=['popup_icon'], inplace=True)
        df = df.T
        for col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '').str.replace(',', '').apply(pd.to_numeric, errors='coerce')
        df.sort_index(ascending=False, inplace=True)
        return df, None
    except Exception as e:
        return None, str(e)

def get_financial_data(ticker, freq='Q', session=None):
    if not session:
        session = requests.Session()
    
    freq_param = f"?freq={freq}"
    initial_url = f"https://www.macrotrends.net/stocks/charts/{ticker}/temp/income-statement"
    
    response, error = fetch_url(initial_url, session)
    if error: return None, error
        
    final_url = response.url
    if freq_param not in final_url:
        if '?' in final_url: target_url = final_url + f"&freq={freq}"
        else: target_url = final_url + freq_param
        response, error = fetch_url(target_url, session)
        if error: return None, error
        
    return _parse_original_data(response)

def calculate_ni_growth(series):
    rates = []
    for i in range(3):
        if i + 4 < len(series):
            curr = series.iloc[i]
            prev = series.iloc[i+4]
            if pd.notna(curr) and pd.notna(prev) and prev != 0:
                if prev < 0 and curr > 0:
                    rates.append("흑자전환")
                else:
                    g = (curr / prev) - 1
                    rates.append(round(g * 100, 2))
            else:
                rates.append(None)
        else:
            rates.append(None)
    return rates

def calculate_growth_rate(series):
    rates = []
    for i in range(3):
        if i + 4 < len(series):
            curr = series.iloc[i]
            prev = series.iloc[i+4]
            if pd.notna(curr) and pd.notna(prev) and prev != 0:
                g = (curr / abs(prev)) - 1
                rates.append(round(g * 100, 2))
            else:
                rates.append(None)
        else:
            rates.append(None)
    return rates

def get_todays_list_tickers(result_json_path):
    with open(result_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    stocks = data.get('data', [])
    todays_list = []
    
    for stock in stocks:
        val = stock.get('50DIV')
        try:
            div50 = float(val) if val is not None else -9999
        except:
            div50 = -9999
            
        if div50 <= 0 or div50 > 35: continue
            
        val_rs = stock.get('RS_6mo')
        try:
            rs6 = float(val_rs) if val_rs is not None else -9999
            
            import math
            if math.isnan(rs6): rs6 = -9999
        except:
            rs6 = -9999
            
        if rs6 <= 0: continue
            
        todays_list.append(stock['Ticker'])
        
    return list(set(todays_list))

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESULT_PATH = os.path.join(BASE_DIR, 'static', 'result.json')
    SAVE_PATH = os.path.join(BASE_DIR, 'static', 'fs_data.json')
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting FS Data Fetch...")
    
    if not os.path.exists(RESULT_PATH):
        print("result.json not found.")
        return
        
    tickers = get_todays_list_tickers(RESULT_PATH)
    print(f"Found {len(tickers)} tickers in Today's List.")
    
    # Load existing fs_data if available to not overwrite data for tickers that dropped out
    # but still might be useful to keep. (Optional, I'll just overwrite or update)
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, 'r', encoding='utf-8') as f:
            fs_data = json.load(f)
    else:
        fs_data = {}

    session = requests.Session()
    
    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] Fetching FS for {ticker}...")
        df, err = get_financial_data(ticker, freq='Q', session=session)
        
        if err or df is None:
            print(f" -> Error: {err}")
            continue
            
        res = {
            "0SALE": None, "1SALE": None, "2SALE": None,
            "0NI": None, "1NI": None, "2NI": None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if 'Revenue' in df.columns:
            sale_rates = calculate_growth_rate(df['Revenue'])
            res["0SALE"] = sale_rates[0]
            res["1SALE"] = sale_rates[1]
            res["2SALE"] = sale_rates[2]
            
        if 'Net Income' in df.columns:
            ni_rates = calculate_ni_growth(df['Net Income'])
            res["0NI"] = ni_rates[0]
            res["1NI"] = ni_rates[1]
            res["2NI"] = ni_rates[2]
            
        fs_data[ticker] = res
        print(f" -> Success: SALE={[res['0SALE'], res['1SALE'], res['2SALE']]} NI={[res['0NI'], res['1NI'], res['2NI']]}")
        
        
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(fs_data, f, indent=2, ensure_ascii=False)
        
    print("FS Data fetch complete and saved to fs_data.json.")
    
    # Auto-commit and push to GitHub
    try:
        print("Pushing to GitHub...")
        os.system('git config --global user.name "github-actions[bot]"')
        os.system('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        os.system('git add static/fs_data.json fetch_fs_data.py')
        os.system('git commit -m "Auto-update: FS Data"')
        os.system('git push')
        print("Successfully pushed to GitHub.")
    except Exception as e:
        print(f"Error pushing to GitHub: {e}")

if __name__ == "__main__":
    main()
