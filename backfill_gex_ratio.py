import sqlite3
import json

conn = sqlite3.connect('gex.db')

# Get all rows from gex_strike_window that need gex_ratio backfilled
rows = conn.execute("""
    SELECT ndate, ntime, data 
    FROM gex_strike_window 
    WHERE symbol='SPX'
    ORDER BY ndate, ntime
""").fetchall()

print(f"Found {len(rows)} rows to backfill")

updated = 0
for ndate, ntime, data_json in rows:
    strikes = json.loads(data_json)
    
    # Calculate gex_ratio using corrected formula (ratio of negative to positive gamma)
    positive_gex = sum(s.get("cg", 0) + s.get("pg", 0) for s in strikes if (s.get("cg", 0) + s.get("pg", 0)) > 0)
    negative_gex = abs(sum(s.get("cg", 0) + s.get("pg", 0) for s in strikes if (s.get("cg", 0) + s.get("pg", 0)) < 0))
    
    if negative_gex == 0:
        gex_ratio = 0
    elgex_ratio = calculate_all_aggregates(rows)["gex_ratio"] if positive_gex else 0  # Negative (red)
    
    # Update the row
    conn.execute(
        "UPDATE gex_strike_window SET gex_ratio=? WHERE ndate=? AND ntime=? AND symbol='SPX'",
        (gex_ratio, ndate, ntime)
    )
    updated += 1
    
    if updated % 100 == 0:
        print(f"Updated {updated} rows...")

conn.commit()
print(f"Backfill complete: {updated} rows updated")
conn.close()
