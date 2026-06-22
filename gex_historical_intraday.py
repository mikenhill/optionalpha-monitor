"""
GEX Historical Intraday Capture & Analysis
==========================================
Fetches market.histgex snapshots from OptionAlpha for past trading days at
30-minute intervals (09:30 – 15:30 ET) and builds a combined CSV for analysis.

Key discovery: the API is  market.histgex  (not market.gex)
  - ndate : int  YYYYMMDD
  - ntime : int  HHMM  (no leading zero — 09:30 = 930)
  - uprice is returned in every response, so no SPX CSV needed for alignment.

Usage
-----
  # Single date
  python gex_historical_intraday.py --dates 20260617

  # Multiple dates
  python gex_historical_intraday.py --dates 20260610 20260611 20260612

  # Date range
  python gex_historical_intraday.py --from 20260601 --to 20260617

  # Custom 30-min slots only (default is 930,1000,...,1530)
  python gex_historical_intraday.py --dates 20260617 --times 930 1000 1030

Session
-------
Run optionalpha_capture.py (or optionalpha_probe.py) ONCE before a batch to
refresh session.json. The cookies are valid for several hours.
"""

import argparse
import csv
import json
import time
from datetime import date, timedelta
from pathlib import Path
from time import time as _time

from optionalpha_client import call_optionalpha_api, SESSION_FILE

BASE_DIR   = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "results" / "histgex"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Default 30-min slots 09:30 – 15:30 ET (13 snapshots per day)
DEFAULT_TIMES = [930, 1000, 1030, 1100, 1130, 1200, 1230,
                 1300, 1330, 1400, 1430, 1500, 1530]

SLEEP_BETWEEN_REQUESTS = 2.0   # seconds — respect rate limits
SUMMARY_CSV = OUTPUT_DIR / "gex_intraday_summary.csv"

SUMMARY_FIELDS = [
    "date", "ntime", "uprice",
    "net_gex", "call_gex", "put_gex",
    "highest_abs_strike", "highest_abs_gex",
    "second_abs_strike", "second_abs_gex",
    "gex_flip_level",
    "positive_strikes", "negative_strikes",
    "total_abs_gex",
]


# ---------------------------------------------------------------------------
# RPC payload for market.histgex
# ---------------------------------------------------------------------------

def build_histgex_payload(symbol: str, ndate: int, ntime: int) -> list:
    tid = int(_time() * 1000)
    return [
        {
            "t": "rpc",
            "tid": f"{tid}-20001",
            "api": "market.histgex",
            "args": [{"symbol": symbol, "ndate": ndate, "ntime": ntime, "count": 40}],
        }
    ]


def fetch_histgex(symbol: str, ndate: int, ntime: int) -> dict | None:
    payload = build_histgex_payload(symbol, ndate, ntime)
    raw = call_optionalpha_api(payload)
    for item in raw:
        if item.get("api") == "market.histgex":
            return item.get("data")
    return None


# ---------------------------------------------------------------------------
# GEX summary from a histgex data response
# ---------------------------------------------------------------------------

def summarize_histgex(data: dict) -> dict:
    rows   = data.get("data") or []
    uprice = data.get("uprice", 0)
    ndate  = data.get("ndate")
    ntime  = data.get("ntime")

    if not rows:
        return {}

    # Aggregate across all strikes
    net_gex   = sum(r.get("net", 0) or 0 for r in rows)
    call_gex  = sum(r.get("cg",  0) or 0 for r in rows)
    put_gex   = sum(r.get("pg",  0) or 0 for r in rows)
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in rows)

    # Highest absolute GEX strike (by raw abs, proximity not needed for summary)
    valid = [r for r in rows if r.get("strike") is not None]
    sorted_abs = sorted(valid, key=lambda r: abs(r.get("abs", 0) or 0), reverse=True)
    top1 = sorted_abs[0] if sorted_abs else {}
    top2 = sorted_abs[1] if len(sorted_abs) > 1 else {}

    # GEX flip level: estimate the strike where cumulative net GEX crosses zero
    # Sort by strike, walk upward accumulating net GEX; flip = first zero crossing
    by_strike = sorted(valid, key=lambda r: r["strike"])
    cumulative = 0.0
    flip_level = None
    prev_strike = None
    for r in by_strike:
        prev = cumulative
        cumulative += r.get("net", 0) or 0
        if prev_strike is not None and prev * cumulative < 0:
            # Linear interpolation between prev_strike and current strike
            denom = abs(cumulative) + abs(prev)
            flip_level = round(
                prev_strike + (r["strike"] - prev_strike) * abs(prev) / denom, 1
            ) if denom else r["strike"]
            break
        prev_strike = r["strike"]

    positive_strikes = sum(1 for r in rows if (r.get("net") or 0) > 0)
    negative_strikes = sum(1 for r in rows if (r.get("net") or 0) < 0)

    # Format date string MM/DD/YYYY to match SPX CSV convention
    if ndate:
        ds = str(ndate)           # YYYYMMDD
        date_str = f"{ds[4:6]}/{ds[6:8]}/{ds[:4]}"
    else:
        date_str = ""

    return {
        "date":               date_str,
        "ntime":              ntime,
        "uprice":             uprice,
        "net_gex":            round(net_gex, 2),
        "call_gex":           round(call_gex, 2),
        "put_gex":            round(put_gex, 2),
        "highest_abs_strike": top1.get("strike"),
        "highest_abs_gex":    abs(top1.get("abs", 0) or 0),
        "second_abs_strike":  top2.get("strike"),
        "second_abs_gex":     abs(top2.get("abs", 0) or 0),
        "gex_flip_level":     flip_level,
        "positive_strikes":   positive_strikes,
        "negative_strikes":   negative_strikes,
        "total_abs_gex":      round(total_abs, 2),
    }


