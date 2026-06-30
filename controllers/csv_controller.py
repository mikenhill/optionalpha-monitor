"""Controller for CSV data API endpoints."""

import json
import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from controllers.gex_calculations import (
    calculate_sentiment, calculate_gex_ratio, calculate_net_gex,
    calculate_kcs, calculate_dominance, calculate_key_strike_stats,
    calculate_total_oi_and_vol, calculate_total_gex
)
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class CsvController(BaseController):
    """Controller for CSV data-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="CsvController")
    def get_csv_data():
        """Return summary metrics for all historical dates at the same time slot.
        
        Query params:
            time: time in HHMM format (default 935)
            
        Returns:
            JSON response with summary metrics for all dates
        """
        ntime = int(request.args.get("time", 935))
        
        try:
            with get_connection() as con:
                rows = con.execute(
                    """SELECT ndate, ntime, price, data FROM gex_strike_window
                       WHERE ntime=? AND symbol='SPX' AND source='gex'
                       ORDER BY ndate""",
                    (ntime,)
                ).fetchall()
            
            rows_data = []
            
            for row in rows:
                ndate, snap_ntime, price, data = row
                strikes = json.loads(data) if data else []
                if not strikes or not price:
                    continue
                
                s = str(ndate)
                date_iso = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                
                sentiment = calculate_sentiment(strikes)
                gex_ratio = calculate_gex_ratio(strikes)
                net_gex = calculate_net_gex(strikes)
                kcs = calculate_kcs(strikes, price)
                dominance = calculate_dominance(strikes, price)
                key_stats = calculate_key_strike_stats(strikes, price)
                oi_vol = calculate_total_oi_and_vol(strikes)
                total_gex = calculate_total_gex(strikes)
                
                key_net = (key_stats["key_call_gex"] or 0) - (key_stats["key_put_gex"] or 0)
                key_net_oi = (key_stats["key_call_oi"] or 0) - (key_stats["key_put_oi"] or 0)
                
                rows_data.append({
                    "date": date_iso,
                    "time": f"{snap_ntime // 100:02d}:{snap_ntime % 100:02d}",
                    "SPX-last": price,
                    "sentiment": sentiment,
                    "gex_ratio": gex_ratio,
                    "net_gex": net_gex,
                    "kcs": kcs,
                    "key_strike": key_stats["key_strike"],
                    "key_absolute": dominance,
                    "key_net": key_net,
                    "key_dominance_pct": dominance,
                    "key_call_gex": key_stats["key_call_gex"],
                    "key_put_gex": key_stats["key_put_gex"],
                    "key_call_oi": key_stats["key_call_oi"],
                    "key_put_oi": key_stats["key_put_oi"],
                    "key_net_oi": key_net_oi,
                    "key_call_vol": key_stats["key_call_vol"],
                    "OI Calls": oi_vol["total_call_oi"],
                    "OI Puts": oi_vol["total_put_oi"],
                    "OI Net": oi_vol["total_call_oi"] - oi_vol["total_put_oi"],
                    "Vol Calls": oi_vol["total_call_vol"],
                    "Vol Puts": oi_vol["total_put_vol"],
                    "Vol Net": oi_vol["total_call_vol"] - oi_vol["total_put_vol"],
                    "total_call_gex": total_gex["total_call_gex"],
                    "total_put_gex": total_gex["total_put_gex"],
                })
            
            COLUMNS = [
                "date", "time", "SPX-last", "sentiment", "gex_ratio", "net_gex", "kcs",
                "key_strike", "key_absolute", "key_net", "key_dominance_pct",
                "key_call_gex", "key_put_gex", "key_call_oi", "key_put_oi", "key_net_oi",
                "key_call_vol", "OI Calls", "OI Puts", "OI Net",
                "Vol Calls", "Vol Puts", "Vol Net",
                "total_call_gex", "total_put_gex",
            ]
            rows_data.reverse()
            data = {"columns": COLUMNS, "rows": rows_data}
            
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'CsvController',
                    'query_time_ms': 0,
                    'row_count': len(rows_data)
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(data)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
