"""Controller for dates API endpoints."""

import time
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class DatesController(BaseController):
    """Controller for dates-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="DatesController")
    def get_dates():
        """Get all available dates from the snapshot table.
        
        Returns sorted list of ISO date strings (YYYY-MM-DD) that have GEX data.
        
        Returns:
            JSON response with list of dates (plain array for backward compatibility)
        """
        try:
            with get_connection() as con:
                cursor = con.execute('''
                    SELECT DISTINCT ndate 
                    FROM snapshot 
                    WHERE symbol = 'SPX'
                    ORDER BY ndate DESC
                ''')
                rows = cursor.fetchall()
            
            # Convert YYYYMMDD int to ISO format (YYYY-MM-DD)
            dates = []
            for row in rows:
                s = str(row[0])  # YYYYMMDD int -> string
                dates.append(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
            
            # Return plain array for backward compatibility with original /api/dates
            # The MVC version at /mvc/api/dates can add test metadata if needed
            if request.args.get('test_mode') == '1':
                # For test mode, return wrapped response with metadata
                response = BaseController.success_response(data=dates)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'DatesController',
                    'query_time_ms': 0,
                    'row_count': len(dates)
                }
                return BaseController.json_response(response)
            else:
                # For normal requests, return plain array (original behavior)
                return BaseController.json_response(dates)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
