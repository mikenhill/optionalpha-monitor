import sqlite3
import json

con = sqlite3.connect('gex.db')

print('=== 03:42 raw_json ===')
cursor = con.execute('SELECT raw_json FROM live_captures WHERE ndate=20260626 AND ntime=342')
row = cursor.fetchone()
if row and row[0]:
    data = json.loads(row[0])
    print(f'  Type: {type(data)}')
    print(f'  Keys: {list(data.keys()) if isinstance(data, dict) else "list"}')
    if isinstance(data, list):
        print(f'  Length: {len(data)}')
        if len(data) > 0:
            print(f'  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else "not dict"}')
    elif isinstance(data, dict):
        if 'data' in data:
            print(f'  data key length: {len(data["data"])}')

print('\n=== 07:36 raw_json ===')
cursor = con.execute('SELECT raw_json FROM live_captures WHERE ndate=20260626 AND ntime=736')
row = cursor.fetchone()
if row and row[0]:
    data = json.loads(row[0])
    print(f'  Type: {type(data)}')
    print(f'  Keys: {list(data.keys()) if isinstance(data, dict) else "list"}')
    if isinstance(data, list):
        print(f'  Length: {len(data)}')
        if len(data) > 0:
            print(f'  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else "not dict"}')
    elif isinstance(data, dict):
        if 'data' in data:
            print(f'  data key length: {len(data["data"])}')

con.close()
