import sqlite3
import json

con = sqlite3.connect('gex.db')

# Get the original 09:30 record from 2026-06-23
cursor = con.execute('SELECT ndate, ntime, uprice, raw_json, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio FROM snapshot WHERE ndate=20260623 AND ntime=930 AND symbol="SPX" AND source="histgex"')
row = cursor.fetchone()

if row:
    ndate, ntime, uprice, raw_json, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio = row
    print(f"=== Original 09:30 Record ===")
    print(f"uprice: {uprice}")
    print(f"total_call_vol: {total_call_vol}")
    print(f"total_put_vol: {total_put_vol}")
    print(f"key_call_gex: {key_call_gex}")
    print(f"key_put_gex: {key_put_gex}")
    print(f"gex_ratio: {gex_ratio}")
    
    if raw_json:
        data = json.loads(raw_json)
        print(f"\nNumber of strikes in raw_json: {len(data.get('data', []))}")
        
        # Find the key strike (7475) in the data
        key_strike_data = None
        for strike in data.get('data', []):
            if strike.get('strike') == 7475:
                key_strike_data = strike
                break
        
        if key_strike_data:
            print(f"\nKey strike (7475) data:")
            print(f"  cg: {key_strike_data.get('cg')}")
            print(f"  pg: {key_strike_data.get('pg')}")
            print(f"  cvol: {key_strike_data.get('cvol')}")
            print(f"  pvol: {key_strike_data.get('pvol')}")
else:
    print("No original 09:30 record found")

# Get the test record from 2026-06-28
cursor = con.execute('SELECT ndate, ntime, uprice, raw_json, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio FROM snapshot WHERE ndate=20260628 AND ntime=930 AND symbol="SPX" AND source="test"')
row = cursor.fetchone()

if row:
    ndate, ntime, uprice, raw_json, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio = row
    print(f"\n=== Test Record (2026-06-28 09:30) ===")
    print(f"uprice: {uprice}")
    print(f"total_call_vol: {total_call_vol}")
    print(f"total_put_vol: {total_put_vol}")
    print(f"key_call_gex: {key_call_gex}")
    print(f"key_put_gex: {key_put_gex}")
    print(f"gex_ratio: {gex_ratio}")
    
    if raw_json:
        data = json.loads(raw_json)
        print(f"\nNumber of strikes in raw_json: {len(data.get('data', []))}")
        
        # Find the key strike (7475) in the data
        key_strike_data = None
        for strike in data.get('data', []):
            if strike.get('strike') == 7475:
                key_strike_data = strike
                break
        
        if key_strike_data:
            print(f"\nKey strike (7475) data:")
            print(f"  cg: {key_strike_data.get('cg')}")
            print(f"  pg: {key_strike_data.get('pg')}")
            print(f"  cvol: {key_strike_data.get('cvol')}")
            print(f"  pvol: {key_strike_data.get('pvol')}")
else:
    print("No test record found")
