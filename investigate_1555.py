"""
Investigate why 1555 time slot only has 1 record instead of ~120 like other RTH slots.
"""

import sqlite3

def investigate_1555():
    con = sqlite3.connect('gex.db')
    
    # Show 1555 records
    print("Records at 1555:")
    rows = con.execute('SELECT ndate, ntime, price FROM gex_strike_window WHERE ntime=1555 AND symbol="SPX" AND source="gex" ORDER BY ndate').fetchall()
    print(f"Found {len(rows)} records at 1555")
    for row in rows:
        print(f"  {row[0]}: {row[2]}")
    
    # Show 1530 records for comparison
    print("\nRecords at 1530 (for comparison):")
    rows_1530 = con.execute('SELECT ndate, ntime, price FROM gex_strike_window WHERE ntime=1530 AND symbol="SPX" AND source="gex" ORDER BY ndate').fetchall()
    print(f"Found {len(rows_1530)} records at 1530")
    print(f"First 5: {rows_1530[:5]}")
    print(f"Last 5: {rows_1530[-5:]}")
    
    # Check if 1555 data exists in other time slots
    print("\nChecking if 1555 data might be in 1530 or other slots...")
    
    # Get dates that have 1530 but not 1555
    dates_1530 = set(r[0] for r in rows_1530)
    dates_1555 = set(r[0] for r in rows)
    missing_dates = dates_1530 - dates_1555
    print(f"Dates with 1530 but missing 1555: {len(missing_dates)}")
    if len(missing_dates) <= 10:
        print(f"  {sorted(missing_dates)}")
    
    con.close()

if __name__ == '__main__':
    investigate_1555()
