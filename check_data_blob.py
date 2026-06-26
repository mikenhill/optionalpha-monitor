import sqlite3
import json

con = sqlite3.connect('gex.db')

print('2026-06-25 10:00 data blob content:')
cursor = con.execute('SELECT data FROM gex_snapshots WHERE ndate=20260625 AND ntime=1000 AND symbol="SPX"')
row = cursor.fetchone()
if row and row[0]:
    try:
        data = json.loads(row[0])
        print(f'  data type: {type(data)}')
        if isinstance(data, dict):
            print(f'  data keys: {list(data.keys())}')
            if 'data' in data:
                print(f'  data.data length: {len(data["data"])}')
                print(f'  data.data[0]: {data["data"][0]}')
            if 'summary' in data:
                print(f'  data.summary: {data["summary"]}')
        elif isinstance(data, list):
            print(f'  data is list with {len(data)} items')
            print(f'  data[0]: {data[0]}')
    except Exception as e:
        print(f'  Error parsing data: {e}')
        print(f'  data preview: {row[0][:200]}')

print('\nCompare with a working snapshot (10:30):')
cursor = con.execute('SELECT data, net_gex, kcs FROM gex_snapshots WHERE ndate=20260625 AND ntime=1030 AND symbol="SPX"')
row = cursor.fetchone()
if row:
    print(f'  net_gex: {row[1]}, kcs: {row[2]}')
    if row[0]:
        try:
            data = json.loads(row[0])
            print(f'  data type: {type(data)}')
            if isinstance(data, dict):
                print(f'  data keys: {list(data.keys())}')
        except Exception as e:
            print(f'  Error: {e}')

con.close()
