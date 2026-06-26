import sqlite3

con = sqlite3.connect('gex.db')

print('2026-06-25 RTH snapshots (previously missing data):')
times = [1000, 1001, 1032, 1058, 1135]
for ntime in times:
    cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, net_gex, kcs FROM gex_snapshots WHERE ndate=20260625 AND ntime=? AND symbol="SPX"', (ntime,))
    row = cursor.fetchone()
    print(f'  ntime={ntime}: net_gex={row[5]:,.0f}, kcs={row[6]:.1f}')

con.close()
