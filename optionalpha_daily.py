import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from market_data import backfill_ohlc, fetch_spx_ohlc
from optionalpha_client import fetch_market_data
from process_gex_window import summarize_file, write_summary_files

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "results"
DAILY_SUMMARY_FILE = OUTPUT_DIR / "daily_gex_summary.csv"


def get_uk_time():
    try:
        return ZoneInfo("Europe/London")
    except ZoneInfoNotFoundError:
        return None


def default_xid(symbol, run_date):
    return f"{symbol}_{run_date.strftime('%Y%m%d')}"


def delete_existing_day_files(symbol, date_str):
    for f in OUTPUT_DIR.glob(f"{date_str}_*_{symbol}_*.json"):
        f.unlink()
        print(f"Deleted: {f}")


def run(symbol):
    uk_time = get_uk_time()
    now = datetime.now(uk_time).astimezone() if uk_time else datetime.now().astimezone()
    xid = default_xid(symbol, now)
    date_str = now.strftime('%Y%m%d')

    OUTPUT_DIR.mkdir(exist_ok=True)
    delete_existing_day_files(symbol, date_str)

    data = fetch_market_data(symbol=symbol, xid=xid)

    output_file = OUTPUT_DIR / f"{now.strftime('%Y%m%d_%H%M%S')}_{symbol}_{xid}.json"
    output = {
        "captured_at": now.isoformat(),
        "symbol": symbol,
        "xid": xid,
        "data": data,
    }
    output_file.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Saved: {output_file}")
    for item in data:
        api = item.get("api")
        keys = sorted((item.get("data") or {}).keys())
        print(f"{api}: {', '.join(keys)}")

    summary = summarize_file(output_file)
    summary_file, csv_file = write_summary_files(
        output_file,
        summary,
        include_csv=True,
        append_path=DAILY_SUMMARY_FILE,
    )
    print(f"Sentiment: {summary['sentiment']}")
    print(f"GEX ratio: {summary['gex_ratio']}")
    print(f"Highest absolute GEX strike: {summary['highest_absolute_gex_strike']}")
    print(f"Key strike balance: {summary['key_strike_balance']}%")
    print(f"Weighted mean put strike (GEX): {summary['weighted_mean_put_strike_gex']}")
    print(f"Weighted mean put strike (OI):  {summary['weighted_mean_put_strike_oi']}")
    print(f"Weighted mean put strike (Vol): {summary['weighted_mean_put_strike_vol']}")
    print(f"Weighted mean call strike (GEX): {summary['weighted_mean_call_strike_gex']}")
    print(f"Weighted mean call strike (OI):  {summary['weighted_mean_call_strike_oi']}")
    print(f"Weighted mean call strike (Vol): {summary['weighted_mean_call_strike_vol']}")
    print(f"Call/put GEX strike spread: {summary['call_put_gex_strike_spread']}")
    print(f"Call/put OI strike spread:  {summary['call_put_oi_strike_spread']}")
    print(f"Call/put Vol strike spread: {summary['call_put_vol_strike_spread']}")
    print(f"Saved: {summary_file}")
    print(f"Saved: {csv_file}")
    print(f"Upserted: {DAILY_SUMMARY_FILE} (date={summary['date'][:10]})")

    # Backfill OHLC for any rows missing it (catches today and any historical gaps)
    import csv as _csv
    today_str = now.date().isoformat()
    if DAILY_SUMMARY_FILE.exists():
        with DAILY_SUMMARY_FILE.open("r", newline="", encoding="utf-8") as _f:
            missing_dates = [
                row["date"][:10]
                for row in _csv.DictReader(_f)
                if not row.get("ohlc_close") and row.get("date", "")[:10] < today_str
            ]
        for date_str in missing_dates:
            from datetime import date as _date
            d = _date.fromisoformat(date_str)
            ohlc = fetch_spx_ohlc(d)
            if ohlc:
                ok = backfill_ohlc(DAILY_SUMMARY_FILE, date_str, ohlc)
                print(f"Backfilled OHLC for {date_str}: {ohlc}" if ok else f"No row to backfill for {date_str}")
            else:
                print(f"No SPX OHLC data available for {date_str}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="SPX")
    args = parser.parse_args()
    run(args.symbol)


if __name__ == "__main__":
    main()
