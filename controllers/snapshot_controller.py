"""Controller for snapshot API endpoints."""

import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from dao.snapshot_dao import SnapshotDAO
from middleware.test_mode import with_test_metadata


# Time regimes for filtering snapshots
TIME_REGIMES = [
    {"id": "pre", "label": "Pre-market", "start": 0, "end": 929},
    {"id": "0930_1000", "label": "09:30-10:00", "start": 930, "end": 1000},
    {"id": "1001_1030", "label": "10:01-10:30", "start": 1001, "end": 1030},
    {"id": "1031_1100", "label": "10:31-11:00", "start": 1031, "end": 1100},
    {"id": "1101_1130", "label": "11:01-11:30", "start": 1101, "end": 1130},
    {"id": "1131_1200", "label": "11:31-12:00", "start": 1131, "end": 1200},
    {"id": "1201_1230", "label": "12:01-12:30", "start": 1201, "end": 1230},
    {"id": "1231_1300", "label": "12:31-13:00", "start": 1231, "end": 1300},
    {"id": "1301_1330", "label": "13:01-13:30", "start": 1301, "end": 1330},
    {"id": "1331_1400", "label": "13:31-14:00", "start": 1331, "end": 1400},
    {"id": "1401_1430", "label": "14:01-14:30", "start": 1401, "end": 1430},
    {"id": "1431_1500", "label": "14:31-15:00", "start": 1431, "end": 1500},
    {"id": "1501_1530", "label": "15:01-15:30", "start": 1501, "end": 1530},
    {"id": "1531_1600", "label": "15:31-16:00", "start": 1531, "end": 1600},
]


