"""Controller for trade signals API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class TradeSignalsController(BaseController):
    """Controller for trade signals-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="TradeSignalsController")
    def get_trade_signals():
        """Return all persisted trade signals for a date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with list of trade signals
        """
        date_iso = request.args.get("date")
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("date required"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            with get_connection() as con:
                rows = con.execute(
                    """SELECT ntime, regime, setup_type, action, short_strike, wing_strike, 
                              short_strike2, wing_strike2, structure, rationale, invalidation, caution, 
                              prev_outcome, next_spx, next_ntime, outcome, outcome_points, generated_ts, is_llm_enhanced 
                       FROM trade_signals WHERE ndate=? AND symbol='SPX' ORDER BY ntime""",
                    (ndate,)
                ).fetchall()
            
            cols = ["ntime", "regime", "setup_type", "action", "short_strike", "wing_strike",
                    "short_strike2", "wing_strike2", "structure", "rationale", "invalidation",
                    "caution", "prev_outcome", "next_spx", "next_ntime", "outcome", "outcome_points",
                    "generated_ts", "is_llm_enhanced"]
            
            signals = [dict(zip(cols, r)) for r in rows]
            
            response = BaseController.success_response(data={
                "date": date_iso,
                "signals": signals
            })
            
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'TradeSignalsController',
                    'query_time_ms': 0,
                    'row_count': len(signals)
                }
            
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
