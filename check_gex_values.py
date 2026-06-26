import sqlite3
import json

con = sqlite3.connect('gex.db')

print('Checking GEX values in data blob for 10:00:')
cursor = con.execute('SELECT data FROM gex_snapshots WHERE ndate=20260625 AND ntime=1000 AND symbol="SPX"')
row = cursor.fetchone()
if row and row[0]:
    data = json.loads(row[0])
    if isinstance(data, list):
        # Count non-zero GEX values
        non_zero_cg = sum(1 for s in data if s.get('cg', 0) != 0)
        non_zero_pg = sum(1 for s in data if s.get('pg', 0) != 0)
        print(f'  Total strikes: {len(data)}')
        print(f'  Strikes with non-zero cg: {non_zero_cg}')
        print(f'  Strikes with non-zero pg: {non_zero_pg}')
        # Show some sample values
        print(f'  Sample strikes (around uprice 7330):')
        for s in data:
            if 7300 <= s.get('strike', 0) <= 7360:
                print(f'    {s}')

print('\nChecking 10:30 for comparison:')
cursor = con.execute('SELECT data FROM gex_snapshots WHERE ndate=20260625 AND ntime=1030 AND symbol="SPX"')
row = cursor.fetchone()
if row and row[0]:
    data = json.loads(row[0])
    if isinstance(data, list):
        non_zero_cg = sum(1 for s in data if s.get('cg', 0) != 0)
        non_zero_pg = sum(1 for s in data if s.get('pg', 0) != 0)
        print(f'  Total strikes: {len(data)}')
        print(f'  Strikes with non-zero cg: {non_zero_cg}')
        print(f'  Strikes with non-zero pg: {non_zero_pg}')

con.close()
