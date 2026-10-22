"""
마지막 봉 메우기 회귀 테스트 — 네트워크 없이 (2026-10-22).
    python test_last_bar_fill.py
야후가 장 마감 뒤 당일 봉을 NaN 으로 줄 때 메타 종가로 마지막 봉 하나만 메우는지, 날짜가 다르거나 종가가 있으면 손대지 않는지.
"""
import math
import pandas as pd
import utils

def fake(close_last, meta_day):
    idx = pd.DatetimeIndex(['2026-10-20', '2026-10-21']).tz_localize('America/New_York')
    h = pd.DataFrame({'Open': [226.0, math.nan], 'High': [243.0, math.nan], 'Low': [225.0, math.nan], 'Close': [242.08, close_last], 'Volume': [9e6, 8e6]}, index=idx)
    meta = {'regularMarketPrice': 245.81, 'regularMarketDayHigh': 247.0, 'regularMarketDayLow': 240.0, 'regularMarketVolume': 8.1e6,
            'regularMarketTime': pd.Timestamp(meta_day + ' 16:00:01').tz_localize('America/New_York')}
    class T:
        def __init__(self, t): self.history_metadata = meta
        def history(self, **kw): return h.copy()
    return T

def run(close_last, meta_day):
    utils.yf.Ticker = fake(close_last, meta_day)
    return utils.history_filled('MRNA')

h = run(math.nan, '2026-10-21')
assert h['Close'].iloc[-1] == 245.81 and h['High'].iloc[-1] == 247.0 and h['Low'].iloc[-1] == 240.0, h.tail(1)
assert h['Close'].iloc[-2] == 242.08 and h.index.tz is None
assert run(math.nan, '2026-10-20')['Close'].isna().iloc[-1], '메타 날짜가 다르면 메우지 않는다'
assert run(244.0, '2026-10-21')['Close'].iloc[-1] == 244.0, '종가가 있으면 그대로'
print('✅ 마지막 봉 메우기 3건 통과')
