import sqlite3

con = sqlite3.connect('gex.db')
rows = con.execute('SELECT DISTINCT ntime FROM gex_strike_window WHERE symbol="SPX" AND source="gex" ORDER BY ntime').fetchall()
print('Current time slots:', [r[0] for r in rows])

# Count records per time slot
for row in rows:
    ntime = row[0]
    count = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=? AND symbol="SPX" AND source="gex"', (ntime,)).fetchone()[0]
    print(f'  {ntime}: {count} records')
