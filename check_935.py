import sqlite3
con = sqlite3.connect('gex.db')
count = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=935 AND symbol="SPX" AND source="gex"').fetchone()[0]
print(f'Existing 935 records: {count}')
