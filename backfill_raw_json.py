"""Backfill raw_json for snapshots that have NULL raw_json.

This script reads the list of missing snapshots from missing_raw_json_list.txt
and fetches the data from OptionAlpha one by one to avoid rate limiting.
"""

import json
import sqlite3
import time
from datetime import datetime

from optionalpha_client import fetch_market_data

def format_xid(date_str, ntime):
    """Format date and time into OptionAlpha xid format.
    
    Example: 2026-06-25, 1000 -> SPX_20260625_1000
    """
    ndate = date_str.replace("-", "")
    return f"SPX_{ndate}_{ntime}"

def backfill_snapshot(date_str, ntime):
    """Backfill a single snapshot from OptionAlpha."""
    xid = format_xid(date_str, ntime)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching {date_str} {ntime} (xid: {xid})...")
    
    try:
        # Fetch data from OptionAlpha
        response = fetch_market_data(symbol="SPX", xid=xid)
        
        # Extract the GEX data (second item in the response array)
        if len(response) < 2:
            print(f"  ERROR: Invalid response format")
            return False
        
        gex_data = response[1]
        if gex_data.get("t") != "rpc" or "result" not in gex_data:
            print(f"  ERROR: No GEX data in response")
            return False
        
        result = gex_data["result"]
        if not result:
            print(f"  ERROR: Empty result")
            return False
        
        # Extract the raw JSON data
        raw_json = json.dumps(result)
        
        # Update database
        ndate = int(date_str.replace("-", ""))
        con = sqlite3.connect('gex.db')
        con.execute(
            'UPDATE snapshot SET raw_json=? WHERE ndate=? AND ntime=? AND symbol="SPX"',
            (raw_json, ndate, ntime)
        )
        con.commit()
        con.close()
        
        print(f"  SUCCESS: Updated raw_json (length: {len(raw_json)})")
        return True
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    # Read list of missing snapshots
    with open('missing_raw_json_list.txt', 'r') as f:
        lines = f.readlines()
    
    snapshots = []
    for line in lines:
        line = line.strip()
        if line:
            date_str, ntime = line.split(',')
            snapshots.append((date_str, int(ntime)))
    
    print(f"Found {len(snapshots)} snapshots to backfill\n")
    
    # Process each snapshot
    success_count = 0
    for i, (date_str, ntime) in enumerate(snapshots, 1):
        print(f"\n[{i}/{len(snapshots)}]", end=" ")
        
        if backfill_snapshot(date_str, ntime):
            success_count += 1
        
        # Delay between requests to avoid rate limiting
        if i < len(snapshots):
            print(f"  Waiting 5 seconds before next request...")
            time.sleep(5)
    
    print(f"\n\nBackfill complete: {success_count}/{len(snapshots)} successful")

if __name__ == "__main__":
    main()
