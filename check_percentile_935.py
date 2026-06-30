import sqlite3

con = sqlite3.connect('gex.db')

# Check what percentile data exists for 2026-06-25 at 935
ndate = 20260625
ntime = 935

print(f"Checking percentile data for {ndate} at {ntime}:")
rows = con.execute(
    'SELECT metric_name, value, percentile FROM gex_percentile_history WHERE ndate=? AND ntime=?',
    (ndate, ntime)
).fetchall()

if rows:
    print(f"Found {len(rows)} percentile records:")
    for row in rows:
        print(f"  {row[0]}: value={row[1]}, percentile={row[2]}")
else:
    print("No percentile data found for this date/time")

# Check what time slots have percentile data for this date
print(f"\nAll time slots with percentile data for {ndate}:")
rows = con.execute(
    'SELECT DISTINCT ntime FROM gex_percentile_history WHERE ndate=?',
    (ndate,)
).fetchall()
print([r[0] for r in rows])

# Check what dates have percentile data for 935
print(f"\nAll dates with percentile data for 935:")
rows = con.execute(
    'SELECT DISTINCT ndate FROM gex_percentile_history WHERE ntime=?',
    (ntime,)
).fetchall()
print([r[0] for r in rows])

con.close()
