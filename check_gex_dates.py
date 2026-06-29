import sqlite3

con = sqlite3.connect('gex.db')
cursor = con.cursor()

# Check available dates in gex_strike_window
print("=== Available dates in gex_strike_window ===")
cursor.execute("SELECT DISTINCT ndate FROM gex_strike_window ORDER BY ndate")
dates = cursor.fetchall()
for date in dates:
    print(f"  {date[0]}")

print(f"\nTotal dates: {len(dates)}")

# Check available dates in snapshot
print("\n=== Available dates in snapshot ===")
cursor.execute("SELECT DISTINCT ndate FROM snapshot ORDER BY ndate")
dates = cursor.fetchall()
for date in dates:
    print(f"  {date[0]}")

print(f"\nTotal dates: {len(dates)}")

# Check if 2026-06-26 exists
print("\n=== Checking 2026-06-26 ===")
ndate = 20260626
cursor.execute("SELECT COUNT(*) FROM gex_strike_window WHERE ndate=?", (ndate,))
count = cursor.fetchone()[0]
print(f"gex_strike_window count for 20260626: {count}")

cursor.execute("SELECT COUNT(*) FROM snapshot WHERE ndate=?", (ndate,))
count = cursor.fetchone()[0]
print(f"snapshot count for 20260626: {count}")

# Show some sample records around that date
print("\n=== Sample records around 2026-06-26 ===")
cursor.execute("""
    SELECT ndate, ntime, symbol, source, price
    FROM gex_strike_window
    WHERE ndate >= 20260620 AND ndate <= 20260630
    ORDER BY ndate, ntime
    LIMIT 10
""")
rows = cursor.fetchall()
for row in rows:
    print(f"  {row}")

con.close()
