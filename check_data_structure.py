import sqlite3
import json

con = sqlite3.connect('gex.db')

print('Checking data structure for different snapshots:')
times = [528, 1000, 1030]
for ntime in times:
    cursor = con.execute('SELECT ndate, ntime, data FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"', (ntime,))
    row = cursor.fetchone()
    if row:
        data = json.loads(row[2])
        print(f'\nntime={ntime}:')
        print(f'  data type: {type(data)}')
        if isinstance(data, dict):
            print(f'  data keys: {list(data.keys())}')
        elif isinstance(data, list):
            print(f'  data is list with {len(data)} items')

con.close()
