import sqlite3
import json

conn = sqlite3.connect('gex.db')
rows = conn.execute("""
    SELECT data FROM gex_strike_window 
    WHERE ndate=20260618 AND ntime=1400 AND symbol='SPX'
""").fetchall()

if rows:
    data = json.loads(rows[0][0])
    print(f'Total strikes: {len(data)}')
    if data:
        print('Keys in first strike:', list(data[0].keys()))
        print('First strike:', json.dumps(data[0], indent=2))
else:
    print('No data found')

conn.close()
