import sqlite3
import json

def extract_strike_window(strikes, uprice):
    """
    Extract 40 strikes around the SPX price.
    
    Rules:
    - Sort strikes by price
    - Find the strike closest to uprice
    - Take 20 strikes below and 20 above
    - If strike == uprice exactly, take 20 below + 1 at price + 19 above
    
    Args:
        strikes: List of strike dictionaries
        uprice: SPX price
        
    Returns:
        List of strike dictionaries (40 strikes)
    """
    if not strikes:
        return []
    
    # Sort strikes by price
    sorted_strikes = sorted(strikes, key=lambda r: r["strike"])
    
    # Find the index of the strike closest to uprice
    uprice_idx = min(range(len(sorted_strikes)), 
                     key=lambda i: abs(sorted_strikes[i]["strike"] - uprice))
    
    # Check if there's an exact match
    exact_match = sorted_strikes[uprice_idx]["strike"] == uprice
    
    if exact_match:
        # Take 20 below + 1 at price + 19 above
        start_idx = max(0, uprice_idx - 20)
        end_idx = min(len(sorted_strikes), uprice_idx + 20)
        window = sorted_strikes[start_idx:end_idx]
        
        # Ensure we have exactly 40 strikes if possible
        # If we have fewer than 40, take what we have
        # If we have more than 40, trim from the side with more room
        if len(window) > 40:
            # Trim to exactly 40
            if uprice_idx - start_idx >= 20 and end_idx - uprice_idx >= 19:
                # We have enough on both sides, take 20 below + 1 at price + 19 above
                window = sorted_strikes[uprice_idx - 20:uprice_idx + 20]
            elif uprice_idx - start_idx >= 20:
                # More room below, trim from top
                window = window[:40]
            else:
                # More room above, trim from bottom
                window = window[-40:]
    else:
        # Take 20 before and 20 after the closest strike
        start_idx = max(0, uprice_idx - 20)
        end_idx = min(len(sorted_strikes), uprice_idx + 21)
        window = sorted_strikes[start_idx:end_idx]
        
        # Ensure we have exactly 40 strikes if possible
        if len(window) > 40:
            window = window[:40]
    
    return window

def backfill_gex_strike_window():
    """Parse snapshot table and populate gex_strike_window with 40-strike window data."""
    
    con = sqlite3.connect('gex.db')
    cursor = con.cursor()
    
    # Get all snapshots with raw_json
    cursor.execute("""
        SELECT ndate, ntime, symbol, uprice, raw_json
        FROM snapshot
        WHERE raw_json IS NOT NULL
        ORDER BY ndate, ntime
    """)
    
    rows = cursor.fetchall()
    total = len(rows)
    processed = 0
    skipped = 0
    
    print(f"Found {total} snapshots to process")
    
    for ndate, ntime, symbol, uprice, raw_json in rows:
        try:
            data = json.loads(raw_json)
            
            # Handle both dict and list formats
            if isinstance(data, list):
                # Some records are stored as a list directly
                strikes = data
            elif isinstance(data, dict):
                strikes = data.get("data", [])
            else:
                skipped += 1
                continue
            
            if not strikes:
                skipped += 1
                continue
            
            # Extract 40-strike window
            window_strikes = extract_strike_window(strikes, uprice)
            
            if not window_strikes:
                skipped += 1
                continue
            
            # Insert into gex_strike_window - data column stores only the strikes array
            cursor.execute("""
                INSERT OR REPLACE INTO gex_strike_window (ndate, ntime, symbol, source, price, data)
                VALUES (?, ?, ?, 'gex', ?, ?)
            """, (ndate, ntime, symbol, uprice, json.dumps(window_strikes)))
            
            processed += 1
            
            if processed % 100 == 0:
                con.commit()
                print(f"Processed {processed}/{total} snapshots...")
                
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            skipped += 1
            print(f"Skipping {ndate}-{ntime} due to error: {e}")
            continue
    
    con.commit()
    con.close()
    
    print(f"\nBackfill complete:")
    print(f"  Processed: {processed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {total}")

if __name__ == "__main__":
    backfill_gex_strike_window()
