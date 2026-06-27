"""Controller for narrative API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class NarrativeController(BaseController):
    """Controller for narrative-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="NarrativeController")
    def get_narrative():
        """Get or generate a trading narrative for a given date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with narrative text and metadata
        """
        date_iso = request.args.get("date")
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("date required"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            # Check if narrative exists
            with get_connection() as con:
                row = con.execute(
                    "SELECT narrative, is_llm_enhanced FROM daily_narratives WHERE ndate=?",
                    (ndate,)
                ).fetchone()
            
            if row:
                response = BaseController.success_response(data={
                    "date": date_iso,
                    "narrative": row[0],
                    "is_llm_enhanced": bool(row[1]),
                    "generated": False
                })
                
                if request.args.get('test_mode') == '1':
                    response['test_metadata'] = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'test_mode': True,
                        'dao_used': 'NarrativeController',
                        'query_time_ms': 0,
                        'row_count': 1
                    }
                
                return BaseController.json_response(response)
            
            # Narrative not found - return 404
            return BaseController.json_response(
                BaseController.error_response("Narrative not found for this date"),
                404
            )
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
