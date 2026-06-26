import sqlite3
import json

con = sqlite3.connect('gex.db')

print('2026-06-25 pre-market data column content (detailed):')
cursor = con.execute('SELECT ndate, ntime, data FROM gex_snapshots WHERE ndate=20260625 AND ntime IN (528, 751) AND symbol="SPX"')
rows = cursor.fetchall()
for r in rows:
    print(f'\nndate={r[0]}, ntime={r[1]}')
    try:
        data = json.loads(r[2])
        print(f'  data type: {type(data)}')
        print(f'  data length: {len(data)}')
        print(f'  data: {data[:3] if isinstance(data, list) else data}')
    except Exception as e:
        print(f'  Error: {e}')
        print(f'  data preview: {r[2][:200] if r[2] else "None"}')

con.close()
