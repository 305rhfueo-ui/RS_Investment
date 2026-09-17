"""
헤더 패널과 Market 팝업이 쓰는 데이터 생성.

1) static/sentiment.json
   AAII Investor Sentiment Survey(주간)의 Bullish / Neutral / Bearish 와
   Bull-Bear 스프레드. https://www.aaii.com/sentimentsurvey/sent_results 를
   파싱합니다. 표에는 연도가 없고 "Sep 9" 처럼만 적혀 있어서,
   최신 행부터 거꾸로 내려가며 날짜가 역전되는 지점에서 연도를 하나씩 낮춥니다.

2) static/qqq_chart.json
   QQQ 일봉(OHLC)과 10일·20일 이동평균. Market 팝업의 1번·2번 차트에 씁니다.
   이동평균이 첫날부터 채워지도록 표시 구간보다 넉넉히 받아서 계산한 뒤 잘라냅니다.

3) static/vix.json
   ^VIX 일별 종가(Yahoo Finance history 페이지의 Close 와 같은 값)와 같은 날짜의
   QQQ·SPY 종가 1년치. 헤더 패널에는 선택한 날짜의 VIX 종가를, Market 팝업 4번
   차트에는 1년 전체(VIX + QQQ + SPY)를 씁니다.

세 파일 모두 오래된 날짜 -> 최신 날짜 순서(오름차순)입니다. 차트에 그대로 넣기
위해서이며, 최신값은 배열의 마지막 원소입니다.

단독 실행:
    python market_panel_data.py
파이프라인에서는 fetch_and_save.py 가 매일 호출합니다.
"""

import json
import os
import re
from datetime import datetime, timedelta

SENTIMENT_URL = "https://www.aaii.com/sentimentsurvey/sent_results"
SENTIMENT_FILE = "static/sentiment.json"
QQQ_FILE = "static/qqq_chart.json"
VIX_FILE = "static/vix.json"

# 패널·차트가 다루는 시작일. 히스토리 백필 시작일과 맞춥니다.
START_DATE = "2026-07-01"

# 표시 구간(거래일). 팝업 1번은 3개월, 2번은 2개월을 봅니다.
QQQ_DISPLAY_DAYS = 70

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _strip_tags(html):
    return re.sub(r"<[^>]+>", "", html).strip()


def parse_sentiment_table(html, today=None):
    """AAII 결과 페이지에서 [{date, bullish, neutral, bearish, spread}] 추출 (오름차순)."""
    tables = re.findall(r"<table.*?</table>", html, re.S)
    if not tables:
        raise ValueError("표를 찾지 못했습니다")

    rows = re.findall(r"<tr.*?</tr>", tables[0], re.S)
    raw = []
    for r in rows:
        cells = [_strip_tags(c) for c in re.findall(r"<t[hd].*?</t[hd]>", r, re.S)]
        if len(cells) != 4:
            continue
        m = re.match(r"([A-Za-z]{3})\w*\s+(\d{1,2})", cells[0])
        if not m:
            continue  # 헤더 행
        pct = []
        for c in cells[1:]:
            mm = re.match(r"(-?\d+(?:\.\d+)?)\s*%?$", c)
            if not mm:
                break
            pct.append(float(mm.group(1)))
        if len(pct) != 3:
            continue
        raw.append((MONTHS.get(m.group(1)), int(m.group(2)), pct))

    if not raw:
        raise ValueError("데이터 행을 찾지 못했습니다")

    # 표는 최신순. 위에서 아래로 내려가며 날짜가 거꾸로 커지면 연도를 하나 낮춥니다.
    today = today or datetime.now()
    year = today.year
    out = []
    prev = None
    for month, day, pct in raw:
        if month is None:
            continue
        d = datetime(year, month, day)
        # 첫 행이 미래로 잡히면(연초에 전년도 표를 볼 때) 한 해 내립니다.
        if prev is None and d > today + timedelta(days=7):
            year -= 1
            d = datetime(year, month, day)
        while prev is not None and d >= prev:
            year -= 1
            d = datetime(year, month, day)
        prev = d
        bullish, neutral, bearish = pct
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "bullish": round(bullish, 1),
            "neutral": round(neutral, 1),
            "bearish": round(bearish, 1),
            "spread": round(bullish - bearish, 1),
        })

    out.sort(key=lambda e: e["date"])
    return out


