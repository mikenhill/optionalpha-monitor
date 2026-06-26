import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "gex.db"

con = sqlite3.connect(DB_PATH)

# Update source field based on time
# Half-hour boundary (00 or 30 minutes) = histgex (Historical)
# Otherwise = gex (Live)

cursor = con.execute("""
    UPDATE gex_snapshots
    SET source = 'gex'
    WHERE symbol='SPX'
    AND source = 'histgex'
    AND (ntime % 100) NOT IN (0, 30)
""")

updated = cursor.rowcount
con.commit()

print(f"Updated {updated} rows to source='gex' (Live)")

# Verify the changes
cursor = con.execute("""
    SELECT source, COUNT(*)
    FROM gex_snapshots
    WHERE symbol='SPX'
    GROUP BY source
""")
print("\nSource distribution:")
for source, count in cursor.fetchall():
    print(f"  {source}: {count}")

con.close()
