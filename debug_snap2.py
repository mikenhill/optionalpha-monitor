import sys
sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
import sqlite3, json
from pathlib import Path

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row

row = con.execute(
    "SELECT ntime, uprice, data FROM gex_snapshots WHERE ndate=20260618 AND ntime=930 AND symbol='SPX'"
).fetchone()
ntime, uprice, data_json = row['ntime'], row['uprice'], row['data']
strike_rows = json.loads(data_json)
con.close()

# Simulate what load_gex_snapshot returns
data = {"symbol": "SPX", "ndate": 20260618, "ntime": ntime, "uprice": uprice, "data": strike_rows}

# Import the actual functions
from gex_viewer import summarise_snapshot, _compute_key_strike_stats

snap = summarise_snapshot(data)
print("summarise_snapshot result:")
for k, v in snap.items():
    print(f"  {k}: {v}")

ks = _compute_key_strike_stats(
    [r for r in strike_rows if r.get('strike') is not None],
    snap.get('uprice', 0)
)
print("\n_compute_key_strike_stats result:")
for k, v in ks.items():
    print(f"  {k}: {v}")
