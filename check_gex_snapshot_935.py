import sqlite3

con = sqlite3.connect('gex.db')

# Check if gex_strike_window has data for 2026-06-25 at 935
ndate = 20260625
ntime = 935

print(f"Checking gex_strike_window for {ndate} at {ntime}:")
rows = con.execute(
    'SELECT ndate, ntime, symbol, source, price FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol="SPX"',
    (ndate, ntime)
).fetchall()

if rows:
    print(f"Found {len(rows)} records:")
    for row in rows:
        print(f"  ndate={row[0]}, ntime={row[1]}, symbol={row[2]}, source={row[3]}, price={row[4]}")
else:
    print("No records found in gex_strike_window for this date/time")

# Check what time slots exist for this date
print(f"\nAll time slots in gex_strike_window for {ndate}:")
rows = con.execute(
    'SELECT DISTINCT ntime FROM gex_strike_window WHERE ndate=? AND symbol="SPX" AND source="gex" ORDER BY ntime',
    (ndate,)
).fetchall()
print([r[0] for r in rows])

con.close()
