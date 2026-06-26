import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "gex.db"

def _compute_flat_summary(data, db_uprice=None):
    """Compute flat summary columns from raw JSON data."""
    if isinstance(data, str):
        data = json.loads(data)
    
    # Handle both dict with 'data' key and direct list
    if isinstance(data, dict):
        rows = data.get("data") or []
        # Try uprice (historical) or last (live) or fall back to db_uprice
        uprice = data.get("uprice") or data.get("last") or db_uprice or 0
    elif isinstance(data, list):
        rows = data
        uprice = db_uprice or 0
    else:
        return {}
    
    if not rows:
        return {}
    
    valid = [r for r in rows if r.get("strike") is not None]
    
    # 40-strike window
    below = [r for r in valid if r["strike"] < uprice]
    above = [r for r in valid if r["strike"] >= uprice]
    window_rows = below[-20:] + above[:20]
    if not window_rows:
        return {}
    
    # Calculate all flat columns
    net = sum(r.get("net", 0) or 0 for r in window_rows)
    cg = sum(r.get("cg", 0) or 0 for r in window_rows)
    pg = sum(r.get("pg", 0) or 0 for r in window_rows)
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in window_rows)
    
    sorted_abs = sorted(window_rows, key=lambda r: abs(r.get("abs", 0) or 0), reverse=True)
    wall = sorted_abs[0] if sorted_abs else None
    wall2 = sorted_abs[1] if len(sorted_abs) > 1 else None
    
    # Flip level
    by_strike = sorted(window_rows, key=lambda r: r["strike"])
    cumulative = 0.0
    flip = None
    prev_strike, prev_cum = None, 0.0
    for r in by_strike:
        cumulative += r.get("net", 0) or 0
        if prev_strike is not None and prev_cum * cumulative < 0:
            denom = abs(cumulative) + abs(prev_cum)
            flip = round(prev_strike + (r["strike"] - prev_strike) * abs(prev_cum) / denom, 1) if denom else r["strike"]
            break
        prev_strike, prev_cum = r["strike"], cumulative
    
    total_call_oi = sum(r.get("coi", 0) or 0 for r in window_rows)
    total_put_oi = sum(r.get("poi", 0) or 0 for r in window_rows)
    total_call_vol = sum(r.get("cvol", 0) or 0 for r in window_rows)
    total_put_vol = sum(r.get("pvol", 0) or 0 for r in window_rows)
    
    pos_bars = sum(1 for r in window_rows if (r.get("net", 0) or 0) > 0)
    sentiment = round(pos_bars / len(window_rows) * 100) if window_rows else 50
    
    if cg > abs(pg):
        gex_ratio = round(cg / abs(pg), 2) if pg else 0
    else:
        gex_ratio = round(-abs(pg) / cg, 2) if cg else 0
    
    # Key strike values
    key_strike = wall.get("strike") if wall else None
    key_call_gex = wall.get("cg", 0) if wall else 0
    key_put_gex = wall.get("pg", 0) if wall else 0
    key_call_oi = wall.get("coi", 0) if wall else 0
    key_put_oi = wall.get("poi", 0) if wall else 0
    key_call_vol = wall.get("cvol", 0) if wall else 0
    key_put_vol = wall.get("pvol", 0) if wall else 0
    
    # Key2 strike values
    key2_strike = wall2.get("strike") if wall2 else None
    key2_abs = abs(wall2.get("abs", 0)) if wall2 else 0
    key2_call_vol = wall2.get("cvol", 0) if wall2 else 0
    key2_put_vol = wall2.get("pvol", 0) if wall2 else 0
    
    # Dominance
    dominance = round(total_abs / abs(net) * 100, 1) if net != 0 else 0
    
    return {
        "sentiment": sentiment,
        "gex_ratio": gex_ratio,
        "net_gex": net,
        "kcs": round(total_abs / 1e9, 2) if total_abs else 0,
        "dominance": dominance,
        "total_call_gex": cg,
        "total_put_gex": pg,
        "key_strike": key_strike,
        "key_call_gex": key_call_gex,
        "key_put_gex": key_put_gex,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "key_call_oi": key_call_oi,
        "key_put_oi": key_put_oi,
        "total_call_vol": total_call_vol,
        "total_put_vol": total_put_vol,
        "key_call_vol": key_call_vol,
        "key_put_vol": key_put_vol,
        "key2_strike": key2_strike,
        "key2_abs": key2_abs,
        "key2_call_vol": key2_call_vol,
        "key2_put_vol": key2_put_vol,
        "flip": flip
    }

con = sqlite3.connect(DB_PATH)

# Find all rows with NULL key_call_gex
cursor = con.execute(
    "SELECT ndate, ntime, data, uprice FROM gex_snapshots WHERE key_call_gex IS NULL AND symbol='SPX'"
)
rows = cursor.fetchall()

print(f"Found {len(rows)} snapshots with NULL key_call_gex")

updated = 0
for ndate, ntime, data_json, db_uprice in rows:
    try:
        flat = _compute_flat_summary(data_json, db_uprice=db_uprice)
        if flat:
            con.execute("""
                UPDATE gex_snapshots SET
                    sentiment=?, gex_ratio=?, net_gex=?, kcs=?, dominance=?,
                    total_call_gex=?, total_put_gex=?, key_strike=?, key_call_gex=?, key_put_gex=?,
                    total_call_oi=?, total_put_oi=?, key_call_oi=?, key_put_oi=?,
                    total_call_vol=?, total_put_vol=?, key_call_vol=?, key_put_vol=?,
                    key2_strike=?, key2_abs=?, key2_call_vol=?, key2_put_vol=?, flip=?
                WHERE ndate=? AND ntime=? AND symbol='SPX'
            """, (
                flat["sentiment"], flat["gex_ratio"], flat["net_gex"], flat["kcs"], flat["dominance"],
                flat["total_call_gex"], flat["total_put_gex"], flat["key_strike"], flat["key_call_gex"], flat["key_put_gex"],
                flat["total_call_oi"], flat["total_put_oi"], flat["key_call_oi"], flat["key_put_oi"],
                flat["total_call_vol"], flat["total_put_vol"], flat["key_call_vol"], flat["key_put_vol"],
                flat["key2_strike"], flat["key2_abs"], flat["key2_call_vol"], flat["key2_put_vol"], flat["flip"],
                ndate, ntime
            ))
            updated += 1
            if updated % 100 == 0:
                print(f"Updated {updated} rows...")
    except Exception as e:
        print(f"Error updating {ndate}-{ntime}: {e}")

con.commit()
con.close()

print(f"Done. Updated {updated} rows.")
