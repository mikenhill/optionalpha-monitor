import sqlite3
import json

con = sqlite3.connect('gex.db')

# Get the original 10:00 record from 2026-06-23
cursor = con.execute('SELECT raw_json FROM snapshot WHERE ndate=20260623 AND ntime=1000 AND symbol="SPX" AND source="histgex"')
row = cursor.fetchone()

if row:
    original_raw = row[0]
    original_data = json.loads(original_raw)
    
    # Read the test payload file
    with open('test_payload_20260623_1000.json', 'r') as f:
        test_data = json.load(f)
    
    print('=== Original 10:00 Record ===')
    print(f'Strikes: {len(original_data["data"])}')
    print(f'uprice: {original_data["uprice"]}')
    
    # Calculate totals from original
    orig_cg = sum(s.get('cg', 0) for s in original_data['data'])
    orig_pg = sum(s.get('pg', 0) for s in original_data['data'])
    orig_cvol = sum(s.get('cvol', 0) for s in original_data['data'])
    orig_pvol = sum(s.get('pvol', 0) for s in original_data['data'])
    
    print(f'Calculated from original data:')
    print(f'  call_gex: {orig_cg}')
    print(f'  put_gex: {orig_pg}')
    print(f'  call_vol: {orig_cvol}')
    print(f'  put_vol: {orig_pvol}')
    
    print('\n=== Test Payload ===')
    print(f'Strikes: {len(test_data["data"])}')
    print(f'uprice: {test_data["uprice"]}')
    
    # Calculate totals from test
    test_cg = sum(s.get('cg', 0) for s in test_data['data'])
    test_pg = sum(s.get('pg', 0) for s in test_data['data'])
    test_cvol = sum(s.get('cvol', 0) for s in test_data['data'])
    test_pvol = sum(s.get('pvol', 0) for s in test_data['data'])
    
    print(f'Calculated from test data:')
    print(f'  call_gex: {test_cg}')
    print(f'  put_gex: {test_pg}')
    print(f'  call_vol: {test_cvol}')
    print(f'  put_vol: {test_pvol}')
    
    print('\n=== Comparison ===')
    print(f'call_gex match: {orig_cg == test_cg}')
    print(f'put_gex match: {orig_pg == test_pg}')
    print(f'call_vol match: {orig_cvol == test_cvol}')
    print(f'put_vol match: {orig_pvol == test_pvol}')
