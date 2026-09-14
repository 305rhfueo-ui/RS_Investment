"""
백필 결과 검증.

2026-08-17 이후 스냅샷에는 실시간 파이프라인(utils.py)이 직접 계산한
New_High_52W 원본값이 들어 있습니다. 백필 로직이 그 값을 얼마나 재현하는지
비교해서, 신저가 값도 신뢰할 수 있는지 확인합니다.

사용법:
    python verify_52w_backfill.py                 # 백필 전 원본과 캐시 비교
    python verify_52w_backfill.py --post          # 백필 후 파일 자체를 검사
"""

import argparse
import glob
import json
import os
from collections import Counter

import pandas as pd

import backfill_52w as B

BASELINE_SINCE = "result_2026-08-17"


def load_cache():
    cached = pd.read_parquet(B.CACHE_FILE)
    return {t: g.drop(columns="Ticker") for t, g in cached.groupby("Ticker")}


def compare_against_original(frames):
    """원본 New_High_52W 가 살아 있는 스냅샷과 백필 계산값을 대조."""
    files = sorted(glob.glob(os.path.join(B.HISTORY_DIR, "result_*.json")))
    files = [f for f in files if os.path.basename(f)[:-5] >= BASELINE_SINCE]

    agree = disagree = skipped = 0
    examples = []

    for path in files:
        date_str = os.path.basename(path)[len("result_"):-len(".json")]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for row in data.get("data", []):
            original = row.get("New_High_52W")
            if original not in ("Y", "N"):
                continue
            df = frames.get(row.get("Ticker"))
            flags = B.compute_flags(df, pd.Timestamp(date_str)) if df is not None else None
            if flags is None:
                skipped += 1
                continue
            if flags["New_High_52W"] == original:
                agree += 1
            else:
                disagree += 1
                if len(examples) < 20:
                    examples.append(
                        f"{date_str} {row['Ticker']}: 원본={original} 백필={flags['New_High_52W']}"
                    )

    total = agree + disagree
    print("=== 원본 New_High_52W 대조 (2026-08-17 이후) ===")
    print(f"비교 가능 {total}건 · 일치 {agree} · 불일치 {disagree} · 데이터없음 {skipped}")
    if total:
        print(f"일치율 {agree / total * 100:.2f}%")
    for line in examples:
        print("  ", line)
    return disagree


def inspect_files(since):
    """백필 후 각 스냅샷의 필드 충족도와 Y 분포를 출력."""
    files = sorted(glob.glob(os.path.join(B.HISTORY_DIR, "result_*.json")))
    files = [f for f in files if os.path.basename(f)[len("result_"):-len(".json")] >= since]

    print(f"=== 백필 후 검사 ({len(files)}개 스냅샷) ===")
    bad = 0
    for path in files:
        date_str = os.path.basename(path)[len("result_"):-len(".json")]
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f).get("data", [])

        missing_h = sum(1 for r in rows if "New_High_52W" not in r)
        missing_l = sum(1 for r in rows if "New_Low_52W" not in r)
        vals = Counter(r.get("New_Low_52W") for r in rows)
        invalid = sum(v for k, v in vals.items() if k not in ("Y", "N"))
        highs = sum(1 for r in rows if r.get("New_High_52W") == "Y")
        lows = vals.get("Y", 0)

        flag = ""
        if missing_h or missing_l or invalid:
            flag = "  <== 문제"
            bad += 1
        print(f"  {date_str}: {len(rows)}행 신고가Y={highs:4d} 신저가Y={lows:4d} "
              f"누락(H/L)={missing_h}/{missing_l} 비정상={invalid}{flag}")

    print(f"\n문제 있는 스냅샷: {bad}개")
    return bad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true", help="백필 후 파일 검사 모드")
    parser.add_argument("--since", default="2026-07-01")
    args = parser.parse_args()

    if args.post:
        return 1 if inspect_files(args.since) else 0

    frames = load_cache()
    print(f"캐시 티커 {len(frames)}개\n")
    return 1 if compare_against_original(frames) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