class SnapshotController(BaseController):
    """Controller for snapshot-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def get_snapshots():
        """Return all available snapshot times for a given date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with list of times
        """
        date_iso = request.args.get("date")
        if not date_iso:
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data={"times": []})
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 0
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response({"times": []})
        
        try:
            ndate = int(date_iso.replace("-", ""))
            with get_connection() as con:
                cursor = con.execute(
                    "SELECT DISTINCT ntime FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                    (ndate,)
                )
                times = [row[0] for row in cursor.fetchall()]
            
            # Return plain object for backward compatibility with original /api/snapshots
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data={"times": times})
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': len(times)
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response({"times": times})
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
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
            
            response = BaseController.success_response(data=data)
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def get_snapshots_summary():
        """Return a compact summary row for every available time-slot on a date.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            
        Returns:
            JSON response with summary rows
        """
        date_iso = request.args.get("date")
        if not date_iso:
            response = BaseController.success_response(data={"date": date_iso, "rows": []})
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 0
                }
            return BaseController.json_response(response)
        
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
            
            response = BaseController.success_response(data={"date": date_iso, "rows": rows})
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': len(rows)
                }
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def get_snapshots_all():
        """Return all snapshots with pagination for Distribution page.

        Includes both historical and today's live data.

        Query params:
            offset: pagination offset (default 0)
            limit: rows per page (default 200, max 500)
            regime: time regime filter (e.g., "0930_1000", "pre")
            
        Returns:
            JSON response with paginated snapshots
        """
        from datetime import datetime as _dt
        today_ndate = int(_dt.now(ZoneInfo("America/New_York")).strftime("%Y%m%d"))

        offset = int(request.args.get("offset", 0))
        limit = min(int(request.args.get("limit", 200)), 500)
        regime_id = request.args.get("regime", "0930_1000")

        # Get time range for selected regime
        regime = next((r for r in TIME_REGIMES if r["id"] == regime_id), TIME_REGIMES[1])
        time_start = regime["start"]
        time_end = regime["end"]

        try:
            with get_connection() as con:
                # Get total count (historical + today's live) filtered by regime
                total_hist = con.execute(
                    """SELECT COUNT(*) FROM snapshot
                       WHERE symbol='SPX' AND ndate < ? AND ntime >= ? AND ntime <= ?""",
                    (today_ndate, time_start, time_end)
                ).fetchone()[0]
                total_live = con.execute(
                    """SELECT COUNT(*) FROM snapshot
                       WHERE ndate=? AND source='gex' AND ntime >= ? AND ntime <= ?""",
                    (today_ndate, time_start, time_end)
                ).fetchone()[0]
                total = total_hist + total_live

                # Get paginated historical rows
                hist_rows = con.execute(
                    """SELECT ndate, ntime, uprice, net_gex, sentiment, gex_ratio, kcs, dominance,
                       total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                       total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                       total_call_vol, total_put_vol, key_call_vol, key_put_vol
                       FROM snapshot
                       WHERE symbol='SPX' AND ndate < ? AND ntime >= ? AND ntime <= ?
                       ORDER BY ndate DESC, ntime DESC
                       LIMIT ? OFFSET ?""",
                    (today_ndate, time_start, time_end, limit, offset)
                ).fetchall()

                # Get today's live rows (only on first page)
                live_rows = []
                if offset == 0:
                    live_rows = con.execute(
                        """SELECT ndate, ntime, uprice, sentiment, gex_ratio, net_gex, kcs, dominance,
                           total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                           total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                           total_call_vol, total_put_vol, key_call_vol, key_put_vol
                           FROM snapshot
                           WHERE ndate=? AND source='gex' AND ntime >= ? AND ntime <= ?
                           ORDER BY ntime DESC""",
                        (today_ndate, time_start, time_end)
                    ).fetchall()

            snapshots = []

            # Process live rows first
            for r in live_rows:
                ndate, ntime, spx_last, sentiment, gex_ratio, net_gex, kcs, dominance, \
                total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, \
                total_call_oi, total_put_oi, key_call_oi, key_put_oi, \
                total_call_vol, total_put_vol, key_call_vol, key_put_vol = r
                ndate_str = str(ndate)
                date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
                time_str = f"{ntime // 100:02d}:{ntime % 100:02d}"
                snapshots.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "date": date_str,
                    "time": time_str,
                    "uprice": spx_last,
                    "net_gex": net_gex,
                    "sentiment": sentiment,
                    "gex_ratio": gex_ratio,
                    "kcs": kcs,
                    "dominance": dominance,
                    "total_call_gex": total_call_gex,
                    "total_put_gex": total_put_gex,
                    "key_strike": key_strike,
                    "key_call_gex": key_call_gex,
                    "key_put_gex": key_put_gex,
                    "total_call_oi": total_call_oi,
                    "total_put_oi": total_put_oi,
                    "key_call_oi": key_call_oi,
                    "key_put_oi": key_put_oi,
                    "total_call_vol": total_call_vol,
                    "total_put_vol": total_put_vol,
                    "key_call_vol": key_call_vol,
                    "key_put_vol": key_put_vol,
                })

            # Process historical rows
            for r in hist_rows:
                ndate, ntime, uprice, net_gex, sentiment, gex_ratio, kcs, dominance, \
                total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, \
                total_call_oi, total_put_oi, key_call_oi, key_put_oi, \
                total_call_vol, total_put_vol, key_call_vol, key_put_vol = r
                ndate_str = str(ndate)
                date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
                time_str = f"{ntime // 100:02d}:{ntime % 100:02d}"
                snapshots.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "date": date_str,
                    "time": time_str,
                    "uprice": uprice,
                    "net_gex": net_gex,
                    "sentiment": sentiment,
                    "gex_ratio": gex_ratio,
                    "kcs": kcs,
                    "dominance": dominance,
                    "total_call_gex": total_call_gex,
                    "total_put_gex": total_put_gex,
                    "key_strike": key_strike,
                    "key_call_gex": key_call_gex,
                    "key_put_gex": key_put_gex,
                    "total_call_oi": total_call_oi,
                    "total_put_oi": total_put_oi,
                    "key_call_oi": key_call_oi,
                    "key_put_oi": key_put_oi,
                    "total_call_vol": total_call_vol,
                    "total_put_vol": total_put_vol,
                    "key_call_vol": key_call_vol,
                    "key_put_vol": key_put_vol,
                })

            # Sort combined results by date/time descending
            snapshots.sort(key=lambda x: (x["ndate"], x["ntime"]), reverse=True)

            response = BaseController.success_response(data={
                "snapshots": snapshots,
                "total": total,
                "offset": offset,
                "limit": limit,
                "regime": regime_id
            })
            
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': len(snapshots)
                }
            
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
