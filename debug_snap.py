import sqlite3, json
from pathlib import Path

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
con = sqlite3.connect(str(DB))

ndate = 20260618
rows = con.execute(
    "SELECT ntime, uprice FROM gex_snapshots WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
    (ndate,)
).fetchall()
print(f"gex_snapshots rows for {ndate}: {len(rows)}")

# Pick 930 row and inspect the data
row = con.execute(
    "SELECT ntime, uprice, data FROM gex_snapshots WHERE ndate=? AND ntime=930 AND symbol='SPX'",
    (ndate,)
).fetchone()
if row:
    ntime, uprice, data_json = row
    data = json.loads(data_json)
    if isinstance(data, list):
        sample = data[:2]
    elif isinstance(data, dict):
        sample = list(data.items())[:5]
    else:
        sample = data
    print(f"\nntime={ntime}  uprice={uprice}")
    print(f"data type: {type(data).__name__}  len: {len(data) if hasattr(data,'__len__') else 'N/A'}")
    print(f"\nFirst 2 strike rows:")
    for s in (data[:2] if isinstance(data, list) else []):
        print(f"  {s}")
    print(f"\nAll keys in first strike row:")
    if isinstance(data, list) and data:
        print(f"  {list(data[0].keys())}")
else:
    print("No 930 row found")

# Also check histgex JSON file directly
hist_dir = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\results\histgex\20260618')
if hist_dir.exists():
    files = sorted(hist_dir.glob("*.json"))
    print(f"\nHistgex files: {[f.name for f in files[:5]]}")
    if files:
        d = json.loads(files[0].read_text())
        print(f"JSON top-level keys: {list(d.keys())}")
        rows_data = d.get('data') or d
        if isinstance(rows_data, list) and rows_data:
            print(f"Strike row keys: {list(rows_data[0].keys())}")
            print(f"Sample row: {rows_data[0]}")
else:
    print(f"\nNo histgex dir for 20260618")

con.close()
