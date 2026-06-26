import sqlite3
import json
import time
from gex_historical_intraday import fetch_histgex

DB_PATH = "gex.db"

con = sqlite3.connect(DB_PATH)

# Find all histgex snapshots with NULL raw_json
cursor = con.execute('''
    SELECT ndate, ntime 
    FROM gex_snapshots 
    WHERE symbol='SPX' AND source='histgex' AND raw_json IS NULL
    ORDER BY ndate, ntime
''')
rows = cursor.fetchall()

print(f"Found {len(rows)} histgex snapshots with NULL raw_json")

updated = 0
failed = 0

for ndate, ntime in rows:
    print(f"Fetching {ndate} {ntime}...", end=" ", flush=True)
    try:
        data = fetch_histgex(symbol="SPX", ndate=ndate, ntime=ntime)
        if not data:
            print("no data")
            failed += 1
            time.sleep(2)
            continue
        
        raw_json_str = json.dumps(data)
        cursor = con.execute('''
            UPDATE gex_snapshots 
            SET raw_json = ?
            WHERE ndate=? AND ntime=? AND symbol='SPX'
        ''', (raw_json_str, ndate, ntime))
        con.commit()
        
        updated += 1
        print(f"OK (length={len(raw_json_str)})")
        time.sleep(2)  # rate limit
    except Exception as e:
        print(f"ERROR: {e}")
        failed += 1
        time.sleep(2)

con.close()
print(f"\nBackfill complete. Updated {updated} snapshots, failed {failed}.")
