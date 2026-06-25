"""Test that the expected SQLite schema is in place.

Run with: python test_schema.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "gex.db"

EXPECTED_GEX_SNAPSHOTS_COLS = {
    "sentiment", "gex_ratio", "net_gex", "kcs", "dominance",
    "total_call_gex", "total_put_gex", "key_strike", "key_call_gex", "key_put_gex",
    "total_call_oi", "total_put_oi", "key_call_oi", "key_put_oi",
    "total_call_vol", "total_put_vol", "key_call_vol", "key_put_vol",
    "key2_strike", "key2_abs", "key2_call_vol", "key2_put_vol", "flip",
    "hmm_state", "hmm_label", "is_premarket", "source",
}


def main():
    assert DB_PATH.exists(), f"gex.db not found at {DB_PATH}"
    con = sqlite3.connect(str(DB_PATH))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(gex_snapshots)").fetchall()}
        missing = EXPECTED_GEX_SNAPSHOTS_COLS - cols
        assert not missing, f"gex_snapshots missing columns: {missing}"
        print(f"PASS: gex_snapshots has all {len(EXPECTED_GEX_SNAPSHOTS_COLS)} expected columns")

        spx_cols = {r[1] for r in con.execute("PRAGMA table_info(spx_open_prices)").fetchall()}
        assert "open_price" in spx_cols, "spx_open_prices missing open_price column"
        print("PASS: spx_open_prices table exists")

        legacy = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'"
        ).fetchone()
        assert legacy is None, "legacy 'snapshots' table still exists"
        print("PASS: legacy 'snapshots' table has been dropped")
    finally:
        con.close()


if __name__ == "__main__":
    main()
