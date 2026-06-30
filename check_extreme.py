import sqlite3
import json

con = sqlite3.connect('gex.db')

# Check specific record: 2026-03-31 10:00
row = con.execute(
    'SELECT ndate, ntime, price, data FROM gex_strike_window WHERE ndate=20260331 AND ntime=1000 AND symbol=? AND source=?',
    ('SPX', 'gex')
).fetchone()

if not row:
    print('No record found for 2026-03-31 10:00')
else:
    print(f'Record: ndate={row[0]}, ntime={row[1]}, price={row[2]}')
    strikes = json.loads(row[3]) if row[3] else []
    print(f'Strikes: {len(strikes)}')
    
    # Show all field names in the first strike
    if strikes:
        print(f'\nField names in first strike: {list(strikes[0].keys())}')
    
    # Check OI/vol pattern using correct field names (coi/poi/cvol/pvol)
    has_zero_oi = all(s.get('coi', 0) == 0 and s.get('poi', 0) == 0 for s in strikes)
    has_zero_vol = all(s.get('cvol', 0) == 0 and s.get('pvol', 0) == 0 for s in strikes)
    has_gex = any(s.get('cg', 0) != 0 or s.get('pg', 0) != 0 for s in strikes)
    
    print(f'\nPattern check (using coi/poi/cvol/pvol):')
    print(f'  All strikes have zero OI: {has_zero_oi}')
    print(f'  All strikes have zero Vol: {has_zero_vol}')
    print(f'  Has non-zero GEX: {has_gex}')
    
    # Find key strike
    uprice = row[2]
    if strikes:
        key = min(strikes, key=lambda s: abs(s['strike'] - uprice))
        print(f'\nKey Strike ({key["strike"]}):')
        print(f'  Call GEX: {key.get("cg", 0)/1e6:.2f}M')
        print(f'  Put GEX: {key.get("pg", 0)/1e6:.2f}M')
        print(f'  Call OI (coi): {key.get("coi", 0)}')
        print(f'  Put OI (poi): {key.get("poi", 0)}')
        print(f'  Call Vol (cvol): {key.get("cvol", 0)}')
        print(f'  Put Vol (pvol): {key.get("pvol", 0)}')
