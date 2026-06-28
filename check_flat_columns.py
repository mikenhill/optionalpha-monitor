import sqlite3
import json

con = sqlite3.connect('gex.db')

# Get the original 10:00 record from 2026-06-23
cursor = con.execute('SELECT total_call_vol, total_put_vol, total_call_gex, total_put_gex, key_call_gex, key_put_gex, gex_ratio FROM snapshot WHERE ndate=20260623 AND ntime=1000 AND symbol="SPX" AND source="histgex"')
row = cursor.fetchone()

if row:
    total_call_vol, total_put_vol, total_call_gex, total_put_gex, key_call_gex, key_put_gex, gex_ratio = row
    
    print('=== Original 10:00 Flat Columns ===')
    print(f'total_call_vol: {total_call_vol}')
    print(f'total_put_vol: {total_put_vol}')
    print(f'total_call_gex: {total_call_gex}')
    print(f'total_put_gex: {total_put_gex}')
    print(f'key_call_gex: {key_call_gex}')
    print(f'key_put_gex: {key_put_gex}')
    print(f'gex_ratio: {gex_ratio}')
    
    # Get raw_json and calculate
    cursor = con.execute('SELECT raw_json FROM snapshot WHERE ndate=20260623 AND ntime=1000 AND symbol="SPX" AND source="histgex"')
    row = cursor.fetchone()
    if row:
        raw_json = row[0]
        data = json.loads(raw_json)
        
        calc_call_vol = sum(s.get('cvol', 0) for s in data['data'])
        calc_put_vol = sum(s.get('pvol', 0) for s in data['data'])
        calc_call_gex = sum(s.get('cg', 0) for s in data['data'])
        calc_put_gex = sum(s.get('pg', 0) for s in data['data'])
        
        print('\n=== Calculated from raw_json ===')
        print(f'call_vol: {calc_call_vol}')
        print(f'put_vol: {calc_put_vol}')
        print(f'call_gex: {calc_call_gex}')
        print(f'put_gex: {calc_put_gex}')
        
        print('\n=== Difference ===')
        print(f'call_vol diff: {total_call_vol - calc_call_vol}')
        print(f'put_vol diff: {total_put_vol - calc_put_vol}')
        print(f'call_gex diff: {total_call_gex - calc_call_gex}')
        print(f'put_gex diff: {total_put_gex - calc_put_gex}')
