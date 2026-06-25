import sqlite3, json, math
from pathlib import Path

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
con = sqlite3.connect(str(DB))

# Latest live capture
row = con.execute(
    "SELECT ndate, ntime, spx_last, net_gex, key_strike, flip, kcs, dominance, sentiment "
    "FROM live_captures ORDER BY id DESC LIMIT 1"
).fetchone()

if not row:
    print("No live captures found")
    con.close()
    exit()

ndate, ntime, spx, net_gex, key_strike, flip, kcs, dominance, sentiment = row
print(f"Latest capture: {ndate} {ntime:04d}  SPX={spx}  Key={key_strike}  Flip={flip}")
print(f"  Net GEX={net_gex/1e9:.2f}B  KCS={kcs}  Dom={dominance}%  Senti={sentiment}%")

# Load full strike data from gex_snapshots for same date/time
snap_row = con.execute(
    "SELECT uprice, data FROM gex_snapshots WHERE ndate=? AND ntime=? AND symbol='SPX'",
    (ndate, ntime)
).fetchone()

target = 7400.0

if snap_row:
    uprice, data_json = snap_row
    strikes = json.loads(data_json)
    print(f"\nUsing gex_snapshots data  (uprice={uprice})")
else:
    # Fall back to latest live JSON
    from datetime import date
    ymd = str(ndate)
    live_dir = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\results\livegex') / ymd
    files = sorted(live_dir.glob(f"{ymd}_{ntime:04d}_SPX_livegex.json")) if live_dir.exists() else []
    if not files:
        files = sorted(live_dir.glob("*.json")) if live_dir.exists() else []
    if not files:
        print("No snapshot data found")
        con.close()
        exit()
    data = json.loads(files[-1].read_text())
    uprice = data.get("uprice", spx)
    strikes = data.get("data", [])
    print(f"\nUsing live JSON file  (uprice={uprice})")

con.close()

# ── GEX-based pin probability ──────────────────────────────────────────────
# 1. Find the absolute GEX at target strike
target_row = next((r for r in strikes if r.get("strike") == target), None)
if target_row is None:
    # find nearest
    nearest = min(strikes, key=lambda r: abs(r.get("strike",0) - target))
    print(f"\nNo exact {target} strike — nearest is {nearest['strike']}")
    target_row = nearest
    target = nearest["strike"]

abs_gex_target = abs(target_row.get("abs", 0) or target_row.get("cg", 0) or 0)
net_gex_target = target_row.get("net", 0) or 0

# 2. Total absolute GEX across all strikes (denominator)
total_abs_gex = sum(abs(r.get("abs", 0) or (abs(r.get("cg",0) or 0) + abs(r.get("pg",0) or 0))) for r in strikes)

# 3. Raw concentration % at target
concentration = (abs_gex_target / total_abs_gex * 100) if total_abs_gex else 0

# 4. Distance penalty — how far is SPX from target?
distance = abs(uprice - target)
distance_pct = distance / uprice * 100

# 5. Proximity-weighted score (same logic as KCS key_strike selection)
proximity_weight = math.exp(-distance / 25.0)
weighted_score = concentration * proximity_weight

# 6. Regime context
regime = "NEGATIVE" if net_gex < 0 else "POSITIVE"
# In negative GEX, pinning is weaker (dealers amplify moves)
regime_multiplier = 0.6 if net_gex < 0 else 1.0

# 7. Final pin probability (heuristic, not statistical)
pin_prob = min(weighted_score * regime_multiplier, 100)

print(f"\n── Pin Analysis: SPX → {target} ──────────────────")
print(f"  Current SPX price : {uprice:.2f}")
print(f"  Distance to target: {distance:.1f} pts ({distance_pct:.2f}%)")
print(f"  Abs GEX at {target} : {abs_gex_target/1e9:.3f}B")
print(f"  Total abs GEX     : {total_abs_gex/1e9:.3f}B")
print(f"  Concentration     : {concentration:.1f}%")
print(f"  Proximity weight  : {proximity_weight:.4f} (exp(-{distance:.0f}/25))")
print(f"  Weighted score    : {weighted_score:.2f}")
print(f"  GEX Regime        : {regime} (multiplier {regime_multiplier})")
print(f"\n  ► Estimated pin probability: {pin_prob:.1f}%")

# Context
if pin_prob >= 30:
    verdict = "MODERATE–HIGH pin potential"
elif pin_prob >= 15:
    verdict = "LOW–MODERATE pin potential"
elif pin_prob >= 5:
    verdict = "LOW pin potential"
else:
    verdict = "VERY LOW — price too far or GEX too thin at this strike"

print(f"  ► Verdict: {verdict}")

# Also show top 5 strikes by pin probability for comparison
print(f"\n── Top 5 strikes by pin probability (same method) ──")
scored = []
for r in strikes:
    k = r.get("strike")
    if k is None: continue
    ag = abs(r.get("abs", 0) or (abs(r.get("cg",0) or 0) + abs(r.get("pg",0) or 0)))
    conc = ag / total_abs_gex * 100 if total_abs_gex else 0
    dist = abs(uprice - k)
    pw = math.exp(-dist / 25.0)
    scored.append((k, conc * pw * regime_multiplier, conc, dist))

scored.sort(key=lambda x: -x[1])
print(f"  {'Strike':>8}  {'Pin Prob':>9}  {'Conc%':>7}  {'Dist':>6}")
for k, pp, conc, dist in scored[:5]:
    marker = " ◄ TARGET" if k == target else (" ◄ CURRENT" if abs(k - uprice) < 5 else "")
    print(f"  {k:>8.0f}  {pp:>8.1f}%  {conc:>6.1f}%  {dist:>6.1f}{marker}")
