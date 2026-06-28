import sqlite3

con = sqlite3.connect('gex.db')

# Find all 09:30 records on 2026-06-23
cursor = con.execute('SELECT ndate, ntime, uprice, source, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio FROM snapshot WHERE ndate=20260623 AND ntime=930 AND symbol="SPX"')
rows = cursor.fetchall()

print('All 09:30 records on 2026-06-23:')
for r in rows:
    ndate, ntime, uprice, source, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio = r
    print(f'  {ndate} {ntime} uprice={uprice} source={source} call_vol={total_call_vol} put_vol={total_put_vol} key_cg={key_call_gex} key_pg={key_put_gex} ratio={gex_ratio}')

# Find all records on 2026-06-23
cursor = con.execute('SELECT ndate, ntime, uprice, source FROM snapshot WHERE ndate=20260623 AND symbol="SPX" ORDER BY ntime')
rows = cursor.fetchall()

print('\nAll records on 2026-06-23:')
for r in rows:
    ndate, ntime, uprice, source = r
    print(f'  {ndate} {ntime} uprice={uprice} source={source}')
