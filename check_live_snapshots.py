import sqlite3

con = sqlite3.connect('gex.db')
cursor = con.execute('SELECT ndate, ntime, source FROM snapshot WHERE ndate=20260623 AND symbol="SPX" AND source="gex" ORDER BY ntime')
rows = cursor.fetchall()

print('Live snapshots on 20260623:')
for r in rows:
    print(f'  {r[0]} {r[1]} ({r[2]})')
