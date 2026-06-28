import sqlite3

con = sqlite3.connect('gex.db')

# Get the 10:00 record from 2026-06-23
cursor = con.execute('SELECT ndate, ntime, uprice, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio, key_strike FROM snapshot WHERE ndate=20260623 AND ntime=1000 AND symbol="SPX"')
row = cursor.fetchone()

if row:
    ndate, ntime, uprice, total_call_vol, total_put_vol, key_call_gex, key_put_gex, gex_ratio, key_strike = row
    print(f"=== 10:00 Record on 2026-06-23 ===")
    print(f"uprice: {uprice}")
    print(f"total_call_vol: {total_call_vol}")
    print(f"total_put_vol: {total_put_vol}")
    print(f"key_call_gex: {key_call_gex}")
    print(f"key_put_gex: {key_put_gex}")
    print(f"gex_ratio: {gex_ratio}")
    print(f"key_strike: {key_strike}")
else:
    print("No 10:00 record found")
