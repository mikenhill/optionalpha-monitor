"""
GexController for the new gex_strike_window table.
This controller reads from the normalized gex_strike_window table
and calculates metrics on-the-fly using separate calculation functions.
"""

import json
from flask import request
from controllers.base_controller import BaseController
from controllers.gex_calculations import (
    calculate_sentiment,
    calculate_gex_ratio,
    calculate_net_gex,
    calculate_kcs,
    calculate_dominance,
    calculate_key_strike_stats,
    calculate_total_oi_and_vol,
    calculate_total_gex
)
from dao.database import get_connection

# Time slots for percentile comparison
TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]

# Time regimes for distribution filtering
TIME_REGIMES = [
    {"id": "pre", "label": "Pre-Market", "start": 0, "end": 934},
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
    {"id": "1531_1600", "label": "15:31-16:00", "start": 1531, "end": 1600},
]


class GexController(BaseController):
    """Controller for GEX data from gex_strike_window table."""
    
    @staticmethod
    def get_gex_snapshots():
        """Get GEX snapshots for a specific date from gex_strike_window table.
        
        GET /api/gex/snapshots?date=2026-06-23&source=gex
        
        Query params:
            - date: YYYY-MM-DD format (required)
            - source: optional, default "gex"
        
        Returns:
            JSON response with calculated metrics for each snapshot
        """
        try:
            date_str = request.args.get("date")
            if not date_str:
                return BaseController.json_response(
                    BaseController.error_response("Missing required parameter: date"),
                    400
                )
            
            # Convert YYYY-MM-DD to YYYYMMDD
            from datetime import datetime
            ndate = int(datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d"))
            
            source = request.args.get("source", "gex")
            
            # Query gex_strike_window table
            with get_connection() as con:
                cursor = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data, hmm_label
                       FROM gex_strike_window
                       WHERE ndate=? AND source=?
                       ORDER BY ntime""",
                    (ndate, source)
                )
                rows = cursor.fetchall()
            
            snapshots = []
            for row in rows:
                ndate, ntime, symbol, src, price, data, hmm_label = row
                strikes = json.loads(data) if data else []
                
                if not strikes:
                    continue
                
                # Calculate all metrics using separate functions
                sentiment = calculate_sentiment(strikes)
                gex_ratio = calculate_gex_ratio(strikes)
                net_gex = calculate_net_gex(strikes)
                kcs = calculate_kcs(strikes, price)
                dominance = calculate_dominance(strikes, price)
                key_stats = calculate_key_strike_stats(strikes, price)
                total_oi_vol = calculate_total_oi_and_vol(strikes)
                total_gex_vals = calculate_total_gex(strikes)
                
                # Pre-market: times outside 09:35-15:55 range
                is_premarket = ntime < 935 or ntime > 1555
                
                snapshots.append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "symbol": symbol,
                    "source": src,
                    "uprice": price,
                    "sentiment": sentiment,
                    "gex_ratio": gex_ratio,
                    "net_gex": net_gex,
                    "kcs": kcs,
                    "dominance": dominance,
                    "key_strike": key_stats["key_strike"],
                    "key_call_gex": key_stats["key_call_gex"],
                    "key_put_gex": key_stats["key_put_gex"],
                    "key_call_oi": key_stats["key_call_oi"],
                    "key_put_oi": key_stats["key_put_oi"],
                    "key_call_vol": key_stats["key_call_vol"],
                    "key_put_vol": key_stats["key_put_vol"],
                    "key2_strike": key_stats["key2_strike"],
                    "key2_abs": key_stats["key2_abs"],
                    "key2_call_vol": key_stats["key2_call_vol"],
                    "key2_put_vol": key_stats["key2_put_vol"],
                    "total_call_oi": total_oi_vol["total_call_oi"],
                    "total_put_oi": total_oi_vol["total_put_oi"],
                    "total_call_vol": total_oi_vol["total_call_vol"],
                    "total_put_vol": total_oi_vol["total_put_vol"],
                    "total_call_gex": total_gex_vals["total_call_gex"],
                    "total_put_gex": total_gex_vals["total_put_gex"],
                    "strike_count": len(strikes),
                    "is_premarket": is_premarket,
                    "hmm_label": hmm_label
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
    def get_distribution_snapshots():
        """Get snapshots from gex_strike_window for distribution table with pagination.

        Query params:
            offset: pagination offset (default 0)
            limit: page size (default 200)
            regime: time regime filter (e.g., "0935_1000", "pre")
        """
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 200))
        regime_id = request.args.get("regime", "0935_1000")

        # Get time range for selected regime
        regime = next((r for r in TIME_REGIMES if r["id"] == regime_id), TIME_REGIMES[1])
        time_start = regime["start"]
        time_end = regime["end"]

        try:
            with get_connection() as con:
                # Get total count
                count_result = con.execute("""
                    SELECT COUNT(*) FROM gex_strike_window
                    WHERE symbol='SPX' AND ntime>=? AND ntime<=?
                """, (time_start, time_end)).fetchone()
                total = count_result[0]

                # Get paginated snapshots with raw data
                rows = con.execute("""
                    SELECT ndate, ntime, price, data
                    FROM gex_strike_window
                    WHERE symbol='SPX' AND ntime>=? AND ntime<=?
                    ORDER BY ndate DESC, ntime DESC
                    LIMIT ? OFFSET ?
                """, (time_start, time_end, limit, offset)).fetchall()

            snapshots = []
            for row in rows:
                ndate, ntime, price, data = row
                date_str = f"{ndate//10000}-{(ndate//100)%100:02d}-{ndate%100:02d}"
                time_str = f"{ntime//100:02d}:{ntime%100:02d}"
                
                strikes = json.loads(data) if data else []
                
                if strikes:
                    # Calculate metrics from strike data
                    sentiment = calculate_sentiment(strikes)
                    gex_ratio = calculate_gex_ratio(strikes)
                    net_gex = calculate_net_gex(strikes)
                    kcs = calculate_kcs(strikes, price)
                    dominance = calculate_dominance(strikes, price)
                    total_oi_vol = calculate_total_oi_and_vol(strikes)
                    total_gex_vals = calculate_total_gex(strikes)
                    
                    snapshots.append({
                        "date": date_str,
                        "time": time_str,
                        "ndate": ndate,
                        "ntime": ntime,
                        "uprice": price,
                        "net_gex": net_gex,
                        "total_call_gex": total_gex_vals["total_call_gex"],
                        "total_put_gex": total_gex_vals["total_put_gex"],
                        "kcs": kcs,
                        "dominance": dominance,
                        "sentiment": sentiment,
                        "gex_ratio": gex_ratio,
                        "total_call_oi": total_oi_vol["total_call_oi"],
                        "total_put_oi": total_oi_vol["total_put_oi"],
                        "total_call_vol": total_oi_vol["total_call_vol"],
                        "total_put_vol": total_oi_vol["total_put_vol"],
                    })

            has_more = offset + limit < total

            return BaseController.json_response({
                "snapshots": snapshots,
                "total": total,
                "has_more": has_more,
            })
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    def get_distribution_all_values():
        """Return all historical values for a metric from gex_strike_window.

        Query params:
            metric: metric name (e.g., net_gex, sentiment)
            regime: time regime filter (e.g., "0930_1000", "pre")
        """
        metric = request.args.get("metric", "net_gex")
        regime_id = request.args.get("regime", "0935_1000")

        # Get time range for selected regime
        regime = next((r for r in TIME_REGIMES if r["id"] == regime_id), TIME_REGIMES[1])
        time_start = regime["start"]
        time_end = regime["end"]

        try:
            with get_connection() as con:
                rows = con.execute("""
                    SELECT price, data
                    FROM gex_strike_window
                    WHERE symbol='SPX' AND ntime>=? AND ntime<=?
                """, (time_start, time_end)).fetchall()

            all_values = []
            for row in rows:
                price, data = row
                strikes = json.loads(data) if data else []
                
                if not strikes:
                    continue
                
                # Calculate the requested metric
                if metric == "net_gex":
                    value = calculate_net_gex(strikes)
                elif metric == "total_call_gex":
                    value = calculate_total_gex(strikes)["total_call_gex"]
                elif metric == "total_put_gex":
                    value = calculate_total_gex(strikes)["total_put_gex"]
                elif metric == "kcs":
                    value = calculate_kcs(strikes, price)
                elif metric == "dominance":
                    value = calculate_dominance(strikes, price)
                elif metric == "sentiment":
                    value = calculate_sentiment(strikes)
                elif metric == "gex_ratio":
                    value = calculate_gex_ratio(strikes)
                elif metric == "total_call_oi":
                    value = calculate_total_oi_and_vol(strikes)["total_call_oi"]
                elif metric == "total_put_oi":
                    value = calculate_total_oi_and_vol(strikes)["total_put_oi"]
                elif metric == "total_call_vol":
                    value = calculate_total_oi_and_vol(strikes)["total_call_vol"]
                elif metric == "total_put_vol":
                    value = calculate_total_oi_and_vol(strikes)["total_put_vol"]
                else:
                    continue
                
                if value is not None:
                    all_values.append(value)

            # Scale for display
            if metric in ["gex_ratio", "sentiment", "dominance", "kcs"]:
                scale = 1
            elif "gex" in metric:
                scale = 1e9
            elif "oi" in metric or "vol" in metric:
                scale = 1e3
            else:
                scale = 1

            scaled_values = [round(v / scale, 3) for v in all_values]

            return BaseController.json_response({
                "metric": metric,
                "values": scaled_values,
                "n_samples": len(scaled_values),
            })
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    def get_gex_percentiles():
        """Return percentile ranks for all metrics for a given date/time snapshot.

        Uses pre-computed gex_percentile_history table for fast lookup.
        net_gex:   bearish_pct = 100 - pct_rank  (higher = more bearish than historical)
        call_gex, put_gex, call_oi, put_oi, call_vol, put_vol:
                   size_pct = pct_rank  (higher = larger than more historical readings)
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 1000)
            
        Returns:
            JSON response with percentile ranks for all metrics
        """
        try:
            date_iso = request.args.get("date")
            ntime = int(request.args.get("time", 1000))
            
            if not date_iso:
                return BaseController.json_response(
                    BaseController.error_response("date required"),
                    400
                )
            
            ndate = int(date_iso.replace("-", ""))
            
            # Load snapshot stats from gex_strike_window
            with get_connection() as con:
                row = con.execute(
                    """SELECT ndate, ntime, symbol, source, price, data
                       FROM gex_strike_window
                       WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'""",
                    (ndate, ntime)
                ).fetchone()
            
            if not row:
                return BaseController.json_response(
                    BaseController.error_response("No snapshot found"),
                    404
                )
            
            ndate, ntime, symbol, source, uprice, data_json = row
            
            if not uprice or not data_json:
                return BaseController.json_response(
                    BaseController.error_response("Invalid snapshot data"),
                    400
                )
            
            strikes = json.loads(data_json)
            if not strikes:
                return BaseController.json_response(
                    BaseController.error_response("No strike data"),
                    400
                )
            
            # Calculate metrics using gex_calculations module
            sentiment = calculate_sentiment(strikes)
            gex_ratio = calculate_gex_ratio(strikes)
            net_gex = calculate_net_gex(strikes)
            kcs = calculate_kcs(strikes, uprice)
            dominance = calculate_dominance(strikes, uprice)
            key_stats = calculate_key_strike_stats(strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(strikes)
            total_gex_vals = calculate_total_gex(strikes)
            
            stats = {
                "net_gex": net_gex,
                "total_call_gex": total_gex_vals["total_call_gex"],
                "total_put_gex": total_gex_vals["total_put_gex"],
                "total_call_oi": total_oi_vol["total_call_oi"],
                "total_put_oi": total_oi_vol["total_put_oi"],
                "total_call_vol": total_oi_vol["total_call_vol"],
                "total_put_vol": total_oi_vol["total_put_vol"],
                "kcs": kcs,
                "dominance": dominance,
            }
            
            # Find nearest standard time slot for percentile comparison
            # If requested time is in standard TIMES list, use it
            # Otherwise, find nearest standard time slot
            if ntime in TIMES:
                lookup_ntime = ntime
            else:
                # Find nearest standard time slot
                lookup_ntime = min(TIMES, key=lambda t: abs(t - ntime))
            
            cache_ntime = lookup_ntime
            
            # Get sample size for this time slot
            with get_connection() as con:
                n = con.execute(
                    "SELECT COUNT(DISTINCT ndate) FROM gex_percentile_history WHERE ntime=?",
                    (cache_ntime,)
                ).fetchone()[0]
            
            # Helper function for size-based metrics (defined outside with block)
            def size_entry(con, metric_name):
                try:
                    row = con.execute(
                        "SELECT percentile FROM gex_percentile_history WHERE ndate=? AND ntime=? AND metric_name=?",
                        (ndate, lookup_ntime, metric_name)
                    ).fetchone()
                    pct = row[0] if row else 50
                except Exception:
                    pct = 50
                try:
                    value = stats[metric_name]
                except KeyError:
                    value = 0
                return {"value": value, "pct": pct}
            
            # Get percentiles for all metrics
            with get_connection() as con:
                # Calculate net_gex percentile using the lookup time slot (nearest standard)
                try:
                    row = con.execute(
                        "SELECT percentile FROM gex_percentile_history WHERE ndate=? AND ntime=? AND metric_name='net_gex'",
                        (ndate, lookup_ntime)
                    ).fetchone()
                    net_pct_raw = row[0] if row else 50
                except Exception:
                    net_pct_raw = 50
                bearish_pct = 100 - net_pct_raw
                
                data = {
                    "sample_size": n,
                    "ntime": ntime,
                    "net_gex": {
                        "value": stats["net_gex"],
                        "pct_raw": net_pct_raw,
                        "bearish_pct": bearish_pct,
                    },
                    "total_call_gex": size_entry(con, "total_call_gex"),
                    "total_put_gex": size_entry(con, "total_put_gex"),
                    "total_call_oi": size_entry(con, "total_call_oi"),
                    "total_put_oi": size_entry(con, "total_put_oi"),
                    "total_call_vol": size_entry(con, "total_call_vol"),
                    "total_put_vol": size_entry(con, "total_put_vol"),
                    "kcs": size_entry(con, "kcs"),
                    "dominance": size_entry(con, "dominance"),
                }
            
            return BaseController.json_response(data)
            
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
    
    @staticmethod
    def calculate_on_the_fly_percentile():
        """Calculate percentile for a metric on-the-fly using recent historical data.
        
        Approach:
        1. Map snapshot time to nearest standard time slot (935, 1000, 1030, etc.)
        2. Query last N days of data for that specific time slot
        3. Calculate percentile against those historical values
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format (default 1000)
            metric: metric name (default net_gex)
            days: number of days to look back (default 90)
            
        Returns:
            JSON response with value, percentile, and sample size
        """
        from datetime import datetime, timedelta
        
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 1000))
        metric = request.args.get("metric", "net_gex")
        days = int(request.args.get("days", 90))
        debug = request.args.get("debug", "false").lower() == "true"
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("date required"),
                400
            )
        
        ndate = int(date_iso.replace("-", ""))
        
        # Map to nearest standard time slot
        if ntime in TIMES:
            lookup_ntime = ntime
        else:
            lookup_ntime = min(TIMES, key=lambda t: abs(t - ntime))
        
        try:
            # Get the current snapshot's metric value
            with get_connection() as con:
                row = con.execute(
                    """SELECT price, data FROM gex_strike_window
                       WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'""",
                    (ndate, ntime)
                ).fetchone()
            
            if not row:
                return BaseController.json_response(
                    BaseController.error_response("No snapshot found"),
                    404
                )
            
            price, data = row
            strikes = json.loads(data) if data else []
            
            if not strikes:
                return BaseController.json_response(
                    BaseController.error_response("No strike data"),
                    400
                )
            
            # Calculate the metric value for current snapshot
            if metric == "net_gex":
                current_value = calculate_net_gex(strikes)
            elif metric == "total_call_gex":
                current_value = calculate_total_gex(strikes)["total_call_gex"]
            elif metric == "total_put_gex":
                current_value = calculate_total_gex(strikes)["total_put_gex"]
            elif metric == "kcs":
                current_value = calculate_kcs(strikes, price)
            elif metric == "dominance":
                current_value = calculate_dominance(strikes, price)
            elif metric == "sentiment":
                current_value = calculate_sentiment(strikes)
            elif metric == "gex_ratio":
                current_value = calculate_gex_ratio(strikes)
            elif metric == "total_call_oi":
                current_value = calculate_total_oi_and_vol(strikes)["total_call_oi"]
            elif metric == "total_put_oi":
                current_value = calculate_total_oi_and_vol(strikes)["total_put_oi"]
            elif metric == "total_call_vol":
                current_value = calculate_total_oi_and_vol(strikes)["total_call_vol"]
            elif metric == "total_put_vol":
                current_value = calculate_total_oi_and_vol(strikes)["total_put_vol"]
            else:
                return BaseController.json_response(
                    BaseController.error_response(f"Unknown metric: {metric}"),
                    400
                )
            
            # Get historical values for the same time slot over last N days
            cutoff_date = datetime.strptime(date_iso, "%Y-%m-%d") - timedelta(days=days)
            cutoff_ndate = int(cutoff_date.strftime("%Y%m%d"))
            
            with get_connection() as con:
                rows = con.execute(
                    """SELECT ndate, price, data FROM gex_strike_window
                       WHERE ndate>=? AND ndate<? AND ntime=? AND symbol='SPX' AND source='gex'
                       ORDER BY ndate DESC""",
                    (cutoff_ndate, ndate, lookup_ntime)
                ).fetchall()
            
            historical_values = []
            historical_debug = []
            for row in rows:
                hist_ndate, hist_price, hist_data = row
                hist_strikes = json.loads(hist_data) if hist_data else []
                
                if not hist_strikes:
                    continue
                
                # Calculate the same metric for historical snapshot
                if metric == "net_gex":
                    hist_value = calculate_net_gex(hist_strikes)
                elif metric == "total_call_gex":
                    hist_value = calculate_total_gex(hist_strikes)["total_call_gex"]
                elif metric == "total_put_gex":
                    hist_value = calculate_total_gex(hist_strikes)["total_put_gex"]
                elif metric == "kcs":
                    hist_value = calculate_kcs(hist_strikes, hist_price)
                elif metric == "dominance":
                    hist_value = calculate_dominance(hist_strikes, hist_price)
                elif metric == "sentiment":
                    hist_value = calculate_sentiment(hist_strikes)
                elif metric == "gex_ratio":
                    hist_value = calculate_gex_ratio(hist_strikes)
                elif metric == "total_call_oi":
                    hist_value = calculate_total_oi_and_vol(hist_strikes)["total_call_oi"]
                elif metric == "total_put_oi":
                    hist_value = calculate_total_oi_and_vol(hist_strikes)["total_put_oi"]
                elif metric == "total_call_vol":
                    hist_value = calculate_total_oi_and_vol(hist_strikes)["total_call_vol"]
                elif metric == "total_put_vol":
                    hist_value = calculate_total_oi_and_vol(hist_strikes)["total_put_vol"]
                
                if hist_value is not None:
                    historical_values.append(hist_value)
                    if debug:
                        d = str(hist_ndate)
                        historical_debug.append({
                            "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                            "ntime": lookup_ntime,
                            "value": hist_value
                        })
            
            if not historical_values:
                return BaseController.json_response({
                    "value": current_value,
                    "percentile": 50,
                    "sample_size": 0,
                    "message": "No historical data available"
                })
            
            # Calculate percentile
            sorted_values = sorted(historical_values)
            rank = sum(1 for v in sorted_values if v <= current_value)
            percentile = round(rank / len(sorted_values) * 100, 1)
            
            result = {
                "value": current_value,
                "percentile": percentile,
                "sample_size": len(historical_values),
                "lookup_time": lookup_ntime,
                "days": days
            }
            if debug:
                result["history"] = sorted(historical_debug, key=lambda x: x["value"])
            return BaseController.json_response(result)
            
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e)),
                500
            )
