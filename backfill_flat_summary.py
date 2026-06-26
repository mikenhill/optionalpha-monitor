import sqlite3
import json
from gex_viewer import _compute_flat_summary

DB_PATH = "gex.db"

con = sqlite3.connect(DB_PATH)

# Find snapshots with total_put_gex=0 but non-empty data blob
cursor = con.execute("""
    SELECT ndate, ntime, data, uprice 
    FROM gex_snapshots 
    WHERE symbol='SPX' 
    AND total_put_gex=0 
    AND data IS NOT NULL 
    AND length(data) > 1000
""")
rows = cursor.fetchall()

print(f"Found {len(rows)} RTH snapshots with net_gex=0 but valid data blob")

updated = 0
for ndate, ntime, data_json, uprice in rows:
    try:
        data_list = json.loads(data_json)
        # Re-calculate summary
        summary = _compute_flat_summary({"uprice": uprice, "data": data_list})
        
        # Update the flat columns
        net_gex = summary.get("net_gex", 0)
        kcs = summary.get("kcs", 0)
        sentiment = summary.get("sentiment_pct", 50)
        gex_ratio = summary.get("gex_ratio", 1)
        dominance = summary.get("key_dominance_pct", 0)
        key_strike = summary.get("key_strike", 0)
        key_call_gex = summary.get("key_call_gex", 0)
        key_put_gex = summary.get("key_put_gex", 0)
        total_call_gex = summary.get("total_call_gex", 0)
        total_put_gex = summary.get("total_put_gex", 0)
        total_call_oi = summary.get("total_call_oi", 0)
        total_put_oi = summary.get("total_put_oi", 0)
        key_call_oi = summary.get("key_call_oi", 0)
        key_put_oi = summary.get("key_put_oi", 0)
        total_call_vol = summary.get("total_call_vol", 0)
        total_put_vol = summary.get("total_put_vol", 0)
        key_call_vol = summary.get("key_call_vol", 0)
        key_put_vol = summary.get("key_put_vol", 0)
        key2_strike = summary.get("key2_strike", 0)
        key2_abs = summary.get("key2_abs", 0)
        key2_call_vol = summary.get("key2_call_vol", 0)
        key2_put_vol = summary.get("key2_put_vol", 0)
        flip = summary.get("flip", 0)
        
        con.execute("""
            UPDATE gex_snapshots 
            SET net_gex=?, kcs=?, sentiment=?, gex_ratio=?, dominance=?,
                key_strike=?, key_call_gex=?, key_put_gex=?,
                total_call_gex=?, total_put_gex=?,
                total_call_oi=?, total_put_oi=?, key_call_oi=?, key_put_oi=?,
                total_call_vol=?, total_put_vol=?, key_call_vol=?, key_put_vol=?,
                key2_strike=?, key2_abs=?, key2_call_vol=?, key2_put_vol=?, flip=?
            WHERE ndate=? AND ntime=? AND symbol='SPX'
        """, (net_gex, kcs, sentiment, gex_ratio, dominance,
              key_strike, key_call_gex, key_put_gex,
              total_call_gex, total_put_gex,
              total_call_oi, total_put_oi, key_call_oi, key_put_oi,
              total_call_vol, total_put_vol, key_call_vol, key_put_vol,
              key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
              ndate, ntime))
        
        updated += 1
        if updated % 10 == 0:
            print(f"Updated {updated} snapshots...")
            con.commit()
            
    except Exception as e:
        print(f"Error updating {ndate} {ntime}: {e}")

con.commit()
print(f"Backfill complete. Updated {updated} snapshots.")
con.close()
