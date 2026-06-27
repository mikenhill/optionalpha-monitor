"""Controller for SPX price API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class SpxController(BaseController):
    """Controller for SPX price-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="SpxController")
    def get_spx_prices():
        """Return SPX price history from snapshot database.
        
        Query params:
            mode: 'eod' (default) or 'single'
            date: ISO date (YYYY-MM-DD) for single mode
            
        Returns:
            JSON response with SPX price history
        """
        mode = request.args.get("mode", "eod")
        target_date = request.args.get("date")
        
        try:
            prices = []
            
            if mode == "single" and target_date:
                # Single date mode: all times for that date
                ndate = int(target_date.replace("-", ""))
                with get_connection() as con:
                    rows = con.execute(
                        "SELECT ntime, uprice FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                        (ndate,)
                    ).fetchall()
                for ntime, uprice in rows:
                    if uprice:
                        prices.append({
                            "date": target_date,
                            "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                            "uprice": uprice
                        })
            else:
                # EOD mode: latest time per day
                with get_connection() as con:
                    rows = con.execute(
                        "SELECT ndate, MAX(ntime) as ntime, uprice FROM snapshot "
                        "WHERE symbol='SPX' GROUP BY ndate ORDER BY ndate"
                    ).fetchall()
                for ndate, ntime, uprice in rows:
                    if uprice:
                        s = str(ndate)
                        date_iso = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                        prices.append({
                            "date": date_iso,
                            "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                            "uprice": uprice
                        })
            
            data = {
                "prices": prices
            }
            
            # Return plain data for backward compatibility with original /api/spx-prices
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SpxController',
                    'query_time_ms': 0,
                    'row_count': len(prices)
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(data)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
