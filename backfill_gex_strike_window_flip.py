"""Backfill flip column for existing gex_strike_window rows."""
import sqlite3
import json
import sys

DB_PATH = 'gex.db'


def backfill_flip(limit=None):
    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Recompute flip for all rows to ensure consistency after logic changes
    query = "SELECT ndate, ntime, symbol, data FROM gex_strike_window ORDER BY ndate, ntime"
    if limit:
        query = f"{query} LIMIT {limit}"

    rows = cursor.execute(query).fetchall()
    total = len(rows)
    print(f"Found {total} rows to backfill")

    updated = 0
    for ndate, ntime, symbol, data_json in rows:
        try:
            data = json.loads(data_json)
            if isinstance(data, list):
                strikes = data
            elif isinstance(data, dict):
                strikes = data.get("data", [])
            else:
                strikes = []
            from controllers.gex_calculations import calculate_flip_level
            flip = calculate_flip_level(strikes)
            cursor.execute(
                "UPDATE gex_strike_window SET flip=? WHERE ndate=? AND ntime=? AND symbol=?",
                (flip, ndate, ntime, symbol)
            )
            updated += 1
            if updated % 100 == 0:
                con.commit()
                print(f"Updated {updated}/{total}...")
        except Exception as e:
            print(f"Error updating {ndate}-{ntime}: {e}", file=sys.stderr)
            continue

    con.commit()
    con.close()
    print(f"Backfill complete. Updated {updated}/{total} rows.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    backfill_flip(limit)
