import yfinance as yf
import pandas as pd

def check_eps_revisions(ticker_symbol):
    print(f"Fetching EPS revisions for {ticker_symbol}...")
    ticker = yf.Ticker(ticker_symbol)
    revisions = ticker.eps_revisions
    
    if revisions is not None and not revisions.empty:
        print("\nEPS Revisions DataFrame:")
        print(revisions)
        print("\nIndex:", revisions.index.tolist())
        print("Columns:", revisions.columns.tolist())
        
        if 'upLast30days' in revisions.columns:
            print(f"\nSum of upLast30days: {revisions['upLast30days'].sum()}")
        if 'downLast30days' in revisions.columns:
            print(f"Sum of downLast30days: {revisions['downLast30days'].sum()}")
            
    else:
        print("No EPS revisions data found.")

if __name__ == "__main__":
    # Checking for AAPL or MSFT as they are likely to have data
    check_eps_revisions("AAPL")
    check_eps_revisions("MSFT")
