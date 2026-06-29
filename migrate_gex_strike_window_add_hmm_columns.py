"""Add hmm_state and hmm_label columns to gex_strike_window table."""
import sqlite3

DB_PATH = 'gex.db'

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Add hmm_state column
try:
    cursor.execute("ALTER TABLE gex_strike_window ADD COLUMN hmm_state INTEGER")
    print("Added hmm_state column")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("hmm_state column already exists")
    else:
        raise

# Add hmm_label column
try:
    cursor.execute("ALTER TABLE gex_strike_window ADD COLUMN hmm_label TEXT")
    print("Added hmm_label column")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("hmm_label column already exists")
    else:
        raise

con.commit()
con.close()
print("Migration complete")
