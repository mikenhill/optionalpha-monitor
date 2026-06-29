import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

# Check the structure of a few raw_json records
cursor.execute("""
    SELECT ndate, ntime, symbol, raw_json
    FROM snapshot
    WHERE raw_json IS NOT NULL
    LIMIT 3
""")

rows = cursor.fetchall()

for ndate, ntime, symbol, raw_json in rows:
    print(f"\n=== {ndate}-{ntime} {symbol} ===")
    data = json.loads(raw_json)
    print(f"Type: {type(data)}")
    if isinstance(data, list):
        print(f"List length: {len(data)}")
        if len(data) > 0:
            print(f"First item type: {type(data[0])}")
            print(f"First item keys: {data[0].keys() if isinstance(data[0], dict) else 'N/A'}")
    elif isinstance(data, dict):
        print(f"Dict keys: {data.keys()}")

con.close()
