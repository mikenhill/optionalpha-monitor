import sqlite3
import csv
from pathlib import Path

DB_PATH = Path(__file__).parent / "gex.db"
OUTPUT_PATH = Path(__file__).parent / "snapshot_classification_report.csv"

def classify_snapshot(ntime, db_source):
    """Classify snapshot as Live/Historical and Pre-Market/In-Market."""
    # CRITICAL RULE: Two API Data Structures
    # market.gex (live): Has 'last' field, NO 'uprice'
    # market.histgex (historical): Has 'uprice' field, NO 'last'
    # Classification based on DB source field:
    # - source='gex' → Live (market.gex)
    # - source='histgex' → Historical (market.histgex)
    
    if db_source == 'gex':
        source = "Live"
    elif db_source == 'histgex':
        source = "Historical"
    else:
        source = f"Unknown ({db_source})"
    
    # Check if pre-market (before 09:30)
    if ntime < 930:
        market = "Pre-Market"
    else:
        market = "In-Market"
    
    return source, market

con = sqlite3.connect(DB_PATH)

# Query all snapshots
cursor = con.execute("""
    SELECT ndate, ntime, symbol, is_premarket, source
    FROM gex_snapshots
    WHERE symbol='SPX'
    ORDER BY ndate DESC, ntime
""")

rows = cursor.fetchall()

# Write CSV report
with open(OUTPUT_PATH, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Date', 'Time', 'Symbol', 'Source (Live/Historical)', 'Market (Pre-Market/In-Market)', 'is_premarket (DB)', 'source (DB)'])
    
    for ndate, ntime, symbol, is_premarket, db_source in rows:
        source, market = classify_snapshot(ntime, db_source)
        
        # Format date
        date_str = f"{ndate//10000}-{(ndate%10000)//100:02d}-{ndate%100:02d}"
        
        # Format time
        time_str = f"{ntime//100:02d}:{ntime%100:02d}"
        
        writer.writerow([date_str, time_str, symbol, source, market, is_premarket, db_source])

con.close()

print(f"Report generated: {OUTPUT_PATH}")
print(f"Total snapshots: {len(rows)}")
