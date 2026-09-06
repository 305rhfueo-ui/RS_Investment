"""
발행 가드·NaN 가드 회귀 테스트 — 배치를 실제로 돌리지 않는다.
    python test_publish_guard.py

1. utils._finite / calculate_percentile_rank: NaN 이 섞여도 순위가 깨지지 않는다
2. assess_quality: 결측 행 비율 계산
3. publish: 결측률 초과 → result.json 은 전날 데이터 유지 + degraded, history 미생성
           정상 → result.json 갱신 + history 생성
"""
import json
import math
import os
import shutil
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import utils  # noqa: E402
import fetch_and_save as fas  # noqa: E402

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


print("\n[1] NaN 가드")
vals = [0.5, float('nan'), 0.9, None, 0.1, float('inf')]
ok("_finite 는 NaN/None/Inf 를 거른다", [utils._finite(v) for v in vals] == [True, False, True, False, True, False])
ok("최고값의 순위가 top 33.33% (3개 중 1등)", utils.calculate_percentile_rank(0.9, vals) == round(1 / 3 * 100, 2))
ok("최저값의 순위가 100%", utils.calculate_percentile_rank(0.1, vals) == 100.0)
ok("NaN 값 자체의 순위는 None", utils.calculate_percentile_rank(float('nan'), vals) is None)

print("\n[2] assess_quality")
rows = [{"Ticker": f"T{i}", "RS_6mo": 0.1 * i, "200DIV": 1.0, "50DIV": 1.0, "api_called": i % 3 == 0} for i in range(10)]
blank = [{"Ticker": f"B{i}", "RS_6mo": None, "200DIV": None, "50DIV": None, "Above_150_SMA": "X"} for i in range(6)]
q_ok = fas.assess_quality(rows, 12.3)
q_bad = fas.assess_quality(rows + blank, 12.3)
ok("정상 데이터 null_rate 0", q_ok["null_rate"] == 0.0 and q_ok["api_called_count"] == 4)
ok("결측 6/16 → null_rate 0.375", q_bad["blank_rows"] == 6 and abs(q_bad["null_rate"] - 0.375) < 1e-9)

print("\n[3] publish 가드 (임시 디렉터리)")
tmp = tempfile.mkdtemp()
try:
    orig = (fas.OUTPUT_FILE, fas.HISTORY_DIR, fas.HISTORY_INDEX, fas.PARTIAL_FILE)
    fas.OUTPUT_FILE = os.path.join(tmp, "result.json")
    fas.HISTORY_DIR = os.path.join(tmp, "history")
    fas.HISTORY_INDEX = os.path.join(tmp, "history_index.json")
    fas.PARTIAL_FILE = os.path.join(tmp, "result_partial.json")

    prev = {"last_updated": "2026-09-03 23:00:00 UTC", "total_count": 10, "data": rows, "wrs_data": []}
    with open(fas.OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(prev, f)

    bad_out = {"last_updated": "2026-09-04 23:00:00 UTC", "total_count": 16, "data": rows + blank, "wrs_data": []}
    degraded = fas.publish(bad_out, q_bad)
    with open(fas.OUTPUT_FILE, encoding="utf-8") as f:
        cur = json.load(f)
    ok("결측률 초과 → degraded True", degraded is True)
    ok("result.json 의 data 는 전날 것 그대로", cur["last_updated"] == prev["last_updated"] and len(cur["data"]) == 10)
    ok("degraded 플래그·품질 메타가 붙는다", cur.get("degraded") is True and cur.get("data_quality", {}).get("blank_rows") == 6)
    ok("부분 수집본은 result_partial.json 에", os.path.exists(fas.PARTIAL_FILE))
    ok("history 는 만들지 않는다", not os.path.exists(fas.HISTORY_DIR) or not os.listdir(fas.HISTORY_DIR))

    good_out = {"last_updated": "2026-09-05 23:00:00 UTC", "total_count": 10, "data": rows, "wrs_data": []}
    degraded2 = fas.publish(good_out, q_ok)
    with open(fas.OUTPUT_FILE, encoding="utf-8") as f:
        cur2 = json.load(f)
    ok("정상 → degraded False, result.json 갱신", degraded2 is False and cur2["last_updated"] == good_out["last_updated"] and cur2.get("degraded") is False)
    ok("history 파일 생성", os.path.isdir(fas.HISTORY_DIR) and len(os.listdir(fas.HISTORY_DIR)) == 1)
    ok("history_index 갱신", os.path.exists(fas.HISTORY_INDEX))
    fas.OUTPUT_FILE, fas.HISTORY_DIR, fas.HISTORY_INDEX, fas.PARTIAL_FILE = orig
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'FAIL' if FAIL else 'OK'} 통과 {PASS} · 실패 {FAIL}")
sys.exit(1 if FAIL else 0)
