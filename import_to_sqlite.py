import sqlite3
import json
from pathlib import Path
import sys

DB_FILE = "gex.db"
RESULTS_DIR = Path("results")


def main():
    """Migrate all histgex and livegex JSON files to a new SQLite database."""
    db_path = Path(DB_FILE)
    if db_path.exists():
        print(f"Database '{DB_FILE}' already exists. Please remove it to re-import.")
        return 1

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    # Create schema
    cur.execute("""
        CREATE TABLE snapshots (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL, -- 'histgex' or 'livegex'
            date TEXT NOT NULL,
            ntime INTEGER NOT NULL,
            uprice REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, date, ntime)
        )
    """)
    cur.execute("""
        CREATE TABLE gex_data (
            snapshot_id INTEGER NOT NULL,
            strike REAL NOT NULL,
            cg REAL, -- call_gex
            pg REAL, -- put_gex
            net REAL, -- net_gex
            coi REAL, -- call_oi
            poi REAL, -- put_oi
            cvol REAL, -- call_vol
            pvol REAL, -- put_vol
            FOREIGN KEY (snapshot_id) REFERENCES snapshots (id)
        )
    """)
    print("Database schema created.")

    # Import data
    hist_count = import_source(cur, "histgex")
    live_count = import_source(cur, "livegex")

    con.commit()
    con.close()

    print("\nImport complete.")
    print(f"  - Imported {hist_count} snapshots from histgex.")
    print(f"  - Imported {live_count} snapshots from livegex.")
    print(f"Database saved to '{DB_FILE}'.")
    return 0

def import_source(cur: sqlite3.Cursor, source: str) -> int:
    """Scan a source directory and import all JSON files into the database."""
    source_dir = RESULTS_DIR / source
    if not source_dir.is_dir():
        print(f"Source directory '{source_dir}' not found, skipping.")
        return 0

    print(f"\nImporting from '{source}'...")
    count = 0
    files = sorted(list(source_dir.glob("**/*.json")))
    for i, f in enumerate(files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            date_iso = f.parts[-2].replace("-", "")
            ntime = int(f.stem.split("_")[1])
            uprice = data.get("uprice")

            # Insert snapshot record
            cur.execute(
                "INSERT INTO snapshots (source, date, ntime, uprice) VALUES (?, ?, ?, ?)",
                (source, date_iso, ntime, uprice)
            )
            snapshot_id = cur.lastrowid

            # Insert GEX data rows
            rows_to_insert = []
            for row in data.get("data", []):
                if row.get("strike") is not None:
                    rows_to_insert.append((
                        snapshot_id,
                        row["strike"],
                        row.get("cg"),
                        row.get("pg"),
                        row.get("net"),
                        row.get("coi"),
                        row.get("poi"),
                        row.get("cvol"),
                        row.get("pvol"),
                    ))
            
            cur.executemany(
                "INSERT INTO gex_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows_to_insert
            )
            count += 1
            print(f"  [{i+1}/{len(files)}] Imported {f.relative_to(RESULTS_DIR)}", end='\r')
        except Exception as e:
            print(f"\nError processing {f}: {e}")

    return count

if __name__ == "__main__":
    sys.exit(main())
