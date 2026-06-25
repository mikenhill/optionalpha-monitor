import sqlite3
from pathlib import Path

db = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
con = sqlite3.connect(str(db))
tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for (t,) in tables:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {n} rows")
con.close()
print("DB size:", round(db.stat().st_size / 1024 / 1024, 1), "MB")
