import json, sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "gex.db"

con = sqlite3.connect(DB)

# What ntimes exist for 20260622?
rows = con.execute(
    "SELECT ntime, uprice, length(data) FROM gex_snapshots WHERE ndate=20260622 ORDER BY ntime"
).fetchall()
print(f"20260622 snapshots: {len(rows)}")
for r in rows:
    print(f"  ntime={r[0]:04d}  uprice={r[1]}  data_len={r[2]}")

# Compare with a known-good date (most recent before 20260622)
rows2 = con.execute(
    "SELECT ndate, ntime, uprice, length(data) FROM gex_snapshots WHERE ndate<20260622 ORDER BY ndate DESC, ntime DESC LIMIT 5"
).fetchall()
print(f"\nMost recent prior snapshots:")
for r in rows2:
    print(f"  ndate={r[0]} ntime={r[1]:04d}  uprice={r[2]}  data_len={r[3]}")

# Check what the api/snapshot endpoint would return for 20260622 at each time
# Simulate load_gex_snapshot
print("\n--- Checking snapshot data structure for 20260622 ---")
for ntime in [930, 1000, 1530]:
    row = con.execute(
        "SELECT uprice, data FROM gex_snapshots WHERE ndate=20260622 AND ntime=?", (ntime,)
    ).fetchone()
    if row:
        data = json.loads(row[1])
        strikes = [r.get("strike") for r in data[:3]]
        keys = list(data[0].keys()) if data else []
        print(f"  ntime={ntime:04d}  uprice={row[0]}  rows={len(data)}  keys={keys}  first_strikes={strikes}")
    else:
        print(f"  ntime={ntime:04d}  NOT FOUND")

con.close()
