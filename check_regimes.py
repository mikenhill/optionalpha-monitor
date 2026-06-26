import sqlite3

con = sqlite3.connect('gex.db')

cursor = con.execute('SELECT DISTINCT regime FROM trade_signals WHERE regime IS NOT NULL')
regimes = [row[0] for row in cursor.fetchall()]
print('Available regimes:')
for r in regimes:
    print(f'  {r}')

con.close()
