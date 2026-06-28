import sqlite3

con = sqlite3.connect('gex.db')

# Check historical snapshots
cursor = con.execute('SELECT ndate, ntime, uprice, source FROM snapshot WHERE ndate=20260623 AND symbol="SPX" LIMIT 5')
rows = cursor.fetchall()

print('Sample snapshots:')
for r in rows:
    print(f'  {r[0]} {r[1]} uprice={r[2]} source={r[3]}')

# Check if historical snapshots have NULL uprice
cursor = con.execute('SELECT COUNT(*) FROM snapshot WHERE source="histgex" AND uprice IS NULL')
null_count = cursor.fetchone()[0]
print(f'\nHistorical snapshots with NULL uprice: {null_count}')

# Check if live snapshots have NULL uprice
cursor = con.execute('SELECT COUNT(*) FROM snapshot WHERE source="gex" AND uprice IS NULL')
null_count_live = cursor.fetchone()[0]
print(f'Live snapshots with NULL uprice: {null_count_live}')
