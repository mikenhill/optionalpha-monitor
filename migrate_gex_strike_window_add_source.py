import sqlite3
import json

def migrate_gex_strike_window():
    """Add source column to gex_strike_window and update primary key."""
    
    con = sqlite3.connect('gex.db')
    cursor = con.cursor()
    
    # Step 1: Export existing data
    print("Exporting existing data...")
    cursor.execute("SELECT ndate, ntime, symbol, price, data FROM gex_strike_window")
    existing_data = cursor.fetchall()
    print(f"Exported {len(existing_data)} records")
    
    # Step 2: Drop old table
    print("Dropping old table...")
    cursor.execute("DROP TABLE IF EXISTS gex_strike_window")
    
    # Step 3: Create new table with source column
    print("Creating new table with source column...")
    cursor.execute("""
        CREATE TABLE gex_strike_window (
            ndate INTEGER NOT NULL,
            ntime INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'gex',
            price REAL NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (ndate, ntime, symbol, source)
        )
    """)
    
    # Step 4: Re-create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gex_strike_window_ndate 
        ON gex_strike_window(ndate)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gex_strike_window_symbol 
        ON gex_strike_window(symbol)
    """)
    
    # Step 5: Re-import data with source='gex'
    print("Re-importing data with source='gex'...")
    for ndate, ntime, symbol, price, data in existing_data:
        cursor.execute("""
            INSERT INTO gex_strike_window (ndate, ntime, symbol, source, price, data)
            VALUES (?, ?, ?, 'gex', ?, ?)
        """, (ndate, ntime, symbol, price, data))
    
    con.commit()
    con.close()
    
    print("Migration complete!")

if __name__ == "__main__":
    migrate_gex_strike_window()
