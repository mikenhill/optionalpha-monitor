import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

# Check the error case (20260622-1530)
cursor.execute("""
    SELECT ndate, ntime, symbol, raw_json
    FROM snapshot
    WHERE ndate=20260622 AND ntime=1530 AND symbol='SPX'
""")

row = cursor.fetchone()
if row:
    ndate, ntime, symbol, raw_json = row
    print(f"=== Error case: {ndate}-{ntime} {symbol} ===")
    print(f"raw_json length: {len(raw_json) if raw_json else 0}")
    if raw_json:
        try:
            data = json.loads(raw_json)
            print(f"Type: {type(data)}")
            if isinstance(data, list):
                print(f"List length: {len(data)}")
                if len(data) > 0:
                    print(f"First item: {data[0]}")
            elif isinstance(data, dict):
                print(f"Keys: {data.keys()}")
                if 'data' in data:
                    print(f"Data type: {type(data['data'])}")
                    if isinstance(data['data'], list) and len(data['data']) > 0:
                        print(f"First strike: {data['data'][0]}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
else:
    print("Error case not found")

# Check the 15 missing snapshots
print("\n=== Missing snapshots (no raw_json or empty) ===")
cursor.execute("""
    SELECT s.ndate, s.ntime, s.symbol, s.raw_json
    FROM snapshot s
    LEFT JOIN gex_strike_window g ON s.ndate = g.ndate AND s.ntime = g.ntime AND s.symbol = g.symbol
    WHERE g.ndate IS NULL
    ORDER BY s.ndate, s.ntime
""")

rows = cursor.fetchall()
for ndate, ntime, symbol, raw_json in rows:
    has_raw = "Yes" if raw_json else "No"
    raw_len = len(raw_json) if raw_json else 0
    print(f"  {ndate}-{ntime} {symbol}: raw_json={has_raw}, length={raw_len}")

con.close()
