import sqlite3

con = sqlite3.connect('gex.db')

print('2026-06-26 live_captures:')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice FROM live_captures WHERE ndate=20260626 AND symbol="SPX" ORDER BY ntime')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

print('\n2026-06-25 pre-market snapshots (check data column):')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, substr(data, 1, 100) FROM gex_snapshots WHERE ndate=20260625 AND ntime IN (528, 751) AND symbol="SPX"')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

con.close()
