import sqlite3
import json

con = sqlite3.connect('gex.db')

print('2026-06-25 RTH snapshots with missing data:')
times = [1000, 1001, 1032, 1058, 1135]
for ntime in times:
    cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, net_gex, kcs, length(data), length(raw_json) FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"', (ntime,))
    row = cursor.fetchone()
    print(f'  ntime={ntime}: {row}')

print('\nChecking raw_json content for 10:00:')
cursor = con.execute('SELECT raw_json FROM gex_snapshots WHERE ndate=20260625 AND ntime=1000 AND symbol="SPX"')
row = cursor.fetchone()
if row and row[0]:
    try:
        data = json.loads(row[0])
        print(f'  raw_json type: {type(data)}')
        print(f'  raw_json keys: {list(data.keys()) if isinstance(data, dict) else "not a dict"}')
        if isinstance(data, dict) and 'summary' in data:
            print(f'  summary: {data["summary"]}')
    except Exception as e:
        print(f'  Error parsing raw_json: {e}')
        print(f'  raw_json preview: {row[0][:200]}')
else:
    print('  raw_json is None or empty')

con.close()
