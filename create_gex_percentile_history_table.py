"""Create gex_percentile_history table for time-slot specific percentiles."""
import sqlite3

DB_PATH = 'gex.db'

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Create the table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS gex_percentile_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ndate           INTEGER NOT NULL,
        ntime           INTEGER NOT NULL,
        metric_name     TEXT NOT NULL,
        value           REAL NOT NULL,
        percentile      REAL NOT NULL,
        UNIQUE(ndate, ntime, metric_name)
    )
""")

# Add indexes for query performance
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_gex_percentile_history_metric "
    "ON gex_percentile_history (metric_name, ndate, ntime)"
)

cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_gex_percentile_history_ntime "
    "ON gex_percentile_history (ntime)"
)

con.commit()
con.close()
print("gex_percentile_history table created successfully")
