import utils
import yfinance as yf
import pandas as pd

def verify_order():
    ticker = "NVDA"
    print(f"Verifying Order logic for {ticker}...")
    
    # Simulate data download
    data = yf.download([ticker], period="1y", progress=False, group_by='ticker')
    
    # Process
    # utils.process_single_ticker expects (original_ticker, batch_data, qqq_data)
    # batch_data structure depends on download. 
    # If single ticker download, structure is simpler usually, but let's see.
    
    print("Data Columns:", data.columns)
    
    # yfinance 0.2.x with auto_adjust=True/False might change columns
    # In utils.py we handle MultiIndex.
    
    res = utils.process_single_ticker(ticker, data, pd.DataFrame()) # QQQ empty for now
    
    if res:
        print(f"\n[{ticker}] Result:")
        print(f"Price: {res.get('Price')}")
        print(f"Sector: {res.get('Sector')}")
        print(f"Order: {res.get('Order')}")
        
        # Manually check logic
        # closes = data['Close'] if 'Close' in data else data
        if isinstance(data.columns, pd.MultiIndex):
             closes = data[ticker]['Close'] # Assuming MultiIndex structure if grouped
        else:
             closes = data['Close'] # Single level
             
        ma50 = closes.rolling(window=50).mean().iloc[-1]
        ma150 = closes.rolling(window=150).mean().iloc[-1]
        ma200 = closes.rolling(window=200).mean().iloc[-1]
        price = closes.iloc[-1]
        
        print("\nManual Check:")
        print(f"Price: {price:.2f}")
        print(f"MA50: {ma50:.2f}")
        print(f"MA150: {ma150:.2f}")
        print(f"MA200: {ma200:.2f}")
        
        is_order = (price > ma50) and (ma50 > ma150) and (ma150 > ma200)
        print(f"Calculated Order should be: {'YES' if is_order else 'NO'}")
        
    else:
        print("Process returned None.")

if __name__ == "__main__":
    verify_order()
