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
                    """SELECT ndate, ntime, symbol, source, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND source=?
                       ORDER BY ntime""",
                    (ndate, source)
                )
                rows = cursor.fetchall()
            
            snapshots = []
            for row in rows:
                ndate, ntime, symbol, src, price, data = row
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
                    "is_premarket": is_premarket
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
