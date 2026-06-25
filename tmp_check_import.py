import json, sqlite3, traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GEX_DIR  = BASE_DIR / "results" / "histgex"
DB_PATH  = BASE_DIR / "gex.db"

files = sorted(GEX_DIR.glob("**/*_histgex.json"))
print(f"Files found: {len(files)}")
if not files:
    print("No files — check GEX_DIR path")
    exit(1)

f = files[0]
print(f"First file: {f.name}")
raw = json.loads(f.read_text(encoding="utf-8"))
parts = f.stem.split("_")
print(f"Stem parts: {parts}")
print(f"uprice: {raw.get('uprice')}  data rows: {len(raw.get('data') or [])}")

# Try a small import
con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA journal_mode=WAL")
con.execute("""
    CREATE TABLE IF NOT EXISTS gex_snapshots (
        ndate INTEGER NOT NULL, ntime INTEGER NOT NULL, symbol TEXT NOT NULL DEFAULT 'SPX',
        uprice REAL, data TEXT, PRIMARY KEY (ndate, ntime, symbol)
    )
""")

inserted = 0
errors = 0
for f in files[:20]:
    try:
        raw   = json.loads(f.read_text(encoding="utf-8"))
        parts = f.stem.split("_")
        ndate = int(parts[0])
        ntime = int(parts[1])
        sym   = parts[2] if len(parts) > 2 else "SPX"
        data  = raw.get("data") or []
        if not data:
            continue
        cur = con.execute(
            "INSERT OR IGNORE INTO gex_snapshots (ndate,ntime,symbol,uprice,data) VALUES (?,?,?,?,?)",
            (ndate, ntime, sym, raw.get("uprice", 0), json.dumps(data))
        )
        inserted += cur.rowcount
    except Exception as e:
        errors += 1
        print(f"  ERROR {f.name}: {e}")
        traceback.print_exc()

con.commit()
print(f"Test: inserted={inserted} errors={errors}")
con.close()
