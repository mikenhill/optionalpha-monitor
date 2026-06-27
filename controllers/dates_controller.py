"""Controller for dates API endpoints."""

from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection


class DatesController(BaseController):
    """Controller for dates-related API endpoints."""
    
    @staticmethod
    def get_dates():
        """Get all available dates from the snapshot table.
        
        Returns sorted list of ISO date strings (YYYY-MM-DD) that have GEX data.
        
        Returns:
            JSON response with list of dates
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
            
            return BaseController.json_response(
                BaseController.success_response(data=dates)
            )
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
