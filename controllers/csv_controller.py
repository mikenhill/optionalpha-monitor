"""Controller for CSV data API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class CsvController(BaseController):
    """Controller for CSV data-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="CsvController")
    def get_csv_data():
        """Return summary metrics for all historical dates at the same time slot.
        
        Query params:
            time: time in HHMM format (default 930)
            
        Returns:
            JSON response with summary metrics for all dates
        """
        ntime = int(request.args.get("time", 930))
        
        try:
            # Get available dates
            with get_connection() as con:
                rows = con.execute(
                    "SELECT DISTINCT ndate FROM snapshot ORDER BY ndate"
                ).fetchall()
            
            dates = []
            for r in rows:
                s = str(r[0])
                dates.append(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
            
            rows_data = []
            
            for date_iso in dates:
                ndate = int(date_iso.replace("-", ""))
                
                # Load snapshot from database
                with get_connection() as con:
                    cursor = con.execute(
                        """SELECT uprice, total_call_gex, total_put_gex, net_gex, kcs, dominance,
                                  key_strike, key_call_gex, key_put_gex, key_call_oi, key_put_oi,
                                  key_call_vol, key_put_vol, total_call_oi, total_put_oi,
                                  total_call_vol, total_put_vol
                           FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'""",
                        (ndate, ntime)
                    )
                    row = cursor.fetchone()
                    
                    if not row:
                        continue
                    
                    (uprice, total_call_gex, total_put_gex, net_gex, kcs, dominance,
                     key_strike, key_call_gex, key_put_gex, key_call_oi, key_put_oi,
                     key_call_vol, key_put_vol, total_call_oi, total_put_oi,
                     total_call_vol, total_put_vol) = row
                    
                    # Calculate sentiment from key strike data
                    key_net = (key_call_gex or 0) - (key_put_gex or 0)
                    key_net_oi = (key_call_oi or 0) - (key_put_oi or 0)
                    
                    # Calculate gex_ratio
                    if total_call_gex and total_call_gex > 0:
                        if total_call_gex > total_put_gex:
                            gex_ratio = round(total_call_gex / total_put_gex, 1) if total_put_gex else 0
                        else:
                            gex_ratio = round(-total_put_gex / total_call_gex, 1) if total_call_gex else 0
                    else:
                        gex_ratio = 0
                    
                    row_data = {
                        "date": date_iso,
                        "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                        "SPX-last": uprice,
                        "sentiment": 50,  # Would need more data to calculate
                        "gex_ratio": gex_ratio,
                        "net_gex": net_gex,
                        "key_strike": key_strike,
                        "key_absolute": dominance,
                        "key_net": key_net,
                        "key_dominance_pct": dominance,
                        "key_call_gex": key_call_gex,
                        "key_put_gex": key_put_gex,
                        "key_call_oi": key_call_oi,
                        "key_put_oi": key_put_oi,
                        "key_net_oi": key_net_oi,
                        "key_call_vol": key_call_vol,
                        "OI Calls": total_call_oi,
                        "OI Puts": total_put_oi,
                        "OI Net": (total_call_oi or 0) - (total_put_oi or 0),
                        "Vol Calls": total_call_vol,
                        "Vol Puts": total_put_vol,
                        "Vol Net": (total_call_vol or 0) - (total_put_vol or 0),
                    }
                    
                    rows_data.append(row_data)
            
            data = {
                "rows": rows_data
            }
            
            # Return plain data for backward compatibility with original /api/csv-data
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
