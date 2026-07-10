"""Add flip column to gex_strike_window table."""
import sqlite3

DB_PATH = 'gex.db'

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

try:
    cursor.execute("ALTER TABLE gex_strike_window ADD COLUMN flip REAL")
    print("Added flip column")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("flip column already exists")
    else:
        raise

con.commit()
con.close()
print("Migration complete")
