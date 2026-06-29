import sqlite3
import json

con = sqlite3.connect('gex.db')
cursor = con.cursor()

# Check the structure of a few gex_strike_window records
cursor.execute("""
    SELECT ndate, ntime, symbol, price, data
    FROM gex_strike_window
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    ndate, ntime, symbol, price, data = row
    print(f"=== Sample gex_strike_window record ===")
    print(f"ndate: {ndate}, ntime: {ntime}, symbol: {symbol}, price: {price}")
    
    strikes = json.loads(data)
    if len(strikes) > 0:
        print(f"\nFirst strike keys: {strikes[0].keys()}")
        print(f"\nFirst strike data:")
        for key, value in strikes[0].items():
            print(f"  {key}: {value}")

con.close()
