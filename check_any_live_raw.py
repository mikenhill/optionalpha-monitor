import sqlite3

con = sqlite3.connect('gex.db')
cursor = con.execute('SELECT ndate, ntime, source FROM snapshot WHERE source="gex" AND raw_json IS NOT NULL ORDER BY ndate DESC, ntime DESC LIMIT 10')
rows = cursor.fetchall()

print('Live snapshots with raw_json (most recent):')
for r in rows:
    print(f'  {r[0]} {r[1]} ({r[2]})')
