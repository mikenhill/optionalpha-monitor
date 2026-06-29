import sqlite3

def create_gex_strike_window_table():
    """Create the gex_strike_window table with composite primary key."""
    
    con = sqlite3.connect('gex.db')
    cursor = con.cursor()
    
    # Create the table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gex_strike_window (
            ndate INTEGER NOT NULL,
            ntime INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (ndate, ntime, symbol)
        )
    """)
    
    # Add indexes for query performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gex_strike_window_ndate 
        ON gex_strike_window(ndate)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gex_strike_window_symbol 
        ON gex_strike_window(symbol)
    """)
    
    con.commit()
    con.close()
    
    print("Created gex_strike_window table successfully")

if __name__ == "__main__":
    create_gex_strike_window_table()
