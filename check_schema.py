import sqlite3

con = sqlite3.connect(r'G:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
tables = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for (tname,) in tables:
    cols = con.execute(f"PRAGMA table_info({tname})").fetchall()
    count = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
    print(f"\n=== {tname} ({count} rows) ===")
    for col in cols:
        print(f"  {col[1]:30s} {col[2]:20s} {'NOT NULL' if col[3] else ''} {'PK' if col[5] else ''}")
con.close()
