import yfinance as yf
t = yf.Ticker("LITE")
print("--- earnings_estimate ---")
try:
    print(t.earnings_estimate)
except Exception as e:
    print(e)
print("--- revenue_estimate ---")
try:
    print(t.revenue_estimate)
except Exception as e:
    print(e)
