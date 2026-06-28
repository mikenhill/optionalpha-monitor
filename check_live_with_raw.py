import sqlite3

con = sqlite3.connect('gex.db')
cursor = con.execute('SELECT ndate, ntime, source FROM snapshot WHERE ndate=20260623 AND symbol="SPX" AND source="gex" AND raw_json IS NOT NULL ORDER BY ntime')
rows = cursor.fetchall()

print('Live snapshots with raw_json on 20260623:')
for r in rows:
    print(f'  {r[0]} {r[1]} ({r[2]})')
