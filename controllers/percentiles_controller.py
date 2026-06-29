"""Controller for percentiles API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


# Time slots for percentile comparison
TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]


class PercentilesController(BaseController):
    """Controller for percentiles-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="PercentilesController")
    def get_percentiles():
        """Return percentile ranks for all metrics for a given date/time snapshot.

        Uses pre-computed percentile_history table for fast lookup.
        net_gex:   bearish_pct = 100 - pct_rank  (higher = more bearish than historical)
        call_gex, put_gex, call_oi, put_oi, call_vol, put_vol:
                   size_pct = pct_rank  (higher = larger than more historical readings)
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 1000)
            
        Returns:
            JSON response with percentile ranks for all metrics
        """
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 1000))
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("date required"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            # Load snapshot stats from database
            stats = PercentilesController._load_snapshot_stats(ndate, ntime)
            is_live = False
            
            if not stats:
                return BaseController.json_response(
                    BaseController.error_response("No snapshot found"),
                    404
                )
            
            # For live snapshots, find the time slot with the most historical data
            if is_live:
                cache_ntime = PercentilesController._find_best_time_slot()
            else:
                cache_ntime = ntime
            
            # Get sample size for this time slot
            with get_connection() as con:
                n = con.execute(
                    "SELECT COUNT(DISTINCT ndate) FROM percentile_history WHERE ntime=?",
                    (cache_ntime,)
                ).fetchone()[0]
            
            # Get percentiles for all metrics
            percentiles = PercentilesController._calculate_percentiles(
                ndate, ntime, cache_ntime, stats, is_live
            )
            
            data = {
                "sample_size": n,
                "ntime": ntime,
                **percentiles
            }
            
            # Return plain data for backward compatibility with original /api/percentiles
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'PercentilesController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(data)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    def _load_snapshot_stats(ndate, ntime):
        """Load snapshot stats from database."""
        with get_connection() as con:
            # Try to get stats from snapshot table
            cursor = con.execute(
                """SELECT net_gex, total_call_gex, total_put_gex, 
                          total_call_oi, total_put_oi, 
                          total_call_vol, total_put_vol, kcs, dominance
                   FROM snapshot 
                   WHERE ndate=? AND ntime=? AND symbol='SPX'""",
                (ndate, ntime)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "net_gex": row[0],
                    "call_gex": row[1],
                    "put_gex": row[2],
                    "call_oi": row[3],
                    "put_oi": row[4],
                    "call_vol": row[5],
                    "put_vol": row[6],
                    "kcs": row[7],
                    "dominance": row[8],
                }
        
        return None
    
    @staticmethod
    def _find_best_time_slot():
        """Find the time slot with the largest sample size in percentile_history."""
        best_ntime = 1000
        best_size = 0
        
        with get_connection() as con:
            for t in TIMES:
                size = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=?",
                    (t,)
                ).fetchone()[0]
                if size > best_size:
                    best_size = size
                    best_ntime = t
        
        return best_ntime
    
    @staticmethod
    def _calculate_percentiles(ndate, ntime, cache_ntime, stats, is_live):
        """Calculate percentile ranks for all metrics."""
        with get_connection() as con:
            # Calculate net_gex percentile
            if is_live:
                net_pct_raw = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name='net_gex' AND value<=?",
                    (cache_ntime, stats["net_gex"])
                ).fetchone()[0]
                total = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name='net_gex'",
                    (cache_ntime,)
                ).fetchone()[0]
                net_pct_raw = round(net_pct_raw / total * 100, 1) if total > 0 else 50
            else:
                row = con.execute(
                    "SELECT percentile FROM percentile_history WHERE ndate=? AND ntime=? AND metric_name='net_gex'",
                    (ndate, ntime)
                ).fetchone()
                net_pct_raw = row[0] if row else 50
            
            bearish_pct = 100 - net_pct_raw
            
            # Helper function for size-based metrics
            def size_entry(metric_name):
                if is_live:
                    pct_raw = con.execute(
                        "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=? AND value<=?",
                        (cache_ntime, metric_name, stats[metric_name])
                    ).fetchone()[0]
                    total = con.execute(
                        "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=?",
                        (cache_ntime, metric_name)
                    ).fetchone()[0]
                    pct = round(pct_raw / total * 100, 1) if total > 0 else 50
                else:
                    row = con.execute(
                        "SELECT percentile FROM percentile_history WHERE ndate=? AND ntime=? AND metric_name=?",
                        (ndate, ntime, metric_name)
                    ).fetchone()
                    pct = row[0] if row else 50
                return {"value": stats[metric_name], "pct": pct}
            
            return {
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
