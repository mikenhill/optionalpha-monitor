import sqlite3

con = sqlite3.connect('gex.db')
row = con.execute('SELECT source FROM snapshot WHERE ndate=20260625 AND ntime=1400 AND symbol="SPX"').fetchone()
print(f'Source field value: {row[0] if row else None}')

# Check distinct source values
rows = con.execute('SELECT DISTINCT source, COUNT(*) FROM snapshot GROUP BY source').fetchall()
print('\nDistinct source values:')
for source, count in rows:
    print(f'  {source}: {count}')

con.close()
