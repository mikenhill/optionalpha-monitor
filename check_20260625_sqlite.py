import sqlite3

con = sqlite3.connect('gex.db')

print('=== 2026-06-25 Pre-market snapshots in SQLite ===')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, net_gex, kcs FROM gex_snapshots WHERE ndate=20260625 AND is_premarket=1 AND symbol="SPX" ORDER BY ntime')
for row in cursor.fetchall():
    print(f'  ntime={row[1]:04d}: is_premarket={row[2]}, sentiment={row[3]:.0f}%, uprice={row[4]:.2f}, net_gex={row[5]:,.0f}, kcs={row[6]:.1f}')

print('\n=== 2026-06-25 RTH snapshots (10:00, 10:01, 10:32, 10:58, 11:35) in SQLite ===')
times = [1000, 1001, 1032, 1058, 1135]
for ntime in times:
    cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, net_gex, kcs FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"', (ntime,))
    row = cursor.fetchone()
    if row:
        print(f'  ntime={ntime:04d}: is_premarket={row[2]}, sentiment={row[3]:.0f}%, uprice={row[4]:.2f}, net_gex={row[5]:,.0f}, kcs={row[6]:.1f}')
    else:
        print(f'  ntime={ntime:04d}: NOT FOUND')

con.close()
