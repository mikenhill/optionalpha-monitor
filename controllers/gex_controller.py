"""
GexController for the new gex_strike_window table.
This controller reads from the normalized gex_strike_window table
and calculates metrics on-the-fly using separate calculation functions.
"""

import json
from flask import request
from controllers.base_controller import BaseController
from controllers.gex_calculations import (
    calculate_sentiment,
    calculate_gex_ratio,
    calculate_net_gex,
    calculate_kcs,
    calculate_dominance,
    calculate_key_strike_stats,
    calculate_total_oi_and_vol,
    calculate_total_gex
)
from dao.database import get_connection

# Time slots for percentile comparison
TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]


class GexController(BaseController):
    """Controller for GEX data from gex_strike_window table."""
    
    @staticmethod
    def get_gex_snapshots():
        """Get GEX snapshots for a specific date from gex_strike_window table.
        
        GET /api/gex/snapshots?date=2026-06-23&source=gex
        
        Query params:
            - date: YYYY-MM-DD format (required)
            - source: optional, default "gex"
        
        Returns:
            JSON response with calculated metrics for each snapshot
        """
        try:
            date_str = request.args.get("date")
            if not date_str:
                return BaseController.json_response(
                    BaseController.error_response("Missing required parameter: date"),
                    400
                )
            
            # Convert YYYY-MM-DD to YYYYMMDD
            from datetime import datetime
            ndate = int(datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d"))
            
            source = request.args.get("source", "gex")
            
            # Query gex_strike_window table
            with get_connection() as con:
                cursor = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data, hmm_label
                       FROM gex_strike_window
                       WHERE ndate=? AND source=?
                       ORDER BY ntime""",
                    (ndate, source)
                )
                rows = cursor.fetchall()
            
            snapshots = []
            for row in rows:
                ndate, ntime, symbol, src, price, data, hmm_label = row
                strikes = json.loads(data) if data else []
                
                if not strikes:
                    continue
                
                # Calculate all metrics using separate functions
                sentiment = calculate_sentiment(strikes)
                gex_ratio = calculate_gex_ratio(strikes)
                net_gex = calculate_net_gex(strikes)
                kcs = calculate_kcs(strikes, price)
                dominance = calculate_dominance(strikes, price)
                key_stats = calculate_key_strike_stats(strikes, price)
                total_oi_vol = calculate_total_oi_and_vol(strikes)
                total_gex_vals = calculate_total_gex(strikes)
                
                # Pre-market: times outside 09:35-15:55 range
                is_premarket = ntime < 935 or ntime > 1555
                
                snapshots.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "symbol": symbol,
                    "source": src,
                    "uprice": price,
                    "sentiment": sentiment,
                    "gex_ratio": gex_ratio,
                    "net_gex": net_gex,
                    "kcs": kcs,
                    "dominance": dominance,
                    "key_strike": key_stats["key_strike"],
                    "key_call_gex": key_stats["key_call_gex"],
                    "key_put_gex": key_stats["key_put_gex"],
                    "key_call_oi": key_stats["key_call_oi"],
                    "key_put_oi": key_stats["key_put_oi"],
                    "key_call_vol": key_stats["key_call_vol"],
                    "key_put_vol": key_stats["key_put_vol"],
                    "key2_strike": key_stats["key2_strike"],
                    "key2_abs": key_stats["key2_abs"],
                    "key2_call_vol": key_stats["key2_call_vol"],
                    "key2_put_vol": key_stats["key2_put_vol"],
                    "total_call_oi": total_oi_vol["total_call_oi"],
                    "total_put_oi": total_oi_vol["total_put_oi"],
                    "total_call_vol": total_oi_vol["total_call_vol"],
                    "total_put_vol": total_oi_vol["total_put_vol"],
                    "total_call_gex": total_gex_vals["total_call_gex"],
                    "total_put_gex": total_gex_vals["total_put_gex"],
                    "strike_count": len(strikes),
                    "is_premarket": is_premarket,
                    "hmm_label": hmm_label
                })
            
            return BaseController.json_response({
                "success": True,
                "count": len(snapshots),
                "snapshots": snapshots
            })
            
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    def get_gex_percentiles():
        """Return percentile ranks for all metrics for a given date/time snapshot.

        Uses pre-computed gex_percentile_history table for fast lookup.
        net_gex:   bearish_pct = 100 - pct_rank  (higher = more bearish than historical)
        call_gex, put_gex, call_oi, put_oi, call_vol, put_vol:
                   size_pct = pct_rank  (higher = larger than more historical readings)
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 1000)
            
        Returns:
            JSON response with percentile ranks for all metrics
        """
        try:
            date_iso = request.args.get("date")
            ntime = int(request.args.get("time", 1000))
            
            if not date_iso:
                return BaseController.json_response(
                    BaseController.error_response("date required"),
                    400
                )
            
            ndate = int(date_iso.replace("-", ""))
            
            # Load snapshot stats from gex_strike_window
            with get_connection() as con:
                row = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'""",
                    (ndate, ntime)
                ).fetchone()
            
            if not row:
                return BaseController.json_response(
                    BaseController.error_response("No snapshot found"),
                    404
                )
            
            ndate, ntime, symbol, source, uprice, data_json = row
            
            if not uprice or not data_json:
                return BaseController.json_response(
                    BaseController.error_response("Invalid snapshot data"),
                    400
                )
            
            strikes = json.loads(data_json)
            if not strikes:
                return BaseController.json_response(
                    BaseController.error_response("No strike data"),
                    400
                )
            
            # Calculate metrics using gex_calculations module
            sentiment = calculate_sentiment(strikes)
            gex_ratio = calculate_gex_ratio(strikes)
            net_gex = calculate_net_gex(strikes)
            kcs = calculate_kcs(strikes, uprice)
            dominance = calculate_dominance(strikes, uprice)
            key_stats = calculate_key_strike_stats(strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(strikes)
            total_gex_vals = calculate_total_gex(strikes)
            
            stats = {
                "net_gex": net_gex,
                "call_gex": total_gex_vals["total_call_gex"],
                "put_gex": total_gex_vals["total_put_gex"],
                "call_oi": total_oi_vol["total_call_oi"],
                "put_oi": total_oi_vol["total_put_oi"],
                "call_vol": total_oi_vol["total_call_vol"],
                "put_vol": total_oi_vol["total_put_vol"],
                "kcs": kcs,
                "dominance": dominance,
            }
            
            # Find best time slot for percentile comparison
            best_ntime = ntime
            best_size = 0
            with get_connection() as con:
                for t in TIMES:
                    size = con.execute(
                        "SELECT COUNT(DISTINCT ndate) FROM gex_percentile_history WHERE ntime=?",
                        (t,)
                    ).fetchone()[0]
                    if size > best_size:
                        best_size = size
                        best_ntime = t
            
            cache_ntime = best_ntime
            
            # Get sample size for this time slot
            with get_connection() as con:
                n = con.execute(
                    "SELECT COUNT(DISTINCT ndate) FROM gex_percentile_history WHERE ntime=?",
                    (cache_ntime,)
                ).fetchone()[0]
            
            # Get percentiles for all metrics
            with get_connection() as con:
                # Calculate net_gex percentile
                row = con.execute(
                    "SELECT percentile FROM gex_percentile_history WHERE ndate=? AND ntime=? AND metric_name='net_gex'",
                    (ndate, ntime)
                ).fetchone()
                net_pct_raw = row[0] if row else 50
                bearish_pct = 100 - net_pct_raw
                
                # Helper function for size-based metrics
                def size_entry(metric_name):
                    row = con.execute(
                        "SELECT percentile FROM gex_percentile_history WHERE ndate=? AND ntime=? AND metric_name=?",
                        (ndate, ntime, metric_name)
                    ).fetchone()
                    pct = row[0] if row else 50
                    return {"value": stats[metric_name], "pct": pct}
            
            data = {
                "sample_size": n,
                "ntime": ntime,
                "net_gex": {
                    "value": stats["net_gex"],
                    "pct_raw": net_pct_raw,
                    "bearish_pct": bearish_pct,
                },
                "call_gex": size_entry("call_gex"),
                "put_gex": size_entry("put_gex"),
                "call_oi": size_entry("call_oi"),
                "put_oi": size_entry("put_oi"),
                "call_vol": size_entry("call_vol"),
                "put_vol": size_entry("put_vol"),
                "kcs": size_entry("kcs"),
                "dominance": size_entry("dominance"),
            }
            
            return BaseController.json_response(data)
            
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
