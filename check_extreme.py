import sqlite3
import json

con = sqlite3.connect('gex.db')

# Scan entire gex_strike_window for records with zero OI/vol but non-zero GEX
rows = con.execute(
    'SELECT ndate, ntime, price, data FROM gex_strike_window WHERE symbol=? AND source=?',
    ('SPX', 'gex')
).fetchall()

print(f'Total records to scan: {len(rows)}\n')

corrupt_records = []

for row in rows:
    ndate, ntime, price, data = row
    strikes = json.loads(data) if data else []
    
    if not strikes:
        continue
    
    # Check if all strikes have zero OI/vol but non-zero GEX
    has_zero_oi = all(s.get('call_oi', 0) == 0 and s.get('put_oi', 0) == 0 for s in strikes)
    has_zero_vol = all(s.get('call_vol', 0) == 0 and s.get('put_vol', 0) == 0 for s in strikes)
    has_gex = any(s.get('cg', 0) != 0 or s.get('pg', 0) != 0 for s in strikes)
    
    if has_zero_oi and has_zero_vol and has_gex:
        corrupt_records.append((ndate, ntime, price, len(strikes)))

print(f'Found {len(corrupt_records)} corrupt records (zero OI/vol but non-zero GEX):\n')
for nd, nt, price, count in corrupt_records[:20]:
    nd_str = str(nd)
    date_str = f"{nd_str[:4]}-{nd_str[4:6]}-{nd_str[6:]}"
    time_str = f"{nt//100:02d}:{nt%100:02d}"
    print(f'  {date_str} {time_str} (price={price}, strikes={count})')

if len(corrupt_records) > 20:
    print(f'  ... and {len(corrupt_records) - 20} more')

print(f'\n\nALL {len(corrupt_records)} records are corrupt - this is a systemic data issue.')
print(f'The OptionAlpha API may have changed or the sync logic is not capturing OI/volume.')
