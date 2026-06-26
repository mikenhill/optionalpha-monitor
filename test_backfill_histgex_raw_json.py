import sqlite3
import json
from gex_historical_intraday import fetch_histgex

DB_PATH = "gex.db"

# Test with a single histgex snapshot
test_ndate = 20260625
test_ntime = 1130

print(f"Testing backfill for {test_ndate} {test_ntime} (source=histgex)")

# Check current state
con = sqlite3.connect(DB_PATH)
cursor = con.execute('''
    SELECT ndate, ntime, source, raw_json IS NULL as is_null
    FROM gex_snapshots 
    WHERE ndate=? AND ntime=? AND symbol='SPX'
''', (test_ndate, test_ntime))
row = cursor.fetchone()
if row:
    print(f"Current state: ndate={row[0]}, ntime={row[1]}, source={row[2]}, raw_json_null={row[3]}")
else:
    print("Snapshot not found")
    con.close()
    exit(1)

# Fetch histgex data from API
print(f"Fetching histgex data from API...")
try:
    data = fetch_histgex(symbol="SPX", ndate=test_ndate, ntime=test_ntime)
    if not data:
        print("API returned no data")
        con.close()
        exit(1)
    print(f"API response keys: {list(data.keys())}")
    print(f"Data length: {len(data.get('data', []))} strike rows")
except Exception as e:
    print(f"Error fetching from API: {e}")
    con.close()
    exit(1)

# Update raw_json column
print(f"Updating raw_json column...")
raw_json_str = json.dumps(data)
cursor = con.execute('''
    UPDATE gex_snapshots 
    SET raw_json = ?
    WHERE ndate=? AND ntime=? AND symbol='SPX'
''', (raw_json_str, test_ndate, test_ntime))
con.commit()

# Verify update
cursor = con.execute('''
    SELECT ndate, ntime, source, length(raw_json) as json_length
    FROM gex_snapshots 
    WHERE ndate=? AND ntime=? AND symbol='SPX'
''', (test_ndate, test_ntime))
row = cursor.fetchone()
if row:
    print(f"Updated: ndate={row[0]}, ntime={row[1]}, source={row[2]}, raw_json_length={row[3]}")
else:
    print("Update failed")

con.close()
print("Test complete")
