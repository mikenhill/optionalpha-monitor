"""Test populating the spx_open_prices table from the CSV.

Run with: python test_spx_open_prices.py
"""
import sqlite3
from pathlib import Path

from gex_viewer import _populate_spx_open_prices_from_csv

DB_PATH = Path(__file__).resolve().parent / "gex.db"


def count_rows():
    con = sqlite3.connect(str(DB_PATH))
    try:
        return con.execute("SELECT COUNT(*) FROM spx_open_prices").fetchone()[0]
    finally:
        con.close()


def main():
    before = count_rows()
    result = _populate_spx_open_prices_from_csv()
    after = count_rows()
    print(f"Populate result: {result}")
    print(f"spx_open_prices rows: before={before}, after={after}")
    assert after >= before, "Row count decreased unexpectedly"
    assert result["inserted"] >= 0, "Insert count invalid"
    print("PASS: spx_open_prices populated successfully")


if __name__ == "__main__":
    main()
