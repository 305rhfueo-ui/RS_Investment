"""
wrs_trend 회귀 테스트 — 히스토리 전체를 돌리지 않는다.
    python test_wrs_trend.py

1. final_wrs: index.html calculateWRS 와 같은 식 (시총 가중·중앙값·승률·Count/(Count+5)), 종목 1개 업종 제외, NaN RS = 0
2. parse_market_cap: T/B/M/K, N/A → 0
3. build_trend: 3개월 밖 날짜 제외, 없는 업종은 null
4. drop_spikes: 하루만 튄 날만 빼고 마지막 날(= 표)은 남긴다
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrs_trend as wt  # noqa: E402

PASS = 0
FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK  {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def row(ind, mc, rs6, sector="Tech"):
    return {"Sector": sector, "Industry": ind, "Market Cap": mc, "RS_6mo": rs6}


print("1. final_wrs")
rows = [row("A", "3B", 0.3), row("A", "1B", -0.1), row("A", "1B", float("nan")),
        row("Solo", "5B", 0.9), row("A", "N/A", 0.5), row("", "1B", 0.5)]
r = wt.final_wrs(rows)
# A: 종목 3개(N/A 시총 제외) · 가중 (3×0.3 + 1×-0.1 + 1×0)/5 = 0.16 · 중앙값 0 · 승률 1/3 · (1-1/3)
base = 0.16 * 0.4 + 0 * 0.4 + (1 / 3) * (2 / 3) * 0.2
ok("식이 사이트와 같다", abs(r["Tech|A"] - base * 3 / 8) < 1e-12, r)
ok("종목 1개 업종은 뺀다", "Tech|Solo" not in r)
ok("업종 이름 없는 행은 뺀다", all(not k.endswith("|") for k in r))

print("2. parse_market_cap")
ok("T/B/M/K", [wt.parse_market_cap(x) for x in ("1.5T", "2B", "3M", "4k")] == [1.5e12, 2e9, 3e6, 4e3])
ok("N/A·빈 값 → 0", wt.parse_market_cap("N/A") == 0 and wt.parse_market_cap(None) == 0)

print("3. build_trend")
with tempfile.TemporaryDirectory() as tmp:
    hist = os.path.join(tmp, "history")
    os.makedirs(hist)
    two = [row("A", "1B", 0.2), row("A", "1B", 0.4)]
    days = {"2026-07-01": two, "2026-11-06": two, "2026-11-07": two, "2026-11-05": [row("B", "1B", 0.1), row("B", "1B", 0.3)]}
    for d, rs in days.items():   # 2026-07-01 = 3개월 밖
        with open(os.path.join(hist, f"result_{d}.json"), "w") as f:
            json.dump({"data": rs}, f)
    out = os.path.join(tmp, "trend.json")
    wt.build_trend(hist, out)
    t = json.load(open(out))
    ok("3개월 밖 날짜만 빠진다(주말 파일도 점 하나)", t["dates"] == ["2026-11-05", "2026-11-06", "2026-11-07"], t["dates"])
    ok("그날 없는 업종은 null", t["groups"]["Tech|A"][0] is None and t["groups"]["Tech|B"][1] is None, t["groups"])

print("4. drop_spikes")
ds = ["d1", "d2", "d3", "d4", "d5"]
pd_ = [{"a": 0.2, "b": 0.3}, {"a": 0.21, "b": 0.31}, {"a": 0.0, "b": 0.05}, {"a": 0.22, "b": 0.3}, {"a": 0.1, "b": 0.2}]   # d5 = 보통 하락
gone = wt.drop_spikes(ds, pd_)
ok("하루만 튄 날(d3)만 빠지고 옆 날은 남는다", gone == ["d3"] and ds == ["d1", "d2", "d4", "d5"], (gone, ds))
ok("마지막 날은 그대로(= 표)", ds[-1] == "d5")

print(f"\n{PASS} 통과 · {FAIL} 실패")
sys.exit(1 if FAIL else 0)
