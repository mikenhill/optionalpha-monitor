"""Recalculate percentiles for a specific time slot in gex_percentile_history."""
import sqlite3
import json
import sys

sys.path.insert(0, 'G:\\My Drive\\Colab Notebooks\\optionalpha-monitor')
from controllers.gex_calculations import (
    calculate_sentiment,
    calculate_gex_ratio,
    calculate_net_gex,
    calculate_kcs,
    calculate_dominance,
    calculate_key_strike_stats,
    calculate_total_oi_and_vol,
    calculate_total_gex,
)

DB_PATH = 'gex.db'

# Metrics to calculate percentiles for
METRICS = [
    "net_gex", "kcs", "sentiment", "gex_ratio", "dominance",
    "total_call_gex", "total_put_gex",
    "total_call_oi", "total_put_oi",
    "total_call_vol", "total_put_vol",
]

def recalc_percentiles_for_ntime(ntime):
    """Recalculate percentiles for all snapshots at a specific time slot."""
    con = sqlite3.connect(DB_PATH)
    
    # Get all snapshots at this time slot
    rows = con.execute(
        "SELECT ndate, ntime, price, data FROM gex_strike_window WHERE ntime=? AND symbol='SPX' AND source='gex' ORDER BY ndate",
        (ntime,)
    ).fetchall()
    
    if not rows:
        print(f"No snapshots found for time slot {ntime}")
        con.close()
        return
    
    print(f"Recalculating percentiles for time slot {ntime} ({len(rows)} snapshots)...")
    
    # Calculate metrics for all snapshots at this time slot
    metric_values = {metric: [] for metric in METRICS}
    snapshot_data = []
    
    for row in rows:
        ndate, ntime, uprice, data_json = row
        if not uprice or not data_json:
            continue
        
        try:
            strikes = json.loads(data_json)
        except:
            continue
        
        if not strikes:
            continue
        
        # Calculate all metrics
        sentiment = calculate_sentiment(strikes)
        gex_ratio = calculate_gex_ratio(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, uprice)
        dominance = calculate_dominance(strikes, uprice)
        key_stats = calculate_key_strike_stats(strikes, uprice)
        total_oi_vol = calculate_total_oi_and_vol(strikes)
        total_gex_vals = calculate_total_gex(strikes)
        
        snapshot_data.append({
            "ndate": ndate,
            "ntime": ntime,
            "net_gex": net_gex,
            "kcs": kcs,
            "sentiment": sentiment,
            "gex_ratio": gex_ratio,
            "dominance": dominance,
            "total_call_gex": total_gex_vals["total_call_gex"],
            "total_put_gex": total_gex_vals["total_put_gex"],
            "total_call_oi": total_oi_vol["total_call_oi"],
            "total_put_oi": total_oi_vol["total_put_oi"],
            "total_call_vol": total_oi_vol["total_call_vol"],
            "total_put_vol": total_oi_vol["total_put_vol"],
        })
        
        for metric in METRICS:
            metric_values[metric].append(snapshot_data[-1][metric])
    
    # Delete existing percentile records for this time slot
    con.execute(
        "DELETE FROM gex_percentile_history WHERE ntime=?",
        (ntime,)
    )
    
    # Calculate percentile ranks for each metric
    populated = 0
    for metric in METRICS:
        values = metric_values[metric]
        if not values:
            continue
        
        sorted_vals = sorted(values)
        
        for snap in snapshot_data:
            value = snap[metric]
            rank = sum(1 for v in sorted_vals if v <= value)
            percentile = round(rank / len(sorted_vals) * 100, 1)
            
            con.execute(
                "INSERT INTO gex_percentile_history (ndate, ntime, metric_name, value, percentile) VALUES (?, ?, ?, ?, ?)",
                (snap["ndate"], snap["ntime"], metric, value, percentile)
            )
            populated += 1
    
    con.commit()
    con.close()
    print(f"Populated {populated} percentile records for time slot {ntime}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ntime = int(sys.argv[1])
    else:
        print("Usage: python recalc_gex_percentiles.py <ntime>")
        sys.exit(1)
    
    recalc_percentiles_for_ntime(ntime)
