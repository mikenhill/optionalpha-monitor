import sqlite3
import json

con = sqlite3.connect('gex.db')

print('=== 2026-06-25 snapshots - checking raw JSON data ===')
times = [528, 751, 1000, 1001, 1032, 1058, 1135]
for ntime in times:
    cursor = con.execute(
        'SELECT ndate, ntime, data, raw_json FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"',
        (ntime,)
    )
    row = cursor.fetchone()
    if row:
        data_json = row[2]
        raw_json = row[3]
        
        # Parse and check
        try:
            parsed = json.loads(data_json)
            if isinstance(parsed, dict):
                rows = parsed.get("data", [])
            else:
                rows = parsed if isinstance(parsed, list) else []
            
            print(f'  ntime={ntime:04d}: data blob has {len(rows)} rows, raw_json exists: {bool(raw_json)}')
            if len(rows) > 0:
                print(f'    First row keys: {list(rows[0].keys()) if rows else "N/A"}')
        except Exception as e:
            print(f'  ntime={ntime:04d}: ERROR parsing data: {e}')
    else:
        print(f'  ntime={ntime:04d}: NOT FOUND')

con.close()
