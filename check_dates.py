import sqlite3
con = sqlite3.connect('gex.db')
rows = con.execute('SELECT DISTINCT ndate FROM gex_snapshots WHERE symbol="SPX" ORDER BY ndate DESC LIMIT 10').fetchall()
print('Available dates:')
for r in rows:
    print(r[0])
