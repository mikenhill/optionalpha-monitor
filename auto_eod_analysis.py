"""
Auto EOD Analysis Scheduler
============================
Runs after market close (4:00 PM ET) to generate EOD analysis for the current day.
The analysis is saved to results/eod_analysis/YYYY-MM-DD.json.

Usage:
  python auto_eod_analysis.py
  # Runs continuously, checking every minute for market close
"""
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gex_viewer import generate_eod_analysis, SPX_DF

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "results" / "eod_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ET = ZoneInfo("America/New_York")
MARKET_CLOSE_HOUR = 16  # 4:00 PM ET
MARKET_CLOSE_MINUTE = 0


def wait_for_market_close():
    """Wait until after market close (4:00 PM ET)."""
    print("Waiting for market close (4:00 PM ET)...")
    while True:
        now = datetime.now(ET)
        if now.hour > MARKET_CLOSE_HOUR or (now.hour == MARKET_CLOSE_HOUR and now.minute >= MARKET_CLOSE_MINUTE):
            print(f"Market close reached at {now.strftime('%H:%M:%S ET')}")
            return now.strftime("%Y-%m-%d")
        time.sleep(60)  # Check every minute


def run_analysis(date_iso: str):
    """Generate and save EOD analysis for the date."""
    print(f"Generating EOD analysis for {date_iso}...")
    analysis = generate_eod_analysis(date_iso)
    
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return False
    
    # Save to file
    output_file = OUTPUT_DIR / f"{date_iso}.json"
    output_file.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"Saved: {output_file}")
    
    # Also save as markdown for easy reading
    md_file = OUTPUT_DIR / f"{date_iso}.md"
    md_content = f"""# EOD Analysis: {date_iso}

## Thesis (from 10:00 GEX)
{analysis['thesis']['thesis']}

## Actuals (OHLC)
- Open: {analysis['actuals']['open']:.2f}
- High: {analysis['actuals']['high']:.2f}
- Low: {analysis['actuals']['low']:.2f}
- Close: {analysis['actuals']['close']:.2f}

## Verdict
{analysis['verdict']}
"""
    md_file.write_text(md_content, encoding="utf-8")
    print(f"Saved: {md_file}")
    
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Specific date to analyze (YYYY-MM-DD). If not provided, waits for market close.")
    args = parser.parse_args()
    
    if args.date:
        date_iso = args.date
    else:
        date_iso = wait_for_market_close()
    
    success = run_analysis(date_iso)
    if success:
        print("EOD analysis completed successfully.")
    else:
        print("EOD analysis failed.")
