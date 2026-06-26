import sqlite3

con = sqlite3.connect('gex.db')

print('live_captures table schema:')
cursor = con.execute('PRAGMA table_info(live_captures)')
for r in cursor.fetchall():
    print(f'  {r}')

print('\n2026-06-26 live_captures:')
cursor = con.execute('SELECT * FROM live_captures WHERE ndate=20260626 AND symbol="SPX" ORDER BY ntime')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

print('\n2026-06-25 pre-market snapshots (data column length):')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, length(data) FROM gex_snapshots WHERE ndate=20260625 AND ntime IN (528, 751) AND symbol="SPX"')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

con.close()
