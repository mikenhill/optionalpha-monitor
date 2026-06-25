"""Test backfilling flat summary columns into gex_snapshots.

Run with default small batch:  python test_backfill_summary.py
Run with custom limit:          python test_backfill_summary.py --limit 50
Backfill all remaining rows:    python test_backfill_summary.py --all
"""
import argparse
import sqlite3
from pathlib import Path

from gex_viewer import _ensure_gex_snapshots_summary_columns, _backfill_gex_snapshots_summary

DB_PATH = Path(__file__).resolve().parent / "gex.db"


def count_null_rows():
    con = sqlite3.connect(str(DB_PATH))
    try:
        return con.execute(
            "SELECT COUNT(*) FROM gex_snapshots WHERE symbol='SPX' AND net_gex IS NULL"
        ).fetchone()[0]
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Test backfill of flat summary columns")
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to backfill (default 10)")
    parser.add_argument("--all", action="store_true", help="Backfill all remaining rows")
    args = parser.parse_args()

    _ensure_gex_snapshots_summary_columns()
    before = count_null_rows()
    limit = None if args.all else args.limit
    result = _backfill_gex_snapshots_summary(limit=limit)
    after = count_null_rows()

    print(f"Backfill result: {result}")
    print(f"Rows with NULL net_gex: before={before}, after={after}")
    if before == 0:
        print("PASS: no rows need backfilling (already complete)")
    else:
        assert after < before, "Backfill did not reduce NULL rows"
        assert after <= before - result["updated"], "NULL row count mismatch"
        print("PASS: backfill reduced NULL rows")


if __name__ == "__main__":
    main()
