import sqlite3
import json

con = sqlite3.connect('gex.db')

print('2026-06-25 pre-market data column content:')
cursor = con.execute('SELECT ndate, ntime, data FROM gex_snapshots WHERE ndate=20260625 AND ntime IN (528, 751) AND symbol="SPX"')
rows = cursor.fetchall()
for r in rows:
    print(f'\nndate={r[0]}, ntime={r[1]}')
    try:
        data = json.loads(r[2])
        print(f'  data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')
        if isinstance(data, dict) and 'data' in data:
            print(f'  data.data length: {len(data["data"])}')
    except:
        print(f'  data length: {len(r[2]) if r[2] else 0}')
        print(f'  data preview: {r[2][:200] if r[2] else "None"}')

con.close()
