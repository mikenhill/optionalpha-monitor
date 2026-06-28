import sqlite3
import json

con = sqlite3.connect('gex.db')
# Get the 10:00 record from 2026-06-23 (histgex source)
cursor = con.execute('SELECT ndate, ntime, raw_json FROM snapshot WHERE ndate=20260623 AND ntime=1000 AND symbol="SPX" AND source="histgex" AND raw_json IS NOT NULL LIMIT 1')
row = cursor.fetchone()

if row:
    ndate, ntime, raw_json = row
    print(f"=== Historical Snapshot: {ndate} {ntime} ===")
    if raw_json:
        data = json.loads(raw_json)
        # Save to file
        with open('test_payload_20260623_1000.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Saved to test_payload_20260623_1000.json")
        print(f"Symbol: {data.get('symbol')}")
        print(f"ndate: {data.get('ndate')}")
        print(f"ntime: {data.get('ntime')}")
        print(f"uprice: {data.get('uprice')}")
        print(f"Number of strikes: {len(data.get('data', []))}")
    else:
        print("raw_json is NULL")
else:
    print("No data found for 20260623 10:00")
