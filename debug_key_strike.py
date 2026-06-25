import sqlite3
import json
import math
from pathlib import Path

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')

con = sqlite3.connect(str(DB))
row = con.execute(
    'SELECT ndate, ntime, uprice, data FROM gex_snapshots WHERE symbol="SPX" ORDER BY ndate DESC, ntime DESC LIMIT 1'
).fetchone()

if not row:
    print("No snapshot found")
    exit(1)

ndate, ntime, uprice, data_json = row
print(f"Latest snapshot: Date={ndate}, Time={ntime}, SPX Price={uprice}")

data = json.loads(data_json)
print(f"Total strikes in data: {len(data)}")

# Filter strikes 7350-7450
strikes_of_interest = [r for r in data if 7350 <= r.get("strike", 0) <= 7450]
print(f"\nStrikes in range 7350-7450: {len(strikes_of_interest)}")

# Calculate totals for the window
total_abs = sum(abs(r.get("abs", 0) or 0) for r in strikes_of_interest)
total_oi = sum((r.get("coi", 0) or 0) + (r.get("poi", 0) or 0) for r in strikes_of_interest)
total_vol = sum((r.get("cvol", 0) or 0) + (r.get("pvol", 0) or 0) for r in strikes_of_interest)

print(f"\nWindow totals:")
print(f"  Total abs GEX: {total_abs:,.0f}")
print(f"  Total OI: {total_oi:,.0f}")
print(f"  Total Vol: {total_vol:,.0f}")

# Calculate proximity-weighted score for each strike
print(f"\n{'Strike':>6}  {'Abs GEX':>12}  {'Call GEX':>10}  {'Put GEX':>10}  {'Call OI':>10}  {'Put OI':>10}  {'Call Vol':>10}  {'Put Vol':>10}  {'Dist':>6}  {'Prox':>6}  {'Prox*Abs':>12}")
print("-" * 110)

for r in sorted(strikes_of_interest, key=lambda x: x["strike"]):
    strike = r["strike"]
    abs_gex = abs(r.get("abs", 0) or 0)
    cg = r.get("cg", 0) or 0
    pg = r.get("pg", 0) or 0
    coi = r.get("coi", 0) or 0
    poi = r.get("poi", 0) or 0
    cvol = r.get("cvol", 0) or 0
    pvol = r.get("pvol", 0) or 0
    
    dist = abs(strike - uprice)
    prox = math.exp(-dist / 25.0)
    prox_abs = abs_gex * prox
    
    print(f"{strike:6.0f}  {abs_gex:12,.0f}  {cg:10,.0f}  {pg:10,.0f}  {coi:10,.0f}  {poi:10,.0f}  {cvol:10,.0f}  {pvol:10,.0f}  {dist:6.0f}  {prox:6.3f}  {prox_abs:12,.0f}")

# Find key strike
key_row = max(strikes_of_interest, key=lambda r: abs(r.get("abs", 0) or 0) * math.exp(-abs(r["strike"] - uprice) / 25.0))
key_strike = key_row["strike"]
key_abs = abs(key_row.get("abs", 0) or 0)
key_coi = key_row.get("coi", 0) or 0
key_poi = key_row.get("poi", 0) or 0
key_cvol = key_row.get("cvol", 0) or 0
key_pvol = key_row.get("pvol", 0) or 0

print(f"\nKey strike identified: {key_strike}")
print(f"  Distance from price: {abs(key_strike - uprice):.0f}")
print(f"  Proximity factor: {math.exp(-abs(key_strike - uprice) / 25.0):.3f}")

# Calculate KCS components
gex_share = key_abs / total_abs if total_abs else 0.0
oi_share = (key_coi + key_poi) / total_oi if total_oi else 0.0
vol_share = (key_cvol + key_pvol) / total_vol if total_vol else 0.0
prox = math.exp(-abs(key_strike - uprice) / 25.0)
kcs = round((0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * prox * 100, 2)

print(f"\nKCS Calculation:")
print(f"  GEX share: {gex_share:.3f} (50% weight)")
print(f"  OI share: {oi_share:.3f} (30% weight)")
print(f"  Vol share: {vol_share:.3f} (20% weight)")
print(f"  Weighted sum: {(0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share):.3f}")
print(f"  Proximity factor: {prox:.3f}")
print(f"  KCS = {kcs:.2f}")

con.close()
