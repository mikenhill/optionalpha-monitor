"""Fetch market OHLC data from Yahoo Finance and backfill daily CSV."""
import csv
from datetime import timedelta
from pathlib import Path

import yfinance as yf


def fetch_spx_ohlc(trading_date):
    """Fetch SPX (^SPX) OHLC for a specific trading date.

    Returns dict with ohlc_open/high/low/close or None if no data.
    """
    try:
        ticker = yf.Ticker("^SPX")
        start = trading_date.strftime("%Y-%m-%d")
        end = (trading_date + timedelta(days=1)).strftime("%Y-%m-%d")
        hist = ticker.history(start=start, end=end)
        if hist.empty:
            return None
        row = hist.iloc[0]
        o = round(float(row["Open"]), 2)
        h = round(float(row["High"]), 2)
        l = round(float(row["Low"]), 2)
        c = round(float(row["Close"]), 2)
        return {
            "ohlc_open":  o if o != 0.0 else "",
            "ohlc_high":  h if h != 0.0 else "",
            "ohlc_low":   l if l != 0.0 else "",
            "ohlc_close": c if c != 0.0 else "",
        }
    except Exception as e:
        print(f"Warning: could not fetch SPX OHLC for {trading_date}: {e}")
        return None


def backfill_ohlc(csv_path, date_str, ohlc):
    """Update an existing row in the daily CSV with OHLC values.

    Returns True if a row was updated, False otherwise.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return False

    rows = []
    updated = False
    fieldnames = None

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            row_date = row.get("date", "")[:10]
            if row_date == date_str:
                for key in ("ohlc_open", "ohlc_high", "ohlc_low", "ohlc_close"):
                    if key in row:
                        row[key] = str(ohlc.get(key, ""))
                updated = True
            rows.append(row)

    if not updated:
        return False

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return True
