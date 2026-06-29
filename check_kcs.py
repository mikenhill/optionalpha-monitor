import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

ndate = 20260625
ntime = 1030

# Get original snapshot KCS
cursor.execute("""
    SELECT kcs, uprice
    FROM snapshot
    WHERE ndate=? AND ntime=? AND symbol='SPX'
""", (ndate, ntime))
row = cursor.fetchone()
if row:
    kcs_orig, uprice_orig = row
    print(f"=== Original Snapshot ===")
    print(f"kcs: {kcs_orig}")
    print(f"uprice: {uprice_orig}")

# Get gex_strike_window data
cursor.execute("""
    SELECT data, price
    FROM gex_strike_window
    WHERE ndate=? AND ntime=? AND source='gex'
""", (ndate, ntime))
row = cursor.fetchone()
if row:
    data, price = row
    strikes = json.loads(data)
    
    print(f"\n=== GEX Strike Window ===")
    print(f"price: {price}")
    
    # Find the strike closest to uprice
    sorted_strikes = sorted(strikes, key=lambda r: r["strike"])
    uprice_idx = min(range(len(sorted_strikes)), 
                     key=lambda i: abs(sorted_strikes[i]["strike"] - price))
    key_strike = sorted_strikes[uprice_idx]
    
    print(f"Key strike: {key_strike.get('strike')}")
    print(f"Key strike cg: {key_strike.get('cg'):,.2f}")
    print(f"Calculated KCS: {key_strike.get('cg', 0) or 0}")
    
    # Show a few strikes around the key strike
    print(f"\n=== Strikes around key strike ===")
    start = max(0, uprice_idx - 2)
    end = min(len(sorted_strikes), uprice_idx + 3)
    for i in range(start, end):
        s = sorted_strikes[i]
        marker = " <-- KEY" if i == uprice_idx else ""
        print(f"Strike {s.get('strike')}: cg={s.get('cg'):,.2f}, pg={s.get('pg'):,.2f}{marker}")

con.close()
