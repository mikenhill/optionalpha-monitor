import sqlite3
import json
from collections import defaultdict

conn = sqlite3.connect('gex.db')

def count_price_crosses(ndate, strike_price):
    """Count how many times price crosses a strike during the day"""
    price_rows = conn.execute("""
        SELECT price 
        FROM gex_strike_window 
        WHERE ndate=? AND symbol='SPX' AND ntime >= 930
        ORDER BY ntime
    """, (ndate,)).fetchall()
    
    if not price_rows:
        return 0
    
    prices = [r[0] for r in price_rows]
    crosses = 0
    prev_price = prices[0]
    for p in prices[1:]:
        if (prev_price < strike_price <= p) or (prev_price > strike_price >= p):
            crosses += 1
        prev_price = p
    return crosses

def detect_pin_magnet_day(ndate, ntime=1400):
    """Detect if a day has a pin/magnet strike pattern"""
    # Get snapshot at specified time
    rows = conn.execute("""
        SELECT ndate, ntime, price, data 
        FROM gex_strike_window 
        WHERE ndate=? AND ntime=? AND symbol='SPX'
    """, (ndate, ntime)).fetchall()
    
    if not rows:
        return None
    
    ndate, ntime, price, data_json = rows[0]
    strikes = json.loads(data_json)
    
    # Analyze strikes
    strike_data = []
    for s in strikes:
        call_gex = s.get('cg', 0)
        put_gex = s.get('pg', 0)
        total_abs = s.get('abs', 0)
        call_oi = s.get('coi', 0)
        put_oi = s.get('poi', 0)
        
        gex_ratio = abs(call_gex / put_gex) if put_gex != 0 else None
        oi_ratio = call_oi / put_oi if put_oi > 0 else None
        
        strike_data.append({
            'strike': s['strike'],
            'call_gex': call_gex,
            'put_gex': put_gex,
            'total_abs': total_abs,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'gex_ratio': gex_ratio,
            'oi_ratio': oi_ratio,
            'distance_from_price': abs(s['strike'] - price)
        })
    
    # Sort by total absolute gamma (descending)
    strike_data.sort(key=lambda x: x['total_abs'], reverse=True)
    
    if len(strike_data) < 2:
        return None
    
    top_strike = strike_data[0]
    second_strike = strike_data[1]
    
    # Detection criteria:
    # 1. Dominance: Top strike must have at least 3x the absolute gamma of second strike
    dominance_ratio = top_strike['total_abs'] / second_strike['total_abs'] if second_strike['total_abs'] > 0 else 0
    
    # 2. Balance: GEX ratio between 0.7 and 1.5 (relatively balanced)
    gex_ratio = top_strike['gex_ratio']
    is_balanced = gex_ratio and 0.7 <= gex_ratio <= 1.5
    
    # 3. Price oscillation: Price must cross the strike at least 2 times during the day
    crosses = count_price_crosses(ndate, top_strike['strike'])
    
    # 4. Proximity: Strike must be within 50 points of the snapshot price
    is_nearby = top_strike['distance_from_price'] <= 50
    
    if dominance_ratio >= 3.0 and is_balanced and crosses >= 2 and is_nearby:
        return {
            'date': ndate,
            'time': ntime,
            'price': price,
            'strike': top_strike['strike'],
            'total_abs': top_strike['total_abs'],
            'call_gex': top_strike['call_gex'],
            'put_gex': top_strike['put_gex'],
            'gex_ratio': top_strike['gex_ratio'],
            'oi_ratio': top_strike['oi_ratio'],
            'dominance_ratio': dominance_ratio,
            'crosses': crosses,
            'distance': top_strike['distance_from_price']
        }
    
    return None

# Get all unique dates
dates = conn.execute("""
    SELECT DISTINCT ndate FROM gex_strike_window 
    WHERE symbol='SPX' AND ntime >= 930
    ORDER BY ndate
""").fetchall()

print(f"Scanning {len(dates)} dates for pin/magnet patterns...")
print()

pin_magnet_days = []
for (ndate,) in dates:
    result = detect_pin_magnet_day(ndate)
    if result:
        pin_magnet_days.append(result)
        print(f"✓ {ndate}: Strike {result['strike']} (dominance={result['dominance_ratio']:.1f}x, crosses={result['crosses']}, gex_ratio={result['gex_ratio']:.2f})")

print()
print(f"Found {len(pin_magnet_days)} pin/magnet days")
print("=" * 120)
print()

if pin_magnet_days:
    for day in pin_magnet_days:
        print(f"Date: {day['date']}")
        print(f"  Strike: {day['strike']}")
        print(f"  Price at snapshot: {day['price']}")
        print(f"  Total Abs Gamma: {day['total_abs']:.0f}")
        print(f"  Call Gamma: {day['call_gex']:.0f}")
        print(f"  Put Gamma: {day['put_gex']:.0f}")
        print(f"  GEX Ratio: {day['gex_ratio']:.2f}")
        print(f"  OI Ratio: {day['oi_ratio']:.2f}")
        print(f"  Dominance ratio: {day['dominance_ratio']:.1f}x")
        print(f"  Price crosses: {day['crosses']}")
        print(f"  Distance from price: {day['distance']:.0f}")
        print()

conn.close()
