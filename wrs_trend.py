"""
Sector/Industry WRS 그래프 팝업용 Final WRS 추이 파일(static/wrs_trend.json) 생성.

히스토리 스냅샷은 한 개가 2MB 가까이 되므로 3개월치(60여 개)를 브라우저가 받을 수 없습니다.
그래서 날짜마다 업종별 Final WRS 만 계산해 작은 파일 하나로 묶습니다.

계산은 index.html 의 calculateWRS() (Sector/Industry WRS 표) 와 같습니다.
    Final WRS = (WRS(6mo)×0.4 + 중앙값 RS(6mo)×0.4 + 승률×(1-1/Count)×0.2) × Count/(Count+5)
    종목 2개 이상인 업종만.
그래서 그래프의 마지막 점 = 표의 Final WRS 입니다.

토·일 날짜 파일은 건너뜁니다. 파일 날짜는 UTC 실행일 = 미국 거래일이라,
주말 파일은 금요일 종가를 다시 받은 것이기 때문입니다.
하루만 업종 전체가 튀었다 돌아온 수집 이상 날짜도 뺍니다(drop_spikes, 뺀 날은 "dropped").

출력 형식:
    {
      "last_updated": "...",
      "dates": ["2026-08-07", ..., "2026-11-06"],          # 오름차순
      "groups": {"Technology|Semiconductors": [0.31, null, ...], ...}   # dates 와 같은 길이
    }

단독 실행:
    python wrs_trend.py
파이프라인에서는 fetch_and_save.py 가 매일 호출합니다.
"""

import json
import math
import os
import re
import statistics
from datetime import date, datetime, timedelta, timezone

HISTORY_DIR = "static/history"
TREND_FILE = "static/wrs_trend.json"
DAYS = 92  # 최근 3개월(달력 기준)
SPIKE = 0.04  # 전체 업종 Final WRS 중앙값이 하루만 이만큼 튀었다 돌아오면 수집 이상으로 보고 뺀다

_NUM = re.compile(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")


def _js_float(s):
    """JS parseFloat 처럼 앞부분 숫자만 읽는다. 못 읽으면 None."""
    m = _NUM.match(s)
    return float(m.group(0)) if m else None


def parse_market_cap(mc):
    """index.html parseMarketCap 과 같다: "1.23T" · "45.6B" · "789M" · "12K"."""
    if not mc or not isinstance(mc, str):
        return 0
    val = _js_float(mc[:-1])
    if val is None:
        return 0
    return val * {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}.get(mc[-1].upper(), 1)


def _rs(v):
    """JS parseFloat(x) || 0 — 숫자가 아니거나 NaN 이면 0."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(f) else f


def final_wrs(rows):
    """한 스냅샷의 {"Sector|Industry": Final WRS} (종목 2개 이상 업종만)."""
    groups = {}
    for item in rows:
        sector, industry = item.get("Sector"), item.get("Industry")
        if not isinstance(sector, str) or sector in ("", "N/A"):
            continue
        if not isinstance(industry, str) or industry in ("", "N/A"):
            continue
        g = groups.setdefault(f"{sector}|{industry}", {"count": 0, "mc": 0.0, "w6": 0.0, "rs": [], "win": 0})
        mc = parse_market_cap(item.get("Market Cap"))
        if mc > 0:
            rs6 = _rs(item.get("RS_6mo"))
            g["count"] += 1
            g["mc"] += mc
            g["w6"] += mc * rs6
            g["rs"].append(rs6)
            if rs6 > 0:
                g["win"] += 1

    out = {}
    for key, g in groups.items():
        n = g["count"]
        if n <= 1:
            continue
        rs = sorted(g["rs"])
        mid = n // 2
        median = (rs[mid - 1] + rs[mid]) / 2 if n % 2 == 0 else rs[mid]
        wrs6 = g["w6"] / g["mc"] if g["mc"] > 0 else 0
        base = wrs6 * 0.4 + median * 0.4 + (g["win"] / n) * (1 - 1 / n) * 0.2
        out[key] = base * (n / (n + 5))
    return out


def drop_spikes(dates, per_day, spike=SPIKE):
    """수집 이상 날짜를 dates·per_day 에서 빼고 뺀 날짜 목록을 돌려준다.

    2026-08-17·09-17·10-22 스냅샷은 정규 시각이 아닌 재실행본이라 업종 전체가 하루만
    한꺼번에 꺼졌다가(종목 가격 중앙값까지 41→103 처럼 튐) 다음 날 돌아왔다.
    전체 업종 중앙값이 앞뒤 날과 같은 방향으로 spike 넘게 튄 날을 가장 큰 것부터 하나씩 뺀다
    (하나 빼고 다시 재야 그 옆 날이 덩달아 걸리지 않는다). 첫날·마지막 날(= 표)은 빼지 않는다.
    ponytail: 하루짜리 튐만 잡는다 — 이틀 이상 이어진 이상은 그대로 보이고, 마지막 날(오늘)이 깨지면
    그 전날이 반대로 튄 것처럼 보여 빠질 수 있다. 자주 생기면 스냅샷의 실행 시각으로 거르는 쪽이 낫다.
    """
    med = [statistics.median(day.values()) if day else 0.0 for day in per_day]
    dropped = []
    while True:
        worst, at = spike, None
        for i in range(1, len(med) - 1):
            a, b, c = med[i - 1], med[i], med[i + 1]
            s = b - (a + c) / 2
            if (b - a) * s > 0 and (b - c) * s > 0 and abs(s) > worst:
                worst, at = abs(s), i
        if at is None:
            return dropped
        dropped.append(dates.pop(at))
        per_day.pop(at)
        med.pop(at)


def build_trend(history_dir=HISTORY_DIR, trend_file=TREND_FILE, days=DAYS):
    """최근 days 일(평일 파일만)의 업종별 Final WRS 를 새로 씁니다."""
    if not os.path.isdir(history_dir):
        print(f"  ⚠️ 히스토리 폴더 없음: {history_dir}")
        return None

    dated = []
    for name in os.listdir(history_dir):
        if not (name.startswith("result_") and name.endswith(".json")):
            continue
        try:
            d = date.fromisoformat(name[len("result_"):-len(".json")])
        except ValueError:
            continue
        if d.weekday() < 5:
            dated.append((d, name))
    if not dated:
        return None
    dated.sort()
    since = dated[-1][0] - timedelta(days=days)

    dates, per_day = [], []
    for d, name in dated:
        if d < since:
            continue
        try:
            with open(os.path.join(history_dir, name), "r", encoding="utf-8") as f:
                rows = json.load(f).get("data", [])
        except Exception as exc:
            print(f"  ⚠️ 추이 건너뜀 {name}: {exc}")
            continue
        dates.append(d.isoformat())
        per_day.append(final_wrs(rows))

    dropped = drop_spikes(dates, per_day)
    keys = sorted({k for day in per_day for k in day})
    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "dates": dates,
        "dropped": dropped,
        "groups": {k: [round(day[k], 4) if k in day else None for day in per_day] for k in keys},
    }
    os.makedirs(os.path.dirname(trend_file), exist_ok=True)
    with open(trend_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  Final WRS 추이 저장: {trend_file} ({len(dates)}일 · {len(keys)}개 업종)")
    return payload


if __name__ == "__main__":
    build_trend()
