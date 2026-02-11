import utils
import yfinance as yf
import pandas as pd

def debug_process():
    tickers = [{'Ticker': 'AAPL'}, {'Ticker': 'NVDA'}]
    print("Testing with tickers:", tickers)
    
    # Simulate the logic in get_market_cap_and_rs
    batch_tickers = [t['Ticker'] for t in tickers]
    sanitized = [utils.sanitize_ticker_for_yf(t) for t in batch_tickers]
    
    print("Downloading data...")
    data = yf.download(sanitized, period="1y", progress=False, group_by='ticker')
    print("\nDownload Data Type:", type(data))
    print("Download Data Columns:\n", data.columns)
    
    for t in batch_tickers:
        print(f"\nProcessing {t}...")
        try:
            # Copy-paste logic from utils.process_single_ticker to inspect
            yf_ticker = utils.sanitize_ticker_for_yf(t)
            
            if isinstance(data.columns, pd.MultiIndex):
                print(f"MultiIndex detected. Levels: {data.columns.levels}")
                if yf_ticker in data.columns.levels[0]:
                    df = data[yf_ticker]
                    print(f"Extracted df for {yf_ticker}. Columns: {df.columns}")
                    # Check if 'Close' exists
                    if 'Close' in df.columns:
                        print(f"'Close' column found. Length: {len(df['Close'])}")
                    else:
                        print(f"'Close' column MISSING. Available: {df.columns.tolist()}")
                else:
                    print(f"Ticker {yf_ticker} not in level 0 columns.")
            else:
                 print("Not MultiIndex.")
                 df = data
                 print(f"Columns: {df.columns}")
            
            # Now call the actual function
            res = utils.process_single_ticker(t, data, pd.DataFrame()) # Pass empty QQQ data for now
            if res:
                print("Result SUCCESS")
            else:
                print("Result FAILED (None returned)")
                
        except Exception as e:
            print(f"Exception during debug: {e}")

if __name__ == "__main__":
    debug_process()
