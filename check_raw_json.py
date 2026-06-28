import sqlite3

con = sqlite3.connect('gex.db')
row = con.execute('SELECT ndate, ntime, length(raw_json) as json_len FROM snapshot WHERE ndate=20260625 AND ntime=1000 AND symbol="SPX"').fetchone()
print(f"Row: {row}")
con.close()