# ---------------------------------------------------------------------------
# Raw JSON save
# ---------------------------------------------------------------------------

def raw_json_path(ndate: int, ntime: int, symbol: str) -> Path:
    day_dir = OUTPUT_DIR / str(ndate)
    day_dir.mkdir(exist_ok=True)
    return day_dir / f"{ndate}_{ntime:04d}_{symbol}_histgex.json"


# ---------------------------------------------------------------------------
# CSV upsert
# ---------------------------------------------------------------------------

def upsert_summary_csv(row: dict):
    """Append or replace a row in the summary CSV keyed on (date, ntime)."""
    existing = []
    if SUMMARY_CSV.exists():
        with SUMMARY_CSV.open(newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))

    key = (row["date"], str(row["ntime"]))
    existing = [r for r in existing if (r["date"], r["ntime"]) != key]
    existing.append({k: row.get(k, "") for k in SUMMARY_FIELDS})
    existing.sort(key=lambda r: (r["date"], str(r["ntime"]).zfill(4)))

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(existing)


# ---------------------------------------------------------------------------
# Main capture loop
# ---------------------------------------------------------------------------

def capture_day(symbol: str, ndate: int, times: list[int], force: bool = False):
    print(f"\n--- {ndate} ---")
    summaries = []
    for ntime in times:
        raw_path = raw_json_path(ndate, ntime, symbol)

        if raw_path.exists() and not force:
            print(f"  {ntime:04d}  (cached) {raw_path.name}")
            data = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            print(f"  {ntime:04d}  fetching...", end=" ", flush=True)
            try:
                data = fetch_histgex(symbol, ndate, ntime)
            except Exception as e:
                print(f"ERROR: {e}")
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                continue
            if data is None:
                print("no data returned")
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                continue
            raw_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"saved  uprice={data.get('uprice')}  strikes={len(data.get('data') or [])}")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        summary = summarize_histgex(data)
        if summary:
            summaries.append(summary)
            upsert_summary_csv(summary)

    return summaries


def dates_in_range(from_date: str, to_date: str) -> list[int]:
    """Return list of YYYYMMDD ints for weekdays between from_date and to_date inclusive."""
    start = date.fromisoformat(from_date[:4] + "-" + from_date[4:6] + "-" + from_date[6:8])
    end   = date.fromisoformat(to_date[:4]   + "-" + to_date[4:6]   + "-" + to_date[6:8])
    result = []
    current = start
    while current <= end:
        if current.weekday() < 5:   # Mon–Fri only
            result.append(int(current.strftime("%Y%m%d")))
        current += timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OptionAlpha historical intraday GEX")
    parser.add_argument("--symbol",  default="SPX")
    parser.add_argument("--dates",   nargs="+", help="One or more YYYYMMDD dates")
    parser.add_argument("--from",    dest="from_date", help="Start date YYYYMMDD for range")
    parser.add_argument("--to",      dest="to_date",   help="End date YYYYMMDD for range")
    parser.add_argument("--times",   nargs="+", type=int, default=DEFAULT_TIMES,
                        help="Time slots as HHMM ints e.g. 930 1000 1030")
    parser.add_argument("--force",   action="store_true",
                        help="Re-fetch even if raw JSON already exists")
    args = parser.parse_args()

    if args.from_date and args.to_date:
        ndates = dates_in_range(args.from_date, args.to_date)
    elif args.dates:
        ndates = [int(d) for d in args.dates]
    else:
        parser.error("Provide --dates or --from/--to")

    all_summaries = []
    for ndate in ndates:
        summaries = capture_day(args.symbol, ndate, args.times, force=args.force)
        all_summaries.extend(summaries)

    print(f"\nDone.  {len(all_summaries)} snapshots processed.")
    print(f"Summary CSV : {SUMMARY_CSV}")
    print(f"Raw JSON    : {OUTPUT_DIR}/<YYYYMMDD>/")

    if all_summaries:
        import pandas as pd
        df = pd.DataFrame(all_summaries)
        print(f"\nSample output (first 10 rows):")
        print(df[["date", "ntime", "uprice", "net_gex", "gex_flip_level",
                  "highest_abs_strike", "total_abs_gex"]].head(10).to_string(index=False))
