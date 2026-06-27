"""Controller for snapshot API endpoints."""

from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from dao.snapshot_dao import SnapshotDAO


class SnapshotController(BaseController):
    """Controller for snapshot-related API endpoints."""
    
    @staticmethod
    def get_snapshots():
        """Return all available snapshot times for a given date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with list of times
        """
        date_iso = request.args.get("date")
        if not date_iso:
            return BaseController.json_response(
                BaseController.success_response(data={"times": []})
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            with get_connection() as con:
                cursor = con.execute(
                    "SELECT DISTINCT ntime FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                    (ndate,)
                )
                times = [row[0] for row in cursor.fetchall()]
            
            return BaseController.json_response(
                BaseController.success_response(data={"times": times})
            )
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    def get_snapshot():
        """Get a single snapshot by date and time.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 930)
            prev_time: optional previous time for comparison
            
        Returns:
            JSON response with snapshot data
        """
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 930))
        prev_t = request.args.get("prev_time")
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("Missing required parameter: date"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            # Find snapshot using DAO
            snapshot = SnapshotDAO.find_by_date_time(ndate, ntime, 'SPX')
            
            if not snapshot:
                return BaseController.json_response(
                    BaseController.error_response("No GEX data for this date/time"),
                    404
                )
            
            # Convert to JSON
            data = snapshot.toJson()
            
            # Add previous snapshot if requested
            if prev_t:
                prev_snapshot = SnapshotDAO.find_by_date_time(ndate, int(prev_t), 'SPX')
                if prev_snapshot:
                    data['prev_snapshot'] = prev_snapshot.toJson()
            
            return BaseController.json_response(
                BaseController.success_response(data=data)
            )
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    def get_snapshots_summary():
        """Return a compact summary row for every available time-slot on a date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with summary rows
        """
        date_iso = request.args.get("date")
        if not date_iso:
            return BaseController.json_response(
                BaseController.success_response(data={"date": date_iso, "rows": []})
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            fields = [
                "ntime", "uprice", "sentiment", "gex_ratio", "net_gex", "kcs", "dominance",
                "total_call_gex", "total_put_gex", "key_strike", "key_call_gex", "key_put_gex",
                "total_call_oi", "total_put_oi", "key_call_oi", "key_put_oi",
                "total_call_vol", "total_put_vol", "key_call_vol", "key_put_vol",
                "key2_strike", "key2_abs", "key2_call_vol", "key2_put_vol", "flip",
                "hmm_state", "hmm_label", "is_premarket",
            ]
            
            with get_connection() as con:
                cursor = con.execute(
                    f"SELECT {', '.join(fields)} FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                    (ndate,)
                )
                rows = [dict(row) for row in cursor.fetchall()]
            
            return BaseController.json_response(
                BaseController.success_response(data={"date": date_iso, "rows": rows})
            )
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
