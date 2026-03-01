import utils
import pandas as pd
import yfinance as yf

# Download a tiny batch of data
ticker = 'LITE'
data = yf.download(ticker, period="1y", progress=False, group_by='ticker')
qqq_data = yf.download("QQQ", period="1y", progress=False)

# clear cache in memory for LITE to force re-fetch
if ticker in utils.ANALYSIS_CACHE:
    del utils.ANALYSIS_CACHE[ticker]

result = utils.process_single_ticker(ticker, data, qqq_data)

print("LITE Test Result:")
if result:
    print("SALE CY(%):", result.get('SALE_CY'))
    print("SALE NY(%):", result.get('SALE_NY'))
    print("EPS CY(%):", result.get('EPS_CY'))
    print("EPS NY(%):", result.get('EPS_NY'))
    print("CY_Trend(%):", result.get('CY_Trend'))
    print("NY_Trend(%):", result.get('NY_Trend'))
else:
    print("Process returned None")
