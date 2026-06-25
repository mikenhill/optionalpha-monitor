import sqlite3
from pathlib import Path

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
con = sqlite3.connect(str(DB))

rows = con.execute(
    "SELECT ntime, spx_last, kcs, dominance, key_strike, net_gex, sentiment "
    "FROM live_captures WHERE ndate=20260623 AND ntime>=930 ORDER BY ntime"
).fetchall()
con.close()

print("DATE: 2026-06-23 (from live_captures)")
print(f"  {'Time':>6}  {'SPX':>8}  {'KCS':>6}  {'Dom%':>6}  {'Key':>6}  {'NetGEX':>9}  {'Senti%':>7}  KCS signal / dist-to-key")
print(f"  {'-'*6}  {'-'*8}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*9}  {'-'*7}")

prev_key = None
prev_kcs = None
for ntime, spx, kcs, dom, key, net, senti in rows:
    t = f"{ntime:04d}"; ts = f"{t[:2]}:{t[2:]}"
    notes = []
    if kcs is not None:
        if kcs >= 10:  notes.append("KCS HIGH")
        elif kcs >= 5: notes.append("KCS MOD")
        elif kcs >= 3: notes.append("KCS LOW")
        else:          notes.append("KCS WEAK")

    if spx and key:
        dist = abs(spx - key)
        if dist <= 5:    notes.append(f"AT KEY({key:.0f})")
        elif dist <= 15: notes.append(f"NEAR KEY({key:.0f}) dist={dist:.0f}")
        else:            notes.append(f"key={key:.0f} dist={dist:.0f}")

        if kcs and kcs >= 10 and dist <= 10:
            notes.append("★ STRONG MAGNET")
        elif kcs and kcs >= 8 and dist <= 20:
            notes.append("◆ gravitating")

    if prev_key and key and key != prev_key:
        notes.append(f"KEY {prev_key:.0f}→{key:.0f}")
    if prev_kcs and kcs:
        delta = kcs - prev_kcs
        if abs(delta) >= 2: notes.append(f"KCS {'↑' if delta>0 else '↓'}{abs(delta):.1f}")

    spx_s = f"{spx:8.2f}" if spx else "      --"
    kcs_s = f"{kcs:6.2f}" if kcs else "    --"
    dom_s = f"{dom:5.1f}%" if dom else "    --"
    key_s = f"{key:6.0f}" if key else "    --"
    net_s = f"{net/1e9:+8.2f}B" if net else "       --"
    sent_s = f"{senti:5.0f}%" if senti else "   --"
    print(f"  {ts:>6}  {spx_s}  {kcs_s}  {dom_s}  {key_s}  {net_s}  {sent_s}  {'  '.join(notes)}")
    prev_key, prev_kcs = key, kcs

kcs_vals = [r[2] for r in rows if r[2]]
spxs = [r[1] for r in rows if r[1]]
if kcs_vals:
    print(f"\n  KCS range: {min(kcs_vals):.2f} – {max(kcs_vals):.2f}  avg={sum(kcs_vals)/len(kcs_vals):.2f}")
if spxs:
    print(f"  SPX range: {min(spxs):.2f} – {max(spxs):.2f}  (move so far={max(spxs)-min(spxs):.2f}pts)")
