import sqlite3

con = sqlite3.connect('gex.db')

# Check what metric names exist in percentile table
print("Distinct metric names in gex_percentile_history:")
rows = con.execute('SELECT DISTINCT metric_name FROM gex_percentile_history').fetchall()
print([r[0] for r in rows])

# Check what time slots have percentile data
print("\nDistinct time slots in gex_percentile_history:")
rows = con.execute('SELECT DISTINCT ntime FROM gex_percentile_history ORDER BY ntime').fetchall()
print([r[0] for r in rows])

# Check sample size for each time slot
print("\nSample size per time slot:")
rows = con.execute('SELECT ntime, COUNT(DISTINCT ndate) as count FROM gex_percentile_history GROUP BY ntime ORDER BY ntime').fetchall()
for row in rows:
    print(f"  {row[0]}: {row[1]} dates")

# Check if 935 has any data
print("\nChecking 935 specifically:")
rows = con.execute('SELECT COUNT(*) FROM gex_percentile_history WHERE ntime=935').fetchone()
print(f"Total records at 935: {rows[0]}")

con.close()
