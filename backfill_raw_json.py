import sqlite3
import json
from pathlib import Path

DB_PATH = "gex.db"

con = sqlite3.connect(DB_PATH)

# Build mapping from (ndate, ntime) to file path
file_mapping = {}

# Process histgex files
histgex_dir = Path('results/histgex')
if histgex_dir.exists():
    histgex_files = list(histgex_dir.rglob('*_histgex.json'))
    print(f"Found {len(histgex_files)} histgex files")
    
    for f in histgex_files:
        # Parse filename: 20260618_0930_SPX_histgex.json
        parts = f.stem.split('_')
        if len(parts) >= 3:
            ndate = int(parts[0])
            ntime = int(parts[1])
            file_mapping[(ndate, ntime)] = f

# Process gex files (live captures)
results_dir = Path('results')
gex_files = list(results_dir.glob('*_SPX_SPX_*.json'))
gex_files = [f for f in gex_files if 'gex_summary' not in f.name and 'gex_window' not in f.name]
print(f"Found {len(gex_files)} gex files")

for f in gex_files:
    # Parse filename: 20260602_131143_SPX_SPX_20260602.json
    parts = f.stem.split('_')
    if len(parts) >= 5:
        ndate = int(parts[0])
        # Extract time (HHMM) from timestamp (HHMMSS)
        timestamp = parts[1]
        ntime = int(timestamp[:4]) if len(timestamp) >= 4 else int(timestamp)
        file_mapping[(ndate, ntime)] = f

print(f"Total file mappings: {len(file_mapping)}")

# Find snapshots with NULL raw_json
cursor = con.execute("""
    SELECT ndate, ntime 
    FROM gex_snapshots 
    WHERE symbol='SPX' AND raw_json IS NULL
""")
rows = cursor.fetchall()

print(f"Found {len(rows)} snapshots with NULL raw_json")

updated = 0
skipped = 0
for ndate, ntime in rows:
    key = (ndate, ntime)
    if key in file_mapping:
        try:
            file_path = file_mapping[key]
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # For histgex files, the content is the raw API response
            # For gex files, need to extract the market.gex data
            if 'histgex' in file_path.name:
                raw_json = content
            else:
                # Parse the gex file structure
                data = json.loads(content)
                # Extract the market.gex response
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('api') == 'market.gex':
                            raw_json = json.dumps(item.get('data', {}))
                            break
                    else:
                        raw_json = content
                else:
                    raw_json = content
            
            con.execute("""
                UPDATE gex_snapshots 
                SET raw_json = ?
                WHERE ndate=? AND ntime=? AND symbol='SPX'
            """, (raw_json, ndate, ntime))
            
            updated += 1
            if updated % 100 == 0:
                print(f"Updated {updated} snapshots...")
                con.commit()
        except Exception as e:
            print(f"Error updating {ndate} {ntime}: {e}")
            skipped += 1
    else:
        skipped += 1

con.commit()
print(f"Backfill complete. Updated {updated} snapshots, skipped {skipped} (no matching file).")
con.close()
