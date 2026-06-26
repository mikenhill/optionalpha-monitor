import sqlite3

con = sqlite3.connect('gex.db')

print('=== gex_snapshots table schema ===')
cursor = con.execute('PRAGMA table_info(gex_snapshots)')
for row in cursor.fetchall():
    print(f'  {row[1]} ({row[2]})')

con.close()
