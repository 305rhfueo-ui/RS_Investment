import yfinance as yf
import pandas as pd

def calculate_bb(closes):
    if len(closes) < 20:
        return None, None

    mb = closes.rolling(window=20).mean()
    sigma = closes.rolling(window=20).std()
    
    # Calculate Bandwidth Series
    # Avoid division by zero
    bandwidth = (4 * sigma) / mb  # ( (MB+2s) - (MB-2s) ) / MB = 4s / MB
    
    # Current BBWTHD
    current_bw = bandwidth.iloc[-1]
    bbwthd = round(current_bw, 2) if pd.notna(current_bw) else None
    
    # BBWTHD LOW (Last 60 days)
    # Slice last 60 valid entries if possible
    if len(bandwidth) >= 60:
        recent_bw = bandwidth.iloc[-60:]
        min_bw = recent_bw.min()
        bbwthd_low = round(min_bw, 2) if pd.notna(min_bw) else None
    else:
        # If we have < 60 days of bandwidth data, take min of what we have
        # (After initial 20 days NaN)
        valid_bw = bandwidth.dropna()
        if not valid_bw.empty:
            min_bw = valid_bw.min()
            bbwthd_low = round(min_bw, 2) if pd.notna(min_bw) else None
            
    return bbwthd, bbwthd_low

def main():
    ticker = "AAPL"
    print(f"Fetching data for {ticker}...")
    try:
        t = yf.Ticker(ticker)
        # Fetch enough history for 60-day low + 20-day MA window (approx 4 months trading days) + buffer
        # 1y is safe
        hist = t.history(period="1y")
        closes = hist['Close']
        
        print(f"Data length: {len(closes)}")
        print(f"Latest Close: {closes.iloc[-1]:.2f}")
        
        bbw, bbw_low = calculate_bb(closes)
        
        print(f"BBWTHD: {bbw}")
        print(f"BBWTHD LOW: {bbw_low}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
