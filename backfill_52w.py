"""
52주 신고가(New_High_52W) / 52주 신저가(New_Low_52W) 히스토리 백필 스크립트.

static/history/result_YYYY-MM-DD.json 스냅샷에는 2026-08-17 이전까지
New_High_52W 필드가 없고, New_Low_52W 는 전 구간에 없습니다.
이 스크립트는 yfinance 로 일봉 OHLC 를 내려받아 각 스냅샷 날짜 기준
"직전 52주 구간" 을 다시 계산해 필드를 채워 넣습니다.

판정 기준은 utils.py 의 실시간 계산과 동일합니다.
  New_High_52W : 해당일 고가 >= 직전 52주 최고가  -> 'Y'
  New_Low_52W  : 해당일 저가 <= 직전 52주 최저가  -> 'Y'
  Low_52W_Pct  : (해당일 종가 / 직전 52주 최저가) * 100

사용법:
    python backfill_52w.py --since 2026-07-01
    python backfill_52w.py --since 2026-07-01 --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from utils import sanitize_ticker_for_yf

HISTORY_DIR = "static/history"
RESULT_FILE = "static/result.json"
CACHE_FILE = "backfill_52w_cache.parquet"

# 52주 = 365 캘린더일
WINDOW_DAYS = 365
BATCH_SIZE = 20


def collect_targets(since):
    """백필 대상 스냅샷 파일 목록과 전체 티커 집합을 수집."""
    files = []
    for name in sorted(os.listdir(HISTORY_DIR)):
        if not (name.startswith("result_") and name.endswith(".json")):
            continue
        date_str = name[len("result_"):-len(".json")]
        if date_str >= since:
            files.append((date_str, os.path.join(HISTORY_DIR, name)))

    tickers = set()
    for _, path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for row in data.get("data", []):
            if row.get("Ticker"):
                tickers.add(row["Ticker"])
    return files, sorted(tickers)


def download_ohlc(tickers, start, end):
    """티커별 일봉 High/Low/Close 를 받아 {ticker: DataFrame} 으로 반환."""
    frames = {}
    failed = []
    total = len(tickers)

    for i in range(0, total, BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        yf_map = {sanitize_ticker_for_yf(t): t for t in batch}
        symbols = list(yf_map.keys())

        try:
            raw = yf.download(
                symbols,
                start=start,
                end=end,
                progress=False,
                group_by="ticker",
                # utils.py 의 yf.download 는 auto_adjust 를 지정하지 않아 기본값(True)을
                # 쓰므로, 배당·분할 조정된 가격으로 52주 고저를 계산합니다.
                # 백필도 반드시 같은 기준이어야 실시간 값과 일치합니다.
                auto_adjust=True,
                threads=True,
            )
        except Exception as exc:
            print(f"  [batch {i}] 다운로드 실패: {exc}")
            failed.extend(batch)
            continue

        for sym, orig in yf_map.items():
            try:
                if len(symbols) == 1:
                    df = raw
                else:
                    if sym not in raw.columns.get_level_values(0):
                        failed.append(orig)
                        continue
                    df = raw[sym]

                df = df[["High", "Low", "Close"]].dropna(how="all")
                if df.empty:
                    failed.append(orig)
                    continue
                frames[orig] = df
            except Exception:
                failed.append(orig)

        done = min(i + BATCH_SIZE, total)
        print(f"  진행 {done}/{total} (수집 {len(frames)}, 실패 {len(failed)})")
        time.sleep(0.4)

    return frames, failed


def compute_flags(df, as_of):
    """as_of 이하 마지막 거래일 기준 52주 신고가/신저가 판정."""
    window = df.loc[:as_of]
    if window.empty:
        return None

    last_day = window.index[-1]
    # 스냅샷 날짜보다 5일 이상 오래된 데이터면 신뢰하지 않음 (상장폐지/거래정지 등)
    if (pd.Timestamp(as_of) - last_day).days > 5:
        return None

    cutoff = last_day - timedelta(days=WINDOW_DAYS)
    window = window.loc[window.index > cutoff]
    if window.empty:
        return None

    high_52w = window["High"].max()
    low_52w = window["Low"].min()
    day_high = window["High"].iloc[-1]
    day_low = window["Low"].iloc[-1]
    day_close = window["Close"].iloc[-1]

    if pd.isna(high_52w) or pd.isna(low_52w):
        return None

    result = {
        "New_High_52W": "Y" if pd.notna(day_high) and day_high >= high_52w else "N",
        "New_Low_52W": "Y" if pd.notna(day_low) and day_low <= low_52w else "N",
    }
    if low_52w > 0 and pd.notna(day_close):
        result["Low_52W_Pct"] = round(float(day_close / low_52w) * 100, 2)
    else:
        result["Low_52W_Pct"] = 0.0
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-07-01", help="백필 시작일 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 통계만 출력")
    parser.add_argument("--no-cache", action="store_true", help="가격 캐시를 무시하고 새로 받음")
    args = parser.parse_args()

    files, tickers = collect_targets(args.since)
    if not files:
        print(f"{args.since} 이후 스냅샷이 없습니다.")
        return 1

    print(f"대상 스냅샷 {len(files)}개 ({files[0][0]} ~ {files[-1][0]}), 티커 {len(tickers)}개")

    # 첫 스냅샷보다 52주 앞선 시점부터 받아야 윈도우가 완성됨
    start = (datetime.strptime(files[0][0], "%Y-%m-%d")
             - timedelta(days=WINDOW_DAYS + 10)).strftime("%Y-%m-%d")
    end = (datetime.strptime(files[-1][0], "%Y-%m-%d")
           + timedelta(days=2)).strftime("%Y-%m-%d")

    frames = None
    if os.path.exists(CACHE_FILE) and not args.no_cache:
        try:
            cached = pd.read_parquet(CACHE_FILE)
            frames = {t: g.drop(columns="Ticker") for t, g in cached.groupby("Ticker")}
            print(f"캐시 사용: {len(frames)}개 티커 ({CACHE_FILE})")
        except Exception as exc:
            print(f"캐시 로드 실패, 새로 받습니다: {exc}")
            frames = None

    if frames is None:
        print(f"가격 다운로드: {start} ~ {end}")
        frames, failed = download_ohlc(tickers, start, end)
        print(f"다운로드 완료: 성공 {len(frames)}, 실패 {len(failed)}")
        if failed:
            print(f"  실패 예시: {failed[:15]}")
        if frames:
            combined = pd.concat(
                [df.assign(Ticker=t) for t, df in frames.items()]
            )
            combined.to_parquet(CACHE_FILE)
            print(f"캐시 저장: {CACHE_FILE}")

    if not frames:
        print("가격 데이터를 확보하지 못했습니다.")
        return 1

    targets = list(files)
    if os.path.exists(RESULT_FILE):
        targets.append(("current", RESULT_FILE))

    grand_high = grand_low = grand_miss = grand_rows = 0

    for date_str, path in targets:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if date_str == "current":
            as_of = pd.Timestamp(data.get("last_updated", "").split()[0])
        else:
            as_of = pd.Timestamp(date_str)

        n_high = n_low = n_miss = n_kept = 0
        rows = data.get("data", [])

        for row in rows:
            ticker = row.get("Ticker")
            df = frames.get(ticker)
            flags = compute_flags(df, as_of) if df is not None else None

            # 실시간 파이프라인이 그날 직접 계산해 둔 New_High_52W 는 그대로 둡니다.
            # yfinance 는 스냅샷 이후 발생한 배당·분할까지 소급 반영해 과거 가격을
            # 다시 조정하므로, 지금 다시 계산한 값은 그날의 원본과 미세하게 어긋날
            # 수 있습니다. 원본이 있으면 원본이 더 정확합니다.
            has_original_high = row.get("New_High_52W") in ("Y", "N")

            if flags is None:
                n_miss += 1
                row.setdefault("New_High_52W", "N")
                row.setdefault("New_Low_52W", "N")
                row.setdefault("Low_52W_Pct", 0.0)
                continue

            if has_original_high:
                n_kept += 1
            else:
                row["New_High_52W"] = flags["New_High_52W"]

            row["New_Low_52W"] = flags["New_Low_52W"]
            row["Low_52W_Pct"] = flags["Low_52W_Pct"]
            n_high += row["New_High_52W"] == "Y"
            n_low += flags["New_Low_52W"] == "Y"

        grand_high += n_high
        grand_low += n_low
        grand_miss += n_miss
        grand_rows += len(rows)

        kept_note = f"  원본유지 {n_kept}" if n_kept else ""
        print(f"  {date_str}: {len(rows)}행  신고가 {n_high}  신저가 {n_low}  데이터없음 {n_miss}{kept_note}")

        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print(f"총 {grand_rows}행 처리 · 신고가 {grand_high} · 신저가 {grand_low} · 데이터없음 {grand_miss}")
    if args.dry_run:
        print("(dry-run 이므로 파일은 변경되지 않았습니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
