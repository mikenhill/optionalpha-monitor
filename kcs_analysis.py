import sqlite3, json, sys, math
from pathlib import Path

sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
from gex_viewer import summarise_snapshot, load_gex_snapshot

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')

DATES = ["2026-06-18", "2026-06-22", "2026-06-23"]

def fmt(v, decimals=2):
    if v is None: return "  --  "
    return f"{v:>{6+decimals}.{decimals}f}"

for date_iso in DATES:
    ndate = int(date_iso.replace("-", ""))
    con = sqlite3.connect(str(DB))
    times = [r[0] for r in con.execute(
        "SELECT DISTINCT ntime FROM gex_snapshots WHERE ndate=? AND symbol='SPX' AND ntime>=935 ORDER BY ntime",
        (ndate,)
    ).fetchall()]
    # Also pull live captures if available
    live_rows = con.execute(
        "SELECT ntime, spx_last, kcs, dominance, key_strike, net_gex, sentiment FROM live_captures "
        "WHERE ndate=? AND ntime>=935 ORDER BY ntime",
        (ndate,)
    ).fetchall()
    con.close()

    print(f"\n{'='*80}")
    print(f"  DATE: {date_iso}")
    print(f"{'='*80}")
    print(f"  {'Time':>6}  {'SPX':>8}  {'KCS':>6}  {'Dom%':>6}  {'Key':>6}  {'NetGEX':>9}  {'Senti%':>7}  Notes")
    print(f"  {'-'*6}  {'-'*8}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*9}  {'-'*7}")

    # Build from gex_snapshots
    snap_data = []
    for ntime in times:
        data = load_gex_snapshot(date_iso, ntime)
        if not data:
            continue
        snap = summarise_snapshot(data)
        snap_data.append((ntime, snap))

    # Merge with live captures (live may have slightly different KCS due to window)
    live_by_time = {r[0]: r for r in live_rows}

    prev_spx = None
    prev_key = None
    prev_kcs = None
    rows_out = []
    for ntime, snap in snap_data:
        spx   = snap.get("uprice")
        kcs   = snap.get("kcs")
        dom   = snap.get("key_dominance_pct")
        key   = snap.get("key_strike")
        net   = snap.get("net_gex", 0)
        senti = snap.get("sentiment_pct")

        # Assess KCS signal quality
        notes = []
        if kcs is not None:
            if kcs >= 15:   notes.append("KCS HIGH")
            elif kcs >= 8:  notes.append("KCS MOD")
            elif kcs >= 4:  notes.append("KCS LOW")
            else:           notes.append("KCS WEAK")

        # Did price approach key strike?
        if spx and key:
            dist = abs(spx - key)
            if dist <= 5:   notes.append(f"AT KEY({key})")
            elif dist <= 15: notes.append(f"NEAR KEY({key})")
            else:            notes.append(f"key={key} dist={dist:.0f}")

        # Key strike changed?
        if prev_key and key and key != prev_key:
            notes.append(f"KEY CHANGED {prev_key}→{key}")

        # KCS trend
        if prev_kcs is not None and kcs is not None:
            delta = kcs - prev_kcs
            if abs(delta) >= 3:
                notes.append(f"KCS {'↑' if delta>0 else '↓'}{abs(delta):.1f}")

        rows_out.append((ntime, spx, kcs, dom, key, net, senti, "  ".join(notes)))
        prev_spx, prev_key, prev_kcs = spx, key, kcs

    for ntime, spx, kcs, dom, key, net, senti, notes in rows_out:
        t = f"{ntime:04d}"
        ts = f"{t[:2]}:{t[2:]}"
        spx_s  = f"{spx:8.2f}" if spx else "      --"
        kcs_s  = f"{kcs:6.2f}" if kcs is not None else "    --"
        dom_s  = f"{dom:5.1f}%" if dom is not None else "    --"
        key_s  = f"{int(key):6d}" if key else "    --"
        net_s  = f"{net/1e9:+8.2f}B" if net else "       --"
        sent_s = f"{senti:5.0f}%" if senti is not None else "   --"
        print(f"  {ts:>6}  {spx_s}  {kcs_s}  {dom_s}  {key_s}  {net_s}  {sent_s}  {notes}")

    # Summary stats
    kcs_vals = [s.get("kcs") for _, s in snap_data if s.get("kcs") is not None]
    keys = [s.get("key_strike") for _, s in snap_data if s.get("key_strike")]
    spxs = [s.get("uprice") for _, s in snap_data if s.get("uprice")]
    if kcs_vals:
        print(f"\n  KCS range: {min(kcs_vals):.2f} – {max(kcs_vals):.2f}  avg={sum(kcs_vals)/len(kcs_vals):.2f}")
    if keys:
        unique_keys = sorted(set(keys))
        print(f"  Key strikes seen: {unique_keys}")
    if spxs:
        print(f"  SPX range: {min(spxs):.2f} – {max(spxs):.2f}  (move={max(spxs)-min(spxs):.2f}pts)")

    # KCS vs price distance correlation
    print(f"\n  KCS vs distance-to-key-strike:")
    print(f"  {'Time':>6}  {'KCS':>6}  {'Key':>6}  {'SPX':>8}  {'Dist':>6}  Interpretation")
    for ntime, snap in snap_data:
        kcs = snap.get("kcs")
        key = snap.get("key_strike")
        spx = snap.get("uprice")
        if kcs is None or key is None or spx is None: continue
        dist = abs(spx - key)
        t = f"{ntime:04d}"; ts = f"{t[:2]}:{t[2:]}"
        # High KCS + close to key = strong magnetic effect expected
        if kcs >= 10 and dist <= 10:
            interp = "★ HIGH KCS near key — strong pin/magnet signal"
        elif kcs >= 8 and dist <= 20:
            interp = "◆ Good KCS, price gravitating"
        elif kcs >= 5 and dist > 30:
            interp = "△ Moderate KCS but price far — key not active yet"
        elif kcs < 4:
            interp = "○ Weak KCS — diffuse GEX, no dominant level"
        else:
            interp = ""
        print(f"  {ts:>6}  {kcs:>6.2f}  {key:>6.0f}  {spx:>8.2f}  {dist:>6.1f}  {interp}")

print(f"\n{'='*80}")
print("VERDICT")
print(f"{'='*80}")
print("""
KCS usefulness assessment:

  HIGH KCS (≥10): Key strike has strong multi-factor confluence (GEX+OI+Vol).
    → Price tends to gravitate toward or pin at this strike.
    → High-value signal for setting targets/stops.

  MODERATE KCS (5-10): Meaningful concentration but not dominant.
    → Useful as a reference, not a pin target.

  LOW KCS (<4): GEX dispersed across many strikes.
    → No single dominant level — wider range expected, key strike less reliable.

  KEY CHANGE with KCS drop: When key strike shifts AND KCS falls, regime is
    shifting — dealer hedging is redistributing, often precedes larger moves.

  RECOMMENDATION: Add KCS to analysis with thresholds:
    KCS ≥ 10  → "Strong pin/magnet at [key] — high confidence level"
    KCS 5-10  → "Moderate confluence at [key] — monitor for reaction"
    KCS < 4   → "Diffuse GEX — no dominant level, wider range likely"
""")
