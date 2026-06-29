"""Controller for snapshot API endpoints."""

import json
import math
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from dao.snapshot_dao import SnapshotDAO
from middleware.test_mode import with_test_metadata


# Constants
RTH_OPEN = 935  # Regular Trading Hours start (ET)
TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]


# Time regimes for filtering snapshots
TIME_REGIMES = [
    {"id": "pre", "label": "Pre-market", "start": 0, "end": 934},
    {"id": "0935_1000", "label": "09:35-10:00", "start": 935, "end": 1000},
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
    {"id": "1531_1555", "label": "15:31-15:55", "start": 1531, "end": 1555},
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
                    "SELECT DISTINCT ntime FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime DESC",
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
        """Get a single snapshot by date and time with chart data.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 930)
            prev_time: optional previous time for comparison
            
        Returns:
            JSON response with snapshot data including chart arrays
        """
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 935))
        prev_t = request.args.get("prev_time")
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("Missing required parameter: date"),
                400
            )
        
        try:
            # Load snapshot data
            data = SnapshotController._load_snapshot(date_iso, ntime)
            if data is None:
                return BaseController.json_response(
                    BaseController.error_response("No GEX data for this date/time"),
                    404
                )
            
            # Summarize snapshot
            snap = SnapshotController._summarise_snapshot(data)
            
            # Load previous snapshot if requested
            prev_snap = None
            if prev_t:
                prev_data = SnapshotController._load_snapshot(date_iso, int(prev_t))
                if prev_data:
                    prev_snap = SnapshotController._summarise_snapshot(prev_data)
            
            # Compute strike data for charts (20 strikes below + 20 above underlying)
            uprice = snap.get("uprice", 0)
            all_rows = sorted(
                [r for r in (data.get("data") or []) if r.get("strike") is not None],
                key=lambda r: r["strike"]
            )
            below = [r for r in all_rows if r["strike"] < uprice]
            above = [r for r in all_rows if r["strike"] >= uprice]
            rows = below[-20:] + above[:20]
            
            strikes   = [r["strike"] for r in rows]
            call_gex  = [r.get("cg",   0) or 0 for r in rows]
            put_gex   = [r.get("pg",   0) or 0 for r in rows]
            net_gex   = [r.get("net",  0) or 0 for r in rows]
            call_oi   = [r.get("coi",  0) or 0 for r in rows]
            put_oi    = [-(r.get("poi", 0) or 0) for r in rows]
            call_vol  = [r.get("cvol", 0) or 0 for r in rows]
            put_vol   = [-(r.get("pvol", 0) or 0) for r in rows]
            
            # Cumulative net GEX from left to right
            cumulative_gex = []
            running = 0.0
            for v in net_gex:
                running += v
                cumulative_gex.append(round(running, 2))
            
            # Summary stats from 40-strike window
            total_call_oi  = sum(r.get("coi", 0) or 0 for r in rows)
            total_put_oi   = sum(r.get("poi", 0) or 0 for r in rows)
            total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
            total_put_vol  = sum(r.get("pvol", 0) or 0 for r in rows)
            
            snap["total_call_oi"]  = int(total_call_oi)
            snap["total_put_oi"]   = int(total_put_oi)
            snap["total_call_vol"] = int(total_call_vol)
            snap["total_put_vol"]  = int(total_put_vol)
            snap.update(SnapshotController._compute_key_strike_stats(rows, uprice))
            
            # SPX price data up to current time
            spx_bars = SnapshotController._get_spx_bars_from_db(date_iso, ntime)
            
            # Teaching points
            points = SnapshotController._teaching_points(snap, prev_snap, spx_bars)
            
            # Day classification
            day_type = SnapshotController._classify_gex_day(date_iso)
            
            is_pre = 1 if ntime < RTH_OPEN else 0
            snap["is_premarket"] = is_pre
            
            # Build response
            response_data = {
                "summary":        snap,
                "day_type":       day_type,
                "strikes":        strikes,
                "call_gex":       call_gex,
                "put_gex":        put_gex,
                "net_gex":        net_gex,
                "cumulative_gex": cumulative_gex,
                "call_oi":        call_oi,
                "put_oi":         put_oi,
                "call_vol":       call_vol,
                "put_vol":        put_vol,
                "spx_bars":       spx_bars,
                "points":         points,
                "times":          TIMES,
                "ntime":          ntime,
                "is_premarket":   is_pre,
            }
            
            # Return plain data for backward compatibility with original /api/snapshot
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=response_data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(response_data)
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
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data={"date": date_iso, "rows": []})
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 0
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response({"date": date_iso, "rows": []})
        
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
            
            # Return plain object for backward compatibility with original /api/snapshots/summary
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data={"date": date_iso, "rows": rows})
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': len(rows)
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response({"date": date_iso, "rows": rows})
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

            # Return plain object for backward compatibility with original /api/snapshots/all
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data={
                    "snapshots": snapshots,
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "regime": regime_id
                })
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': len(snapshots)
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response({
                    "snapshots": snapshots,
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "regime": regime_id
                })
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    # -------------------------------------------------------------------------
    # Helper methods for chart data computation
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _load_snapshot(date_iso: str, ntime: int, symbol: str = "SPX") -> dict | None:
        """Load a single snapshot from the unified snapshot table."""
        ndate = int(date_iso.replace("-", ""))
        with get_connection() as con:
            row = con.execute(
                "SELECT uprice, raw_json, source, sentiment, gex_ratio, net_gex, kcs, dominance, "
                "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, hmm_state, hmm_label "
                "FROM snapshot "
                "WHERE ndate=? AND ntime=? AND symbol=?",
                (ndate, ntime, symbol),
            ).fetchone()
        if row:
            parsed = json.loads(row[1]) if row[1] else {"data": []}
            data_list = parsed.get("data") if isinstance(parsed, dict) else parsed
            return {
                "uprice": row[0],
                "data": data_list,
                "source": row[2],
                "sentiment": row[3],
                "gex_ratio": row[4],
                "net_gex": row[5],
                "kcs": row[6],
                "dominance": row[7],
                "total_call_gex": row[8],
                "total_put_gex": row[9],
                "key_strike": row[10],
                "key_call_gex": row[11],
                "key_put_gex": row[12],
                "total_call_oi": row[13],
                "total_put_oi": row[14],
                "key_call_oi": row[15],
                "key_put_oi": row[16],
                "total_call_vol": row[17],
                "total_put_vol": row[18],
                "key_call_vol": row[19],
                "key_put_vol": row[20],
                "key2_strike": row[21],
                "key2_abs": row[22],
                "key2_call_vol": row[23],
                "key2_put_vol": row[24],
                "flip": row[25],
                "hmm_state": row[26],
                "hmm_label": row[27],
            }
        return None
    
    @staticmethod
    def _summarise_snapshot(data: dict) -> dict:
        """Summarise snapshot data. If flat columns are present, use them directly."""
        if "net_gex" in data and data["net_gex"] is not None:
            key_call_gex = data.get("key_call_gex") or 0
            key_put_gex = data.get("key_put_gex") or 0
            key_call_oi = data.get("key_call_oi") or 0
            key_put_oi = data.get("key_put_oi") or 0
            key_call_vol = data.get("key_call_vol") or 0
            key_put_vol = data.get("key_put_vol") or 0
            return {
                "uprice": data.get("uprice", 0),
                "net_gex": data.get("net_gex", 0),
                "call_gex": data.get("total_call_gex", 0),
                "put_gex": data.get("total_put_gex", 0),
                "sentiment_pct": data.get("sentiment", 50),
                "gex_ratio": data.get("gex_ratio", 0),
                "kcs": data.get("kcs", 0),
                "dominance": data.get("dominance", 0),
                "key_strike": data.get("key_strike", 0),
                "key_call_gex": key_call_gex,
                "key_put_gex": key_put_gex,
                "key_net_gex": key_call_gex - key_put_gex,
                "total_call_oi": data.get("total_call_oi", 0),
                "total_put_oi": data.get("total_put_oi", 0),
                "key_call_oi": key_call_oi,
                "key_put_oi": key_put_oi,
                "key_net_oi": key_call_oi - key_put_oi,
                "total_call_vol": data.get("total_call_vol", 0),
                "total_put_vol": data.get("total_put_vol", 0),
                "key_call_vol": key_call_vol,
                "key_put_vol": key_put_vol,
                "key_net_vol": key_call_vol - key_put_vol,
                "key2_strike": data.get("key2_strike"),
                "key2_abs": data.get("key2_abs"),
                "key2_call_vol": data.get("key2_call_vol"),
                "key2_put_vol": data.get("key2_put_vol"),
                "flip": data.get("flip"),
                "hmm_state": data.get("hmm_state"),
                "hmm_label": data.get("hmm_label"),
                "source": data.get("source"),
            }
        
        rows = data.get("data", [])
        if not rows:
            return {"uprice": 0, "net_gex": 0, "call_gex": 0, "put_gex": 0}
        
        uprice = data.get("uprice", 0)
        all_rows = sorted([r for r in rows if r.get("strike") is not None], key=lambda r: r["strike"])
        below = [r for r in all_rows if r["strike"] < uprice]
        above = [r for r in all_rows if r["strike"] >= uprice]
        rows = below[-20:] + above[:20]
        
        call_gex = sum(r.get("cg", 0) or 0 for r in rows)
        put_gex = sum(r.get("pg", 0) or 0 for r in rows)
        net_gex = call_gex - put_gex
        
        pos_bars = sum(1 for r in rows if (r.get("net", 0) or 0) > 0)
        sentiment_pct = round(pos_bars / len(rows) * 100) if rows else 50
        
        if call_gex > put_gex:
            gex_ratio = round(call_gex / put_gex, 1) if put_gex else 0
        else:
            gex_ratio = round(-put_gex / call_gex, 1) if call_gex else 0
        
        return {
            "uprice": uprice,
            "net_gex": net_gex,
            "call_gex": call_gex,
            "put_gex": put_gex,
            "sentiment_pct": sentiment_pct,
            "gex_ratio": gex_ratio,
        }
    
    @staticmethod
    def _compute_key_strike_stats(rows: list, uprice: float) -> dict:
        """Compute key-strike dominance and KCS from the 40-strike window rows."""
        if not rows:
            return {}
        total_abs = sum(abs(r.get("abs", 0) or 0) for r in rows)
        total_oi  = sum((r.get("coi", 0) or 0) + (r.get("poi", 0) or 0) for r in rows)
        total_vol = sum((r.get("cvol", 0) or 0) + (r.get("pvol", 0) or 0) for r in rows)

        key_row    = max(rows, key=lambda r: abs(r.get("abs", 0) or 0)
                                     * math.exp(-abs(r["strike"] - uprice) / 25.0))
        key_strike = key_row["strike"]
        key_abs    = abs(key_row.get("abs", 0) or 0)
        key_cg     = key_row.get("cg", 0) or 0
        key_pg     = key_row.get("pg", 0) or 0
        key_coi    = key_row.get("coi",  0) or 0
        key_poi    = key_row.get("poi",  0) or 0
        key_cvol   = key_row.get("cvol", 0) or 0
        key_pvol   = key_row.get("pvol", 0) or 0

        key_dominance_pct = round(key_abs / total_abs * 100, 1) if total_abs else 0.0

        distance  = abs(key_strike - uprice)
        prox      = math.exp(-distance / 25.0)
        gex_share = key_abs / total_abs  if total_abs  else 0.0
        oi_share  = (key_coi + key_poi)  / total_oi   if total_oi   else 0.0
        vol_share = (key_cvol + key_pvol) / total_vol  if total_vol  else 0.0
        kcs = round((0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * prox * 100, 2)

        other_rows = [r for r in rows if r["strike"] != key_strike]
        key2_row   = max(other_rows, key=lambda r: abs(r.get("abs", 0) or 0)
                                                   * math.exp(-abs(r["strike"] - uprice) / 25.0)) if other_rows else None
        key2_strike = key2_row["strike"] if key2_row else None
        key2_abs    = abs(key2_row.get("abs", 0) or 0) if key2_row else None
        key2_cvol   = key2_row.get("cvol", 0) or 0 if key2_row else None
        key2_pvol   = key2_row.get("pvol", 0) or 0 if key2_row else None

        return {
            "key_strike": key_strike,
            "key_absolute": key_abs,
            "key_call_gex": key_cg,
            "key_put_gex": key_pg,
            "key_net": key_cg - key_pg,
            "key_dominance_pct": key_dominance_pct,
            "kcs": kcs,
            "key_call_oi": key_coi,
            "key_put_oi": key_poi,
            "key_net_oi": key_coi - key_poi,
            "key_call_vol": key_cvol,
            "key_put_vol": key_pvol,
            "key_net_vol": key_cvol - key_pvol,
            "key2_strike": key2_strike,
            "key2_abs": key2_abs,
            "key2_call_vol": key2_cvol,
            "key2_put_vol": key2_pvol,
        }
    
    @staticmethod
    def _get_spx_bars_from_db(date_iso: str, up_to_ntime: int) -> list:
        """Return per-snapshot RTH price bars from snapshot uprice for the chart."""
        ndate = int(date_iso.replace("-", ""))
        with get_connection() as con:
            rows = con.execute(
                "SELECT ntime, uprice FROM snapshot "
                "WHERE ndate=? AND uprice IS NOT NULL AND ntime>=? AND ntime<=? ORDER BY ntime",
                (ndate, RTH_OPEN, up_to_ntime),
            ).fetchall()
        bars = []
        for ntime, price in rows:
            t = f"{ntime:04d}"
            ts = f"{t[:2]}:{t[2:]}"
            bars.append({"time_str": ts, "Open": price, "High": price, "Low": price, "Close": price})
        return bars
    
    @staticmethod
    def _teaching_points(snap: dict, prev_snap: dict | None, spx_rows: list) -> list:
        """Generate teaching points for the snapshot."""
        points = []
        uprice = snap.get("uprice", 0)
        net    = snap.get("net_gex", 0)
        wall   = snap.get("wall")
        flip   = snap.get("flip")

        if net < 0:
            mag = "strongly" if abs(net) > 5e9 else "moderately"
            points.append({
                "type": "danger",
                "icon": "⚡",
                "title": "Negative GEX — Dealers AMPLIFY moves",
                "text": (f"Net GEX is {net/1e9:.1f}B ({mag} negative). "
                         "Dealers are SHORT gamma — when price rises they must BUY to hedge, "
                         "and when price falls they must SELL. This amplifies momentum. "
                         "Breakouts are more likely to follow through. "
                         "Expect larger 30-min candles.")
            })
        else:
            mag = "strongly" if net > 5e9 else "moderately"
            points.append({
                "type": "success",
                "icon": "🧲",
                "title": "Positive GEX — Dealers SUPPRESS moves",
                "text": (f"Net GEX is {net/1e9:.1f}B ({mag} positive). "
                         "Dealers are LONG gamma — when price rises they SELL to hedge, "
                         "and when price falls they BUY. This dampens momentum and "
                         "creates mean-reversion pressure. Breakouts often fail here.")
            })

        key_strike = snap.get("key_strike")
        if key_strike:
            dist_pct = abs(key_strike - uprice) / uprice * 100 if uprice else 0
            points.append({
                "type": "info",
                "icon": "🎯",
                "title": f"Key Strike at {key_strike} ({dist_pct:.1f}% from spot)",
                "text": (f"Maximum gamma concentration. "
                         f"Key call GEX: {snap.get('key_call_gex', 0)/1e9:.2f}B, "
                         f"Key put GEX: {snap.get('key_put_gex', 0)/1e9:.2f}B. "
                         f"Key net: {(snap.get('key_call_gex', 0) - snap.get('key_put_gex', 0))/1e9:.2f}B. "
                         f"Dominance: {snap.get('key_dominance_pct', 0):.1f}%.")
            })

        if flip:
            points.append({
                "type": "warning",
                "icon": "🔄",
                "title": "Gamma Flip Detected",
                "text": f"Net GEX changed sign across strikes at {flip}. This often marks support/resistance levels."
            })

        if wall:
            points.append({
                "type": "info",
                "icon": "🧱",
                "title": "Gamma Wall",
                "text": f"Large call wall at {wall}. Can act as resistance if price approaches."
            })

        return points
    
    @staticmethod
    def _classify_gex_day(date_iso: str) -> dict:
        """Classify the GEX day type using all available snapshots."""
        snapshots = []
        for t in TIMES:
            raw = SnapshotController._load_snapshot(date_iso, t)
            if raw:
                s = SnapshotController._summarise_snapshot(raw)
                s["time"] = t
                snapshots.append(s)
        if not snapshots:
            return {"type": "no-data", "label": "No Data", "description": "No GEX snapshots available."}

        nets = [s.get("net_gex", 0) for s in snapshots]
        avg_net = sum(nets) / len(nets) if nets else 0

        if avg_net < -5e9:
            return {
                "type": "strong-negative",
                "label": "Strongly Negative",
                "description": f"Average net GEX: {avg_net/1e9:.1f}B. Dealers amplify moves."
            }
        elif avg_net < 0:
            return {
                "type": "negative",
                "label": "Negative",
                "description": f"Average net GEX: {avg_net/1e9:.1f}B. Dealers amplify moves."
            }
        elif avg_net > 5e9:
            return {
                "type": "strong-positive",
                "label": "Strongly Positive",
                "description": f"Average net GEX: {avg_net/1e9:.1f}B. Dealers suppress moves."
            }
        else:
            return {
                "type": "positive",
                "label": "Positive",
                "description": f"Average net GEX: {avg_net/1e9:.1f}B. Dealers suppress moves."
            }
    
    # -------------------------------------------------------------------------
    # Data normalization layer for live/historical formats
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _normalize_live_to_historical(live_data: dict, ndate: int = None, ntime: int = None) -> dict:
        """Normalize live data format (market.gex) to historical format (market.histgex).

        Live data format:
            - symbol, last, low, high, data[]

        Historical format:
            - symbol, ndate, ntime, uprice, data[]

        Args:
            live_data: Live data from OptionAlpha market.gex API
            ndate: Optional date override (YYYYMMDD format) for testing
            ntime: Optional time override (HHMM format) for testing

        Returns:
            Normalized data in historical format with current timestamp (or overridden values)
        """
        if ndate is None or ntime is None:
            now = datetime.now(timezone.utc)
            ndate = int(now.strftime("%Y%m%d")) if ndate is None else ndate
            ntime = int(now.strftime("%H%M")) if ntime is None else ntime

        return {
            "symbol": live_data.get("symbol", "SPX"),
            "ndate": ndate,
            "ntime": ntime,
            "uprice": live_data.get("last", 0),
            "data": live_data.get("data", []),
        }
    
    @staticmethod
    def _validate_historical_format(data: dict) -> tuple[bool, str]:
        """Validate historical snapshot data format.
        
        Required fields: symbol, ndate, ntime, uprice, data
        
        Returns:
            (is_valid, error_message)
        """
        required_fields = ["symbol", "ndate", "ntime", "uprice", "data"]
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        if not isinstance(data["data"], list):
            return False, "data must be an array"
        
        if not isinstance(data["ndate"], int) or data["ndate"] < 20200000 or data["ndate"] > 20991231:
            return False, "ndate must be a valid integer in YYYYMMDD format"
        
        if not isinstance(data["ntime"], int) or data["ntime"] < 0 or data["ntime"] > 2359:
            return False, "ntime must be a valid integer in HHMM format"
        
        if not isinstance(data["uprice"], (int, float)) or data["uprice"] <= 0:
            return False, "uprice must be a positive number"
        
        return True, ""
    
    @staticmethod
    def _validate_live_format(data: dict) -> tuple[bool, str]:
        """Validate live snapshot data format.
        
        Required fields: symbol, last, data
        
        Returns:
            (is_valid, error_message)
        """
        required_fields = ["symbol", "last", "data"]
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        if not isinstance(data["data"], list):
            return False, "data must be an array"
        
        if not isinstance(data["last"], (int, float)) or data["last"] <= 0:
            return False, "last must be a positive number"
        
        return True, ""
    
    # -------------------------------------------------------------------------
    # Upsert endpoints for historical and live snapshots
    # -------------------------------------------------------------------------
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def upsert_historical_snapshot():
        """Upsert a historical snapshot from OptionAlpha market.histgex API.
        
        POST /mvc/api/snapshot/historical
        
        Request body (historical format):
            {
                "symbol": "SPX",
                "ndate": 20260625,
                "ntime": 1400,
                "uprice": 7358.22,
                "data": [...]
            }
        
        Returns:
            JSON response with success/error status
        """
        if request.method != "POST":
            return BaseController.json_response(
                BaseController.error_response("Method not allowed"),
                405
            )
        
        try:
            data = request.get_json()
            if not data:
                return BaseController.json_response(
                    BaseController.error_response("Request body is required"),
                    400
                )
            
            # Validate format
            is_valid, error_msg = SnapshotController._validate_historical_format(data)
            if not is_valid:
                return BaseController.json_response(
                    BaseController.error_response(error_msg),
                    400
                )
            
            # Compute flat columns from raw data
            rows = data.get("data", [])
            uprice = data.get("uprice", 0)
            
            # Compute summary stats
            call_gex = sum(r.get("cg", 0) or 0 for r in rows)
            put_gex = sum(r.get("pg", 0) or 0 for r in rows)
            net_gex = call_gex - put_gex
            
            # Sentiment
            pos_bars = sum(1 for r in rows if (r.get("net", 0) or 0) > 0)
            sentiment_pct = round(pos_bars / len(rows) * 100) if rows else 50
            
            # GEX ratio
            if call_gex > put_gex:
                gex_ratio = round(call_gex / put_gex, 1) if put_gex else 0
            else:
                gex_ratio = round(-put_gex / call_gex, 1) if call_gex else 0
            
            # Key strike stats - filter to 20 strikes below and 20 above SPX
            sorted_rows = sorted(rows, key=lambda r: r["strike"])
            # Find the index of the strike closest to uprice
            uprice_idx = min(range(len(sorted_rows)), key=lambda i: abs(sorted_rows[i]["strike"] - uprice))
            # Take 20 strikes before and 20 after (40-strike window)
            window_rows = sorted_rows[max(0, uprice_idx - 20):min(len(sorted_rows), uprice_idx + 21)]
            key_stats = SnapshotController._compute_key_strike_stats(window_rows, uprice)
            
            # Total OI and Vol
            total_call_oi = sum(r.get("coi", 0) or 0 for r in rows)
            total_put_oi = sum(r.get("poi", 0) or 0 for r in rows)
            total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
            total_put_vol = sum(r.get("pvol", 0) or 0 for r in rows)
            
            # Prepare database values
            ndate = data["ndate"]
            ntime = data["ntime"]
            symbol = data["symbol"]
            raw_json = json.dumps(data)
            capture_ts = datetime.now(timezone.utc).isoformat()
            source = "test" if request.args.get("test") == "1" else "histgex"
            
            # Upsert to database
            with get_connection() as con:
                con.execute(
                    """INSERT OR REPLACE INTO snapshot 
                    (ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                     sentiment_pct, gex_ratio, net_gex, key_stats.get("kcs", 0), key_stats.get("key_dominance_pct", 0),
                     call_gex, put_gex, key_stats.get("key_strike", 0), key_stats.get("key_call_gex", 0), key_stats.get("key_put_gex", 0),
                     total_call_oi, total_put_oi, key_stats.get("key_call_oi", 0), key_stats.get("key_put_oi", 0),
                     total_call_vol, total_put_vol, key_stats.get("key_call_vol", 0), key_stats.get("key_put_vol", 0),
                     key_stats.get("key2_strike"), key_stats.get("key2_abs"), key_stats.get("key2_call_vol", 0), key_stats.get("key2_put_vol", 0))
                )
                con.commit()
            
            response_data = {
                "success": True,
                "message": "Historical snapshot upserted successfully",
                "ndate": ndate,
                "ntime": ntime,
                "symbol": symbol
            }
            
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=response_data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(response_data)
                
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def upsert_live_snapshot():
        """Upsert a live snapshot from OptionAlpha market.gex API.

        POST /mvc/api/snapshot/live

        Query params (required):
            - date: YYYY-MM-DD format
            - time: HHMM format

        Request body (live format):
            {
                "symbol": "SPX",
                "last": 7354.02,
                "low": {...},
                "high": {...},
                "data": [...]
            }

        Returns:
            JSON response with success/error status
        """
        if request.method != "POST":
            return BaseController.json_response(
                BaseController.error_response("Method not allowed"),
                405
            )

        try:
            # Require date and time query parameters
            date_str = request.args.get("date")
            time_str = request.args.get("time")
            if not date_str or not time_str:
                return BaseController.json_response(
                    BaseController.error_response("date and time query parameters are required"),
                    400
                )

            ndate = int(date_str.replace("-", ""))
            ntime = int(time_str)

            data = request.get_json()
            if not data:
                return BaseController.json_response(
                    BaseController.error_response("Request body is required"),
                    400
                )

            # Validate format
            is_valid, error_msg = SnapshotController._validate_live_format(data)
            if not is_valid:
                return BaseController.json_response(
                    BaseController.error_response(error_msg),
                    400
                )

            # Normalize live to historical format with provided date/time
            normalized = SnapshotController._normalize_live_to_historical(data, ndate, ntime)
            
            # Compute flat columns from raw data
            rows = normalized.get("data", [])
            uprice = normalized.get("uprice", 0)
            
            # Compute summary stats
            call_gex = sum(r.get("cg", 0) or 0 for r in rows)
            put_gex = sum(r.get("pg", 0) or 0 for r in rows)
            net_gex = call_gex - put_gex
            
            # Sentiment
            pos_bars = sum(1 for r in rows if (r.get("net", 0) or 0) > 0)
            sentiment_pct = round(pos_bars / len(rows) * 100) if rows else 50
            
            # GEX ratio
            if call_gex > put_gex:
                gex_ratio = round(call_gex / put_gex, 1) if put_gex else 0
            else:
                gex_ratio = round(-put_gex / call_gex, 1) if call_gex else 0
            
            # Key strike stats - filter to 20 strikes below and 20 above SPX
            sorted_rows = sorted(rows, key=lambda r: r["strike"])
            # Find the index of the strike closest to uprice
            uprice_idx = min(range(len(sorted_rows)), key=lambda i: abs(sorted_rows[i]["strike"] - uprice))
            # Take 20 strikes before and 20 after (40-strike window)
            window_rows = sorted_rows[max(0, uprice_idx - 20):min(len(sorted_rows), uprice_idx + 21)]
            key_stats = SnapshotController._compute_key_strike_stats(window_rows, uprice)
            
            # Total OI and Vol
            total_call_oi = sum(r.get("coi", 0) or 0 for r in rows)
            total_put_oi = sum(r.get("poi", 0) or 0 for r in rows)
            total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
            total_put_vol = sum(r.get("pvol", 0) or 0 for r in rows)
            
            # Prepare database values
            ndate = normalized["ndate"]
            ntime = normalized["ntime"]
            symbol = normalized["symbol"]
            raw_json = json.dumps(normalized)
            capture_ts = datetime.now(timezone.utc).isoformat()
            source = "test" if request.args.get("test") == "1" else "gex"
            
            # Upsert to database
            with get_connection() as con:
                con.execute(
                    """INSERT OR REPLACE INTO snapshot 
                    (ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                     sentiment_pct, gex_ratio, net_gex, key_stats.get("kcs", 0), key_stats.get("key_dominance_pct", 0),
                     call_gex, put_gex, key_stats.get("key_strike", 0), key_stats.get("key_call_gex", 0), key_stats.get("key_put_gex", 0),
                     total_call_oi, total_put_oi, key_stats.get("key_call_oi", 0), key_stats.get("key_put_oi", 0),
                     total_call_vol, total_put_vol, key_stats.get("key_call_vol", 0), key_stats.get("key_put_vol", 0),
                     key_stats.get("key2_strike"), key_stats.get("key2_abs"), key_stats.get("key2_call_vol", 0), key_stats.get("key2_put_vol", 0))
                )
                con.commit()
            
            response_data = {
                "success": True,
                "message": "Live snapshot upserted successfully",
                "ndate": ndate,
                "ntime": ntime,
                "symbol": symbol
            }
            
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=response_data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(response_data)
                
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def find_test_snapshots():
        """Find all test snapshots (source='test') for admin cleanup.
        
        GET /mvc/api/snapshot/test
        
        Query params (optional):
            - symbol: filter by symbol, default "SPX"
        
        Returns:
            JSON response with list of test snapshots
        """
        if request.method != "GET":
            return BaseController.json_response(
                BaseController.error_response("Method not allowed"),
                405
            )
        
        try:
            symbol = request.args.get("symbol", "SPX")

            # Query for test snapshots
            with get_connection() as con:
                cursor = con.execute(
                    "SELECT ndate, ntime, symbol, source, uprice FROM snapshot WHERE source='test' AND symbol=? ORDER BY ndate DESC, ntime DESC",
                    (symbol,)
                )
                rows = cursor.fetchall()

            snapshots = []
            for row in rows:
                ndate, ntime, sym, source, uprice = row
                snapshots.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "symbol": sym,
                    "source": source,
                    "uprice": uprice
                })

            return BaseController.json_response({
                "success": True,
                "count": len(snapshots),
                "snapshots": snapshots
            })

        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )

    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def get_strike_window_entries():
        """Get all gex_strike_window entries for a specific date.

        GET /mvc/api/gex/strike-window?date=2026-06-23&symbol=SPX

        Query params:
            - date: YYYY-MM-DD format (required)
            - symbol: optional, default "SPX"

        Returns:
            JSON response with list of strike window entries
        """
        try:
            date_str = request.args.get("date")
            if not date_str:
                return BaseController.json_response(
                    BaseController.error_response("Missing required parameter: date"),
                    400
                )

            # Convert YYYY-MM-DD to YYYYMMDD
            try:
                from datetime import datetime
                ndate = int(datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d"))
            except ValueError:
                return BaseController.json_response(
                    BaseController.error_response("Invalid date format, use YYYY-MM-DD"),
                    400
                )

            symbol = request.args.get("symbol", "SPX")
            source = request.args.get("source", "gex")

            # Query gex_strike_window table
            with get_connection() as con:
                cursor = con.execute(
                    """SELECT ndate, ntime, symbol, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND symbol=? AND source=?
                       ORDER BY ntime""",
                    (ndate, symbol, source)
                )
                rows = cursor.fetchall()

            entries = []
            for row in rows:
                ndate, ntime, sym, price, data = row
                strikes = json.loads(data) if data else []
                entries.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "symbol": sym,
                    "price": price,
                    "strike_count": len(strikes),
                    "data": strikes
                })

            return BaseController.json_response({
                "success": True,
                "count": len(entries),
                "entries": entries
            })

        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )

    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def get_strike_window_csv():
        """Get gex_strike_window entries for a specific date in CSV format.

        GET /mvc/api/gex/strike-window/csv?date=2026-06-23&symbol=SPX

        Query params:
            - date: YYYY-MM-DD format (required)
            - symbol: optional, default "SPX"

        Returns:
            CSV response with strike data in table format
        """
        try:
            date_str = request.args.get("date")
            if not date_str:
                return BaseController.json_response(
                    BaseController.error_response("Missing required parameter: date"),
                    400
                )

            # Convert YYYY-MM-DD to YYYYMMDD
            try:
                from datetime import datetime
                ndate = int(datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d"))
            except ValueError:
                return BaseController.json_response(
                    BaseController.error_response("Invalid date format, use YYYY-MM-DD"),
                    400
                )

            symbol = request.args.get("symbol", "SPX")
            source = request.args.get("source", "gex")

            # Query gex_strike_window table
            with get_connection() as con:
                cursor = con.execute(
                    """SELECT ndate, ntime, symbol, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND symbol=? AND source=?
                       ORDER BY ntime""",
                    (ndate, symbol, source)
                )
                rows = cursor.fetchall()

            # Build CSV
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(["ndate", "ntime", "symbol", "price", "strike_index", "strike", "cg", "pg", "abs", "coi", "poi", "cvol", "pvol", "net"])

            # Data rows
            for row in rows:
                ndate, ntime, sym, price, data = row
                strikes = json.loads(data) if data else []

                for idx, strike in enumerate(strikes):
                    writer.writerow([
                        ndate,
                        ntime,
                        sym,
                        price,
                        idx,
                        strike.get("strike", ""),
                        strike.get("cg", 0),
                        strike.get("pg", 0),
                        strike.get("abs", 0),
                        strike.get("coi", 0),
                        strike.get("poi", 0),
                        strike.get("cvol", 0),
                        strike.get("pvol", 0),
                        strike.get("net", 0)
                    ])

            csv_data = output.getvalue()
            output.close()

            from flask import Response
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename=strike_window_{date_str}_{symbol}.csv"}
            )

        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )

    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def upsert_gex():
        """Upsert GEX strike window data from either historical or live format.

        POST /mvc/api/gex/upsert

        Request body (historical format):
            {
                "symbol": "SPX",
                "ndate": 20260625,
                "ntime": 1400,
                "uprice": 7358.22,
                "data": [...]
            }

        Request body (live format):
            {
                "symbol": "SPX",
                "last": 7358.22,
                "data": [...]
            }
        Query params (for live format):
            - date: YYYY-MM-DD format (required for live format)
            - time: HHMM format (required for live format)
            - source: optional, default "gex"

        Returns:
            JSON response with success/error status
        """
        if request.method != "POST":
            return BaseController.json_response(
                BaseController.error_response("Method not allowed"),
                405
            )

        try:
            data = request.get_json()
            if not data:
                return BaseController.json_response(
                    BaseController.error_response("Request body is required"),
                    400
                )

            # Handle OptionAlpha wrapped format (array with t, tid, api, data)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
                if "data" in data:
                    data = data["data"]

            # Detect format and normalize
            if "ndate" in data and "ntime" in data:
                # Historical format
                is_valid, error_msg = SnapshotController._validate_historical_format(data)
                if not is_valid:
                    return BaseController.json_response(
                        BaseController.error_response(error_msg),
                        400
                    )
                normalized = data
            elif "last" in data:
                # Live format - need date/time from query params
                date_str = request.args.get("date")
                time_str = request.args.get("time")
                if not date_str or not time_str:
                    return BaseController.json_response(
                        BaseController.error_response("date and time query parameters are required for live format"),
                        400
                    )

                ndate = int(date_str.replace("-", ""))
                ntime = int(time_str)

                is_valid, error_msg = SnapshotController._validate_live_format(data)
                if not is_valid:
                    return BaseController.json_response(
                        BaseController.error_response(error_msg),
                        400
                    )

                normalized = SnapshotController._normalize_live_to_historical(data, ndate, ntime)
            else:
                return BaseController.json_response(
                    BaseController.error_response("Invalid format: must be historical (ndate, ntime) or live (last) format"),
                    400
                )

            # Extract fields
            ndate = normalized["ndate"]
            ntime = normalized["ntime"]
            symbol = normalized["symbol"]
            uprice = normalized.get("uprice", 0)
            rows = normalized.get("data", [])
            
            # Determine source: test param overrides source param, default to 'gex'
            if request.args.get("test") == "1":
                source = "test"
            else:
                source = request.args.get("source", "gex")

            if not rows:
                return BaseController.json_response(
                    BaseController.error_response("No strike data provided"),
                    400
                )

            # Extract 40-strike window using the same logic
            sorted_rows = sorted(rows, key=lambda r: r["strike"])
            uprice_idx = min(range(len(sorted_rows)), key=lambda i: abs(sorted_rows[i]["strike"] - uprice))
            window_rows = sorted_rows[max(0, uprice_idx - 20):min(len(sorted_rows), uprice_idx + 20)]

            if not window_rows:
                return BaseController.json_response(
                    BaseController.error_response("Could not extract strike window"),
                    400
                )

            # Insert into gex_strike_window
            with get_connection() as con:
                con.execute(
                    """INSERT OR REPLACE INTO gex_strike_window
                       (ndate, ntime, symbol, source, price, data)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (ndate, ntime, symbol, source, uprice, json.dumps(window_rows))
                )
                con.commit()

            return BaseController.json_response({
                "success": True,
                "message": "GEX strike window data upserted successfully",
                "ndate": ndate,
                "ntime": ntime,
                "symbol": symbol,
                "source": source,
                "strike_count": len(window_rows)
            })

        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )

    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def compare_gex():
        """Compare two gex_strike_window records.

        GET /mvc/api/gex/compare
            ?date1=2026-06-23&time1=1000&symbol1=SPX&source1=gex
            &date2=2026-06-23&time2=1000&symbol2=SPX&source2=test

        Query params (all required):
            - date1, date2: YYYY-MM-DD format
            - time1, time2: HHMM format
            - symbol1, symbol2: symbol (e.g., SPX)
            - source1, source2: source (e.g., gex, test)

        Returns:
            JSON response with both records and a comparison
        """
        try:
            # Parse record 1
            date1 = request.args.get("date1")
            time1 = request.args.get("time1")
            symbol1 = request.args.get("symbol1", "SPX")
            source1 = request.args.get("source1", "gex")

            if not date1 or not time1:
                return BaseController.json_response(
                    BaseController.error_response("date1 and time1 are required"),
                    400
                )

            ndate1 = int(date1.replace("-", ""))
            ntime1 = int(time1)

            # Parse record 2
            date2 = request.args.get("date2")
            time2 = request.args.get("time2")
            symbol2 = request.args.get("symbol2", "SPX")
            source2 = request.args.get("source2", "gex")

            if not date2 or not time2:
                return BaseController.json_response(
                    BaseController.error_response("date2 and time2 are required"),
                    400
                )

            ndate2 = int(date2.replace("-", ""))
            ntime2 = int(time2)

            # Query both records
            with get_connection() as con:
                cursor1 = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND ntime=? AND symbol=? AND source=?""",
                    (ndate1, ntime1, symbol1, source1)
                )
                row1 = cursor1.fetchone()

                cursor2 = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND ntime=? AND symbol=? AND source=?""",
                    (ndate2, ntime2, symbol2, source2)
                )
                row2 = cursor2.fetchone()

            if not row1:
                return BaseController.json_response(
                    BaseController.error_response(f"Record 1 not found: {date1}-{time1} {symbol1} {source1}"),
                    404
                )

            if not row2:
                return BaseController.json_response(
                    BaseController.error_response(f"Record 2 not found: {date2}-{time2} {symbol2} {source2}"),
                    404
                )

            # Parse data
            ndate1_val, ntime1_val, sym1, src1, price1, data1 = row1
            ndate2_val, ntime2_val, sym2, src2, price2, data2 = row2

            strikes1 = json.loads(data1) if data1 else []
            strikes2 = json.loads(data2) if data2 else []

            # Compare strike counts
            count_match = len(strikes1) == len(strikes2)

            # Compare individual strikes
            strike_comparisons = []
            for i in range(max(len(strikes1), len(strikes2))):
                strike1 = strikes1[i] if i < len(strikes1) else None
                strike2 = strikes2[i] if i < len(strikes2) else None

                if strike1 and strike2:
                    # Compare key fields
                    fields_to_compare = ["strike", "cg", "pg", "abs", "coi", "poi", "cvol", "pvol", "net"]
                    differences = []
                    for field in fields_to_compare:
                        val1 = strike1.get(field, 0)
                        val2 = strike2.get(field, 0)
                        if val1 != val2:
                            differences.append({
                                "field": field,
                                "value1": val1,
                                "value2": val2
                            })

                    strike_comparisons.append({
                        "index": i,
                        "strike": strike1.get("strike"),
                        "match": len(differences) == 0,
                        "differences": differences
                    })
                else:
                    strike_comparisons.append({
                        "index": i,
                        "strike": strike1.get("strike") if strike1 else strike2.get("strike") if strike2 else None,
                        "match": False,
                        "differences": [{"field": "missing", "value1": strike1 is not None, "value2": strike2 is not None}]
                    })

            # Count differences
            total_differences = sum(1 for sc in strike_comparisons if not sc["match"])

            return BaseController.json_response({
                "success": True,
                "record1": {
                    "ndate": ndate1_val,
                    "ntime": ntime1_val,
                    "symbol": sym1,
                    "source": src1,
                    "price": price1,
                    "strike_count": len(strikes1)
                },
                "record2": {
                    "ndate": ndate2_val,
                    "ntime": ntime2_val,
                    "symbol": sym2,
                    "source": src2,
                    "price": price2,
                    "strike_count": len(strikes2)
                },
                "comparison": {
                    "strike_count_match": count_match,
                    "total_differences": total_differences,
                    "strike_comparisons": strike_comparisons
                }
            })

        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )

    @staticmethod
    @with_test_metadata(dao_name="SnapshotController")
    def delete_snapshot():
        """Delete a snapshot from the database.
        
        DELETE /mvc/api/snapshot
        
        Query params:
            - date: YYYY-MM-DD format
            - time: HHMM format
            - symbol: optional, default "SPX"
        
        Returns:
            JSON response with success/error status
        """
        if request.method != "DELETE":
            return BaseController.json_response(
                BaseController.error_response("Method not allowed"),
                405
            )
        
        try:
            date_iso = request.args.get("date")
            ntime = request.args.get("time")
            symbol = request.args.get("symbol", "SPX")
            
            if not date_iso or not ntime:
                return BaseController.json_response(
                    BaseController.error_response("date and time query parameters are required"),
                    400
                )
            
            # Convert date to ndate
            ndate = int(date_iso.replace("-", ""))
            ntime = int(ntime)
            
            # Delete from database
            with get_connection() as con:
                cursor = con.execute(
                    "DELETE FROM snapshot WHERE ndate=? AND ntime=? AND symbol=?",
                    (ndate, ntime, symbol)
                )
                con.commit()
                deleted_count = cursor.rowcount
            
            if deleted_count == 0:
                return BaseController.json_response(
                    BaseController.error_response("Snapshot not found"),
                    404
                )
            
            response_data = {
                "success": True,
                "message": "Snapshot deleted successfully",
                "ndate": ndate,
                "ntime": ntime,
                "symbol": symbol
            }
            
            if request.args.get('test_mode') == '1':
                response = BaseController.success_response(data=response_data)
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'SnapshotController',
                    'query_time_ms': 0,
                    'row_count': deleted_count
                }
                return BaseController.json_response(response)
            else:
                return BaseController.json_response(response_data)
                
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
