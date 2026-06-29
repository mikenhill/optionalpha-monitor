import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

ndate = 20260625
ntime = 1030

# Get original snapshot gex_ratio
cursor.execute("""
    SELECT gex_ratio, total_call_gex, total_put_gex
    FROM snapshot
    WHERE ndate=? AND ntime=? AND symbol='SPX'
""", (ndate, ntime))
row = cursor.fetchone()
if row:
    gex_ratio_orig, call_gex_orig, put_gex_orig = row
    print(f"=== Original Snapshot ===")
    print(f"gex_ratio: {gex_ratio_orig}")
    print(f"call_gex: {call_gex_orig:,.2f}")
    print(f"put_gex: {put_gex_orig:,.2f}")
    
    # Calculate expected ratio based on user's formula
    if call_gex_orig > abs(put_gex_orig):
        expected_ratio = round(call_gex_orig / abs(put_gex_orig), 1)
    else:
        expected_ratio = round(-abs(put_gex_orig) / call_gex_orig, 1)
    print(f"Expected ratio (user formula): {expected_ratio}")

# Get gex_strike_window data
cursor.execute("""
    SELECT data
    FROM gex_strike_window
    WHERE ndate=? AND ntime=? AND source='gex'
""", (ndate, ntime))
row = cursor.fetchone()
if row:
    data = row[0]
    strikes = json.loads(data)
    
    call_gex = sum(r.get("cg", 0) or 0 for r in strikes)
    put_gex = sum(r.get("pg", 0) or 0 for r in strikes)
    
    print(f"\n=== GEX Strike Window ===")
    print(f"call_gex: {call_gex:,.2f}")
    print(f"put_gex: {put_gex:,.2f}")
    
    # Current calculation
    if call_gex > put_gex:
        current_ratio = round(call_gex / put_gex, 1) if put_gex else 0
    else:
        current_ratio = round(-put_gex / call_gex, 1) if call_gex else 0
    print(f"Current ratio (our function): {current_ratio}")
    
    # Expected calculation based on user's formula
    if call_gex > abs(put_gex):
        expected_ratio = round(call_gex / abs(put_gex), 1)
    else:
        expected_ratio = round(-abs(put_gex) / call_gex, 1)
    print(f"Expected ratio (user formula): {expected_ratio}")

con.close()
