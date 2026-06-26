import sqlite3

con = sqlite3.connect('gex.db')

print('=== All snapshots with net_gex=0 (excluding pre-market) ===')
cursor = con.execute('SELECT ndate, ntime, is_premarket, sentiment, uprice, net_gex, kcs FROM gex_snapshots WHERE net_gex=0 AND is_premarket=0 AND symbol="SPX" ORDER BY ndate DESC, ntime')
rows = cursor.fetchall()
print(f'Found {len(rows)} RTH snapshots with net_gex=0')
for row in rows[:20]:  # Show first 20
    print(f'  {row[0]}-{row[1]:04d}: sentiment={row[3]:.0f}%, uprice={row[4]:.2f}, net_gex={row[5]:,.0f}, kcs={row[6]:.1f}')

if len(rows) > 20:
    print(f'  ... and {len(rows) - 20} more')

con.close()