def build_sentiment(url=SENTIMENT_URL, out_file=SENTIMENT_FILE, start=START_DATE):
    """AAII 설문 결과를 받아 sentiment.json 으로 저장."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    entries = [e for e in parse_sentiment_table(html) if e["date"] >= start]
    if not entries:
        raise ValueError(f"{start} 이후 데이터가 없습니다")

    payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": url,
        "count": len(entries),
        "data": entries,
    }
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  → AAII 센티먼트 갱신: {len(entries)}주 "
          f"({entries[0]['date']} ~ {entries[-1]['date']})")
    return payload


def build_qqq_chart(out_file=QQQ_FILE, display_days=QQQ_DISPLAY_DAYS):
    """QQQ 일봉과 10/20일 이동평균을 qqq_chart.json 으로 저장."""
    import pandas as pd
    import yfinance as yf

    # 이동평균 워밍업까지 감안해 6개월을 받고 표시 구간만 잘라냅니다.
    df = yf.download("QQQ", period="6mo", progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError("QQQ 데이터를 받지 못했습니다")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close"]].dropna()
    df["ma10"] = df["Close"].rolling(10).mean()
    df["ma20"] = df["Close"].rolling(20).mean()

    tail = df.iloc[-display_days:]
    data = []
    for idx, row in tail.iterrows():
        data.append({
            "date": idx.strftime("%Y-%m-%d"),
            "o": round(float(row["Open"]), 2),
            "h": round(float(row["High"]), 2),
            "l": round(float(row["Low"]), 2),
            "c": round(float(row["Close"]), 2),
            "ma10": None if pd.isna(row["ma10"]) else round(float(row["ma10"]), 2),
            "ma20": None if pd.isna(row["ma20"]) else round(float(row["ma20"]), 2),
        })

    payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "count": len(data),
        "data": data,
    }
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  → QQQ 차트 데이터 갱신: {len(data)}일 "
          f"({data[0]['date']} ~ {data[-1]['date']})")
    return payload


def build_vix(out_file=VIX_FILE):
    """^VIX 일별 종가 1년치 + 같은 날짜의 QQQ·SPY 종가를 vix.json 으로 저장.

    행: {date, close(VIX), qqq, spy}. QQQ·SPY 는 그날 값이 없으면 null.
    """
    import pandas as pd
    import yfinance as yf

    df = yf.download(["^VIX", "QQQ", "SPY"], period="1y", progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise ValueError("VIX 데이터를 받지 못했습니다")
    close = df["Close"]

    def num(v):
        return None if pd.isna(v) else round(float(v), 2)

    # 장 마감 직후 당일 봉 종가가 null 로 오는 경우가 있어 VIX 가 비어 있는 행은 뺍니다.
    data = [{"date": idx.strftime("%Y-%m-%d"), "close": num(row["^VIX"]),
             "qqq": num(row["QQQ"]), "spy": num(row["SPY"])}
            for idx, row in close.iterrows() if not pd.isna(row["^VIX"])]
    if not data:
        raise ValueError("VIX 종가가 비어 있습니다")

    payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": "https://finance.yahoo.com/quote/%5EVIX/history/",
        "count": len(data),
        "data": data,
    }
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  → VIX 갱신: {len(data)}일 ({data[0]['date']} ~ {data[-1]['date']}, "
          f"최근 종가 {data[-1]['close']})")
    return payload


def build_all(sentiment_file=SENTIMENT_FILE, qqq_file=QQQ_FILE, vix_file=VIX_FILE):
    """하나가 실패해도 나머지는 갱신되도록 각각 감쌉니다."""
    ok = True
    try:
        build_sentiment(out_file=sentiment_file)
    except Exception as exc:
        print(f"  ⚠️ AAII 센티먼트 갱신 실패(기존 파일 유지): {exc}")
        ok = False
    try:
        build_qqq_chart(out_file=qqq_file)
    except Exception as exc:
        print(f"  ⚠️ QQQ 차트 데이터 갱신 실패(기존 파일 유지): {exc}")
        ok = False
    try:
        build_vix(out_file=vix_file)
    except Exception as exc:
        print(f"  ⚠️ VIX 갱신 실패(기존 파일 유지): {exc}")
        ok = False
    return ok


if __name__ == "__main__":
    build_all()
