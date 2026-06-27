"""Identify snapshots with NULL raw_json that need backfilling."""

import sqlite3

def main():
    con = sqlite3.connect('gex.db')
    
    # Get all snapshots with NULL raw_json for SPX
    rows = con.execute(
        'SELECT ndate, ntime FROM snapshot WHERE raw_json IS NULL AND symbol="SPX" ORDER BY ndate, ntime'
    ).fetchall()
    
    print(f"Found {len(rows)} snapshots with NULL raw_json\n")
    print("Date (YYYY-MM-DD), Time (HHMM)")
    print("=" * 40)
    
    for ndate, ntime in rows:
        ndate_str = str(ndate)
        date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
        print(f"{date_str}, {ntime}")
    
    # Also save to file for backfill script
    with open('missing_raw_json_list.txt', 'w') as f:
        for ndate, ntime in rows:
            ndate_str = str(ndate)
            date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
            f.write(f"{date_str},{ntime}\n")
    
    print(f"\nList saved to missing_raw_json_list.txt")
    con.close()

if __name__ == "__main__":
    main()
