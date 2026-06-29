import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

ndate = 20260625

print("=== Available times for 2026-06-26 in gex_strike_window ===")
cursor.execute("""
    SELECT ntime, price
    FROM gex_strike_window
    WHERE ndate=? AND source='gex'
    ORDER BY ntime
""", (ndate,))
rows = cursor.fetchall()
for row in rows:
    print(f"  ntime: {row[0]}, price: {row[1]}")

print("\n=== Available times for 2026-06-26 in snapshot ===")
cursor.execute("""
    SELECT ntime, uprice, net_gex, total_call_gex, total_put_gex
    FROM snapshot
    WHERE ndate=? AND symbol='SPX'
    ORDER BY ntime
""", (ndate,))
rows = cursor.fetchall()
for row in rows:
    net_gex = row[2] if row[2] is not None else 0
    call_gex = row[3] if row[3] is not None else 0
    put_gex = row[4] if row[4] is not None else 0
    print(f"  ntime: {row[0]}, uprice: {row[1]}, net_gex: {net_gex:,.2f}, call_gex: {call_gex:,.2f}, put_gex: {put_gex:,.2f}")

# Check if there's a 1030 time
print("\n=== Checking for 1030 specifically ===")
cursor.execute("""
    SELECT ndate, ntime, symbol, uprice, net_gex, total_call_gex, total_put_gex
    FROM snapshot
    WHERE ndate=? AND ntime=1030 AND symbol='SPX'
""", (ndate,))
row = cursor.fetchone()
if row:
    print(f"Found in snapshot: {row}")
else:
    print("Not found in snapshot")

cursor.execute("""
    SELECT ndate, ntime, symbol, source, price, data
    FROM gex_strike_window
    WHERE ndate=? AND ntime=1030 AND source='gex'
""", (ndate,))
row = cursor.fetchone()
if row:
    print(f"Found in gex_strike_window: ndate={row[0]}, ntime={row[1]}, symbol={row[2]}, source={row[3]}, price={row[4]}")
    strikes = json.loads(row[5])
    call_gex = sum(r.get("cg", 0) or 0 for r in strikes)
    put_gex = sum(r.get("pg", 0) or 0 for r in strikes)
    net_gex = call_gex - put_gex
    print(f"  Calculated: call_gex={call_gex:,.2f}, put_gex={put_gex:,.2f}, net_gex={net_gex:,.2f}")
else:
    print("Not found in gex_strike_window")

con.close()
