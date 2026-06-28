import sqlite3

con = sqlite3.connect('gex.db')
cursor = con.execute('SELECT ndate, ntime, raw_json IS NOT NULL as has_raw FROM snapshot WHERE ndate=20260623 AND symbol="SPX" AND source="gex" AND ntime=1038')
row = cursor.fetchone()

if row:
    ndate, ntime, has_raw = row
    print(f'20260623 1038: has_raw_json = {has_raw}')
else:
    print('No record found')
