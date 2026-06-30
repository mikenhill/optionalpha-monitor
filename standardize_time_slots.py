"""
Standardize time slots in gex_strike_window to conform to RTH standard:
935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555

Mapping for non-standard time slots:
- 930 -> 935
- 931 -> 935
- 1032 -> 1030
- 1058 -> 1100
- 1117 -> 1130
- 1134 -> 1130
- 1135 -> 1130
"""

import sqlite3

# Define mapping from non-standard to standard time slots
TIME_SLOT_MAPPING = {
    930: 935,
    931: 935,
    1032: 1030,
    1058: 1100,
    1117: 1130,
    1134: 1130,
    1135: 1130,
}

def standardize_time_slots():
    con = sqlite3.connect('gex.db')
    
    # Show current state
    print("Current time slots before standardization:")
    rows = con.execute('SELECT DISTINCT ntime FROM gex_strike_window WHERE symbol="SPX" AND source="gex" ORDER BY ntime').fetchall()
    print([r[0] for r in rows])
    
    # Count records to be updated
    total_updates = 0
    for old_ntime, new_ntime in TIME_SLOT_MAPPING.items():
        count = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=? AND symbol="SPX" AND source="gex"', (old_ntime,)).fetchone()[0]
        if count > 0:
            print(f"  {old_ntime} -> {new_ntime}: {count} records")
            total_updates += count
    
    if total_updates == 0:
        print("No records need updating.")
        return
    
    print(f"\nTotal records to update: {total_updates}")
    
    # Perform updates
    for old_ntime, new_ntime in TIME_SLOT_MAPPING.items():
        con.execute(
            'UPDATE gex_strike_window SET ntime=? WHERE ntime=? AND symbol="SPX" AND source="gex"',
            (new_ntime, old_ntime)
        )
    
    con.commit()
    print("Time slot standardization complete.")
    
    # Show new state
    print("\nTime slots after standardization:")
    rows = con.execute('SELECT DISTINCT ntime FROM gex_strike_window WHERE symbol="SPX" AND source="gex" ORDER BY ntime').fetchall()
    print([r[0] for r in rows])
    
    # Count records per time slot
    print("\nRecords per time slot:")
    for row in rows:
        ntime = row[0]
        count = con.execute('SELECT COUNT(*) FROM gex_strike_window WHERE ntime=? AND symbol="SPX" AND source="gex"', (ntime,)).fetchone()[0]
        print(f'  {ntime}: {count} records')
    
    con.close()

if __name__ == '__main__':
    standardize_time_slots()
