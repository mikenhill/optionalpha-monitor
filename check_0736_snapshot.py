import sqlite3
import json

con = sqlite3.connect('gex.db')

# Get the latest live snapshot (should be 07:36)
cursor = con.execute('''
    SELECT ndate, ntime, symbol, uprice, source, raw_json IS NULL as raw_null, 
           total_put_gex, total_call_gex, gex_ratio
    FROM gex_snapshots 
    WHERE symbol='SPX' 
    ORDER BY ndate DESC, ntime DESC
    LIMIT 5
''')

print('Recent snapshots:')
for row in cursor.fetchall():
    print(f'  {row[0]} {row[1]}: source={row[4]}, raw_null={row[5]}, put_gex={row[6]}, call_gex={row[7]}, gex_ratio={row[8]}')

# Get the specific 07:36 snapshot
cursor = con.execute('''
    SELECT ndate, ntime, symbol, uprice, source, raw_json, data,
           total_put_gex, total_call_gex, gex_ratio, net_gex
    FROM gex_snapshots 
    WHERE symbol='SPX' AND ntime=736
    ORDER BY ndate DESC
    LIMIT 1
''')

row = cursor.fetchone()
if row:
    print(f'\n07:36 snapshot found:')
    print(f'  ndate={row[0]}, ntime={row[1]}, source={row[4]}')
    print(f'  raw_json is NULL: {row[5] is None}')
    print(f'  total_put_gex: {row[7]}')
    print(f'  total_call_gex: {row[8]}')
    print(f'  gex_ratio: {row[9]}')
    print(f'  net_gex: {row[10]}')
    
    if row[5]:
        print(f'\nRaw JSON length: {len(row[5])}')
        raw_data = json.loads(row[5])
        print(f'Raw JSON keys: {list(raw_data.keys())}')
        if 'data' in raw_data:
            print(f'Number of strike rows: {len(raw_data["data"])}')
    else:
        print('\nRaw JSON is NULL - this is why Put GEX is blank')
else:
    print('\nNo 07:36 snapshot found')

con.close()
