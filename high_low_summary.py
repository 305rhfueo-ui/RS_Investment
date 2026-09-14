"""
날짜별 52주 신고가/신저가 개수 요약 파일(static/high_low_summary.json) 생성.

히스토리 스냅샷은 한 개가 2MB 가까이 되므로 브라우저에서 날짜별 집계를
매번 계산할 수 없습니다. 대신 날짜당 숫자 세 개만 담은 작은 파일을 만들어
헤더 패널이 이 파일 하나만 받도록 합니다.

출력 형식:
    {
      "last_updated": "2026-09-14 00:06:50 UTC",
      "total_dates": 213,
      "dates": [ {"date": "2026-09-14", "total": 1412, "highs": 33, "lows": 22}, ... ]
    }
  dates 는 최신순입니다.

단독 실행:
    python high_low_summary.py
파이프라인에서는 fetch_and_save.py 가 매일 호출합니다.
"""

import json
import os
from datetime import datetime

HISTORY_DIR = "static/history"
SUMMARY_FILE = "static/high_low_summary.json"


def count_flags(rows):
    """한 스냅샷의 전체 종목수 / 신고가 Y / 신저가 Y 개수.

    2026-07-01 이전 스냅샷에는 신고가·신저가 필드 자체가 없습니다.
    그런 날짜를 0 으로 내보내면 '그날 신고가가 한 종목도 없었다'는
    뜻으로 오해되므로, filled=False 로 표시해 화면에서 '-' 로 구분합니다.
    """
    highs = lows = 0
    has_high = has_low = False
    for row in rows:
        if "New_High_52W" in row:
            has_high = True
            if row["New_High_52W"] == "Y":
                highs += 1
        if "New_Low_52W" in row:
            has_low = True
            if row["New_Low_52W"] == "Y":
                lows += 1

    filled = bool(rows) and has_high and has_low
    return {
        "total": len(rows),
        "highs": highs if filled else None,
        "lows": lows if filled else None,
        "filled": filled,
    }


def build_summary(history_dir=HISTORY_DIR, summary_file=SUMMARY_FILE):
    """히스토리 폴더 전체를 훑어 요약 파일을 새로 씁니다."""
    if not os.path.isdir(history_dir):
        print(f"  ⚠️ 히스토리 폴더 없음: {history_dir}")
        return None

    entries = []
    for name in sorted(os.listdir(history_dir)):
        if not (name.startswith("result_") and name.endswith(".json")):
            continue
        date_str = name[len("result_"):-len(".json")]
        path = os.path.join(history_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            print(f"  ⚠️ 요약 건너뜀 {name}: {exc}")
            continue

        entry = {"date": date_str}
        entry.update(count_flags(data.get("data", [])))
        entries.append(entry)

    entries.sort(key=lambda e: e["date"], reverse=True)

    payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_dates": len(entries),
        "dates": entries,
    }

    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  → 신고가/신저가 요약 갱신: {len(entries)}개 날짜 ({summary_file})")
    return payload


if __name__ == "__main__":
    result = build_summary()
    if result and result["dates"]:
        print()
        print("  최근 5일")
        for e in result["dates"][:5]:
            print(f"    {e['date']}  전체 {e['total']:4d}  신고가 {e['highs'] if e['filled'] else '-':>4}  신저가 {e['lows'] if e['filled'] else '-':>4}")
