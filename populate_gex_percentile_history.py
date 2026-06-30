"""Populate gex_percentile_history table from gex_strike_window data."""
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

def main(target_ntimes=None):
    con = sqlite3.connect(DB_PATH)
    
    # Get all distinct (ndate, ntime) pairs from gex_strike_window
    if target_ntimes:
        query = "SELECT DISTINCT ndate, ntime FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND ntime IN ({}) ORDER BY ndate, ntime".format(
            ','.join(str(t) for t in target_ntimes)
        )
    else:
        query = "SELECT DISTINCT ndate, ntime FROM gex_strike_window WHERE symbol='SPX' AND source='gex' ORDER BY ndate, ntime"
    
    pairs = con.execute(query).fetchall()
    
    if not pairs:
        print("No data found in gex_strike_window")
        return
    
    print(f"Found {len(pairs)} snapshots to process")
    
    # Group by ntime to build time-slot distributions
    by_ntime = {}
    for ndate, ntime in pairs:
        if ntime not in by_ntime:
            by_ntime[ntime] = []
        by_ntime[ntime].append(ndate)
    
    print(f"Found {len(by_ntime)} unique time slots")
    
    populated = 0
    for ntime, ndates in by_ntime.items():
        print(f"Processing time slot {ntime} ({len(ndates)} dates)...")
        
        # Calculate metrics for all snapshots at this time slot
        metric_values = {metric: [] for metric in METRICS}
        snapshot_data = []
        
        for ndate in ndates:
            rows = con.execute(
                "SELECT ndate, ntime, price, data FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'",
                (ndate, ntime)
            ).fetchall()
            
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
        
        # Calculate percentile ranks for each metric
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
                    "INSERT OR REPLACE INTO gex_percentile_history (ndate, ntime, metric_name, value, percentile) VALUES (?, ?, ?, ?, ?)",
                    (snap["ndate"], snap["ntime"], metric, value, percentile)
                )
                populated += 1
        
        con.commit()
    
    con.close()
    print(f"Populated {populated} percentile records")

if __name__ == "__main__":
    # Accept optional time slots as command line arguments
    import sys
    target_ntimes = None
    if len(sys.argv) > 1:
        target_ntimes = [int(arg) for arg in sys.argv[1:]]
        print(f"Processing only time slots: {target_ntimes}")
    main(target_ntimes)
