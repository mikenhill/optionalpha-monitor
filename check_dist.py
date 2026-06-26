import sqlite3

con = sqlite3.connect('gex.db')

print('2026-06-26 snapshots:')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice FROM gex_snapshots WHERE ndate=20260626 AND symbol="SPX" ORDER BY ntime')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

print('\n2026-06-25 snapshots:')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice FROM gex_snapshots WHERE ndate=20260625 AND symbol="SPX" ORDER BY ntime')
rows = cursor.fetchall()
for r in rows:
    print(f'  {r}')

con.close()
