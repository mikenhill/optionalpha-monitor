import sqlite3

con = sqlite3.connect('gex.db')

print('=== 2026-06-25 snapshots - checking flat column values ===')
times = [528, 751, 1000, 1001, 1032, 1058, 1135]
for ntime in times:
    cursor = con.execute(
        'SELECT ndate, ntime, sentiment, net_gex, kcs, uprice, key_call_gex, key_put_gex FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"',
        (ntime,)
    )
    row = cursor.fetchone()
    if row:
        print(f'  ntime={ntime:04d}: sentiment={row[2]}, net_gex={row[3]}, kcs={row[4]}, uprice={row[5]}, key_call_gex={row[6]}, key_put_gex={row[7]}')
    else:
        print(f'  ntime={ntime:04d}: NOT FOUND')

con.close()
