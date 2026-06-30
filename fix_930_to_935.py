"""
Update only 930 time slot to 935 (120 records)
This is a historical data correction to conform to RTH standard.
Processes 10 records at a time with progress commentary.
"""

import sqlite3

def update_930_to_935():
    con = sqlite3.connect('gex.db')
    
    # Show current state
    print("Current 930 time slot records:")
    rows = con.execute('SELECT ndate, ntime FROM gex_strike_window WHERE ntime=930 AND symbol="SPX" AND source="gex" ORDER BY ndate').fetchall()
    print(f"Found {len(rows)} records at 930")
    
    if len(rows) == 0:
        print("No records at 930 to update.")
        return
    
    # Check if 935 already has data
    existing_935 = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=935 AND symbol="SPX" AND source="gex"').fetchone()[0]
    print(f"Existing records at 935: {existing_935}")
    
    if existing_935 > 0:
        print("WARNING: 935 already has data. This will create duplicates.")
        print(f"Existing 935 records: {existing_935}")
        print("Proceeding with update (will merge with existing data)...")
    
    # Process in batches of 10
    batch_size = 10
    total_updated = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}: {len(batch)} records")
        for row in batch:
            ndate = row[0]
            con.execute(
                'UPDATE gex_strike_window SET ntime=935 WHERE ndate=? AND ntime=930 AND symbol="SPX" AND source="gex"',
                (ndate,)
            )
            total_updated += 1
            print(f"  Updated {ndate} from 930 to 935")
        con.commit()
        print(f"Batch complete. Total updated so far: {total_updated}/{len(rows)}")
    
    print(f"\nFinal: Updated {total_updated} records from 930 to 935")
    
    # Verify
    new_930 = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=930 AND symbol="SPX" AND source="gex"').fetchone()[0]
    new_935 = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=935 AND symbol="SPX" AND source="gex"').fetchone()[0]
    print(f"Records at 930 after update: {new_930}")
    print(f"Records at 935 after update: {new_935}")
    
    con.close()

if __name__ == '__main__':
    update_930_to_935()
