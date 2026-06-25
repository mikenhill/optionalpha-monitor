"""
import_to_sqlite.py
====================
One-time migration: scan all histgex JSON files and load into gex.db.

Schema (single table — fast point lookups, no joins):

    gex_snapshots (ndate INTEGER, ntime INTEGER, symbol TEXT,
                   uprice REAL, data TEXT,
                   PRIMARY KEY (ndate, ntime, symbol))

  data = JSON blob of the strike rows list (same as file["data"]).

Safe to re-run — uses INSERT OR IGNORE so existing rows are not overwritten.
"""

import json
import sqlite3
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
GEX_DIR     = BASE_DIR / "results" / "histgex"
DB_PATH     = BASE_DIR / "gex.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS gex_snapshots (
            ndate   INTEGER NOT NULL,
            ntime   INTEGER NOT NULL,
            symbol  TEXT    NOT NULL DEFAULT 'SPX',
            uprice  REAL,
            data    TEXT,
            PRIMARY KEY (ndate, ntime, symbol)
        )
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_gex_ndate
        ON gex_snapshots (ndate)
    """)
    con.commit()


def import_histgex(con: sqlite3.Connection) -> tuple[int, int]:
    """Scan results/histgex/**/*_histgex.json and INSERT OR IGNORE into gex_snapshots."""
    files = sorted(GEX_DIR.glob("**/*_histgex.json"))
    inserted = 0
    skipped  = 0
    for f in files:
        try:
            raw    = json.loads(f.read_text(encoding="utf-8"))
            # Derive ndate/ntime from filename stem: YYYYMMDD_NNNN_SPX_histgex
            parts  = f.stem.split("_")           # ['20260622', '1530', 'SPX', 'histgex']
            ndate  = int(parts[0])
            ntime  = int(parts[1])
            symbol = parts[2] if len(parts) > 2 else "SPX"
            uprice = raw.get("uprice", 0)
            data   = raw.get("data") or []
            if not data:
                skipped += 1
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO gex_snapshots (ndate, ntime, symbol, uprice, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (ndate, ntime, symbol, uprice, json.dumps(data)),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  WARN: {f.name}: {e}")
    con.commit()
    return inserted, skipped


def main():
    print(f"Database: {DB_PATH}")
    con = get_connection(DB_PATH)
    init_db(con)

    print("Importing histgex snapshots...")
    inserted, skipped = import_histgex(con)
    print(f"  Inserted: {inserted}  Already present / empty: {skipped}")

    total = con.execute("SELECT COUNT(*) FROM gex_snapshots").fetchone()[0]
    dates = con.execute("SELECT COUNT(DISTINCT ndate) FROM gex_snapshots").fetchone()[0]
    print(f"  Total rows in DB: {total}  ({dates} distinct dates)")
    con.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
