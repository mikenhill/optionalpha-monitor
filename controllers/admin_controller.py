"""Controller for admin API endpoints."""

import json
from datetime import datetime
from flask import request
from controllers.base_controller import BaseController
from dao.database import get_connection
from middleware.test_mode import with_test_metadata


class AdminController(BaseController):
    """Controller for admin-related API endpoints."""
    
    @staticmethod
    @with_test_metadata(dao_name="AdminController")
    def get_invalid_snapshots():
        """Find snapshots with invalid/null key fields.
        
        Returns date/time of snapshots where key fields are null or zero,
        indicating the flat columns weren't properly calculated from the raw JSON.
        
        Query params:
            limit: maximum number of invalid snapshots to return (default 100)
            
        Returns:
            JSON response with list of invalid snapshot identifiers
        """
        limit = int(request.args.get("limit", 100))
        
        try:
            with get_connection() as con:
                # Find snapshots where key fields are null or zero, or raw_json is null
                cursor = con.execute("""
                    SELECT ndate, ntime, symbol, uprice, raw_json,
                           key_strike, key_call_gex, key_put_gex,
                           key_call_oi, key_put_oi, key_call_vol, key_put_vol
                    FROM snapshot
                    WHERE symbol='SPX'
                      AND (raw_json IS NULL OR raw_json = ''
                           OR key_strike IS NULL OR key_strike = 0
                           OR key_call_gex IS NULL OR key_call_gex = 0
                           OR key_put_gex IS NULL OR key_put_gex = 0
                           OR key_call_oi IS NULL OR key_call_oi = 0
                           OR key_put_oi IS NULL OR key_put_oi = 0
                           OR key_call_vol IS NULL OR key_call_vol = 0
                           OR key_put_vol IS NULL OR key_put_vol = 0)
                    ORDER BY ndate DESC, ntime DESC
                    LIMIT ?
                """, (limit,))
                
                invalid_snapshots = []
                for row in cursor.fetchall():
                    ndate, ntime, symbol, uprice, raw_json, key_strike, key_call_gex, key_put_gex, \
                    key_call_oi, key_put_oi, key_call_vol, key_put_vol = row
                    
                    ndate_str = str(ndate)
                    date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
                    time_str = f"{ntime // 100:02d}:{ntime % 100:02d}"
                    
                    # Determine why this snapshot is invalid
                    invalid_reasons = []
                    if not raw_json or raw_json == '':
                        invalid_reasons.append("raw_json_missing")
                    if key_strike is None or key_strike == 0:
                        invalid_reasons.append("key_strike_invalid")
                    if key_call_gex is None or key_call_gex == 0:
                        invalid_reasons.append("key_call_gex_invalid")
                    if key_put_gex is None or key_put_gex == 0:
                        invalid_reasons.append("key_put_gex_invalid")
                    if key_call_oi is None or key_call_oi == 0:
                        invalid_reasons.append("key_call_oi_invalid")
                    if key_put_oi is None or key_put_oi == 0:
                        invalid_reasons.append("key_put_oi_invalid")
                    if key_call_vol is None or key_call_vol == 0:
                        invalid_reasons.append("key_call_vol_invalid")
                    if key_put_vol is None or key_put_vol == 0:
                        invalid_reasons.append("key_put_vol_invalid")
                    
                    invalid_snapshots.append({
                        "ndate": ndate,
                        "ntime": ntime,
                        "date": date_str,
                        "time": time_str,
                        "symbol": symbol,
                        "uprice": uprice,
                        "raw_json_present": bool(raw_json and raw_json != ''),
                        "key_strike": key_strike,
                        "key_call_gex": key_call_gex,
                        "key_put_gex": key_put_gex,
                        "key_call_oi": key_call_oi,
                        "key_put_oi": key_put_oi,
                        "key_call_vol": key_call_vol,
                        "key_put_vol": key_put_vol,
                        "invalid_reasons": invalid_reasons
                    })
            
            response = BaseController.success_response(data={
                "invalid_snapshots": invalid_snapshots,
                "count": len(invalid_snapshots)
            })
            
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'AdminController',
                    'query_time_ms': 0,
                    'row_count': len(invalid_snapshots)
                }
            
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    @with_test_metadata(dao_name="AdminController")
    def get_json_from_snapshot():
        """Get the raw JSON data blob for a specific snapshot.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format
            
        Returns:
            JSON response with the raw data blob and parsed JSON
        """
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 930))
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("Missing required parameter: date"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            with get_connection() as con:
                cursor = con.execute(
                    "SELECT ndate, ntime, symbol, raw_json FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'",
                    (ndate, ntime)
                )
                row = cursor.fetchone()
                
                if not row:
                    return BaseController.json_response(
                        BaseController.error_response("Snapshot not found"),
                        404
                    )
                
                ndate, ntime, symbol, data_blob = row
                
                # Parse the JSON data blob
                try:
                    parsed_data = json.loads(data_blob) if data_blob else None
                except json.JSONDecodeError:
                    parsed_data = None
                
                ndate_str = str(ndate)
                date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
                time_str = f"{ntime // 100:02d}:{ntime % 100:02d}"
                
                response = BaseController.success_response(data={
                    "ndate": ndate,
                    "ntime": ntime,
                    "date": date_str,
                    "time": time_str,
                    "symbol": symbol,
                    "parsed_data": parsed_data
                })
                
                if request.args.get('test_mode') == '1':
                    response['test_metadata'] = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'test_mode': True,
                        'dao_used': 'AdminController',
                        'query_time_ms': 0,
                        'row_count': 1
                    }
                
                return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
    
    @staticmethod
    @with_test_metadata(dao_name="AdminController")
    def rebuild_snapshot_from_json():
        """Rebuild snapshot flat columns from raw JSON data blob.
        
        This endpoint recalculates all the flat columns (key_strike, key_call_gex, etc.)
        from the raw JSON data blob stored in the 'data' column.
        
        Query params:
            date: ISO date string (YYYY-MM-DD)
            time: time in HHMM format
            
        Returns:
            JSON response with the rebuilt snapshot data
        """
        date_iso = request.args.get("date")
        ntime = int(request.args.get("time", 930))
        
        if not date_iso:
            return BaseController.json_response(
                BaseController.error_response("Missing required parameter: date"),
                400
            )
        
        try:
            ndate = int(date_iso.replace("-", ""))
            
            with get_connection() as con:
                # Get the raw data blob
                cursor = con.execute(
                    "SELECT ndate, ntime, symbol, raw_json FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'",
                    (ndate, ntime)
                )
                row = cursor.fetchone()
                
                if not row:
                    return BaseController.json_response(
                        BaseController.error_response("Snapshot not found"),
                        404
                    )
                
                ndate, ntime, symbol, data_blob = row
                
                if not data_blob:
                    return BaseController.json_response(
                        BaseController.error_response("No data blob found for this snapshot"),
                        400
                    )
                
                # Parse the JSON data blob
                try:
                    parsed_data = json.loads(data_blob)
                except json.JSONDecodeError as e:
                    return BaseController.json_response(
                        BaseController.error_response(f"Invalid JSON in data blob: {str(e)}"),
                        400
                    )
                
                # Extract the data rows from the parsed structure
                # The structure is typically: {"data": [...], "uprice": ..., ...}
                rows_data = parsed_data.get("data", [])
                uprice = parsed_data.get("uprice", 0)
                
                if not rows_data:
                    return BaseController.json_response(
                        BaseController.error_response("No data rows found in JSON blob"),
                        400
                    )
                
                # Calculate key strike and metrics from the raw data
                # This replicates the logic from the original snapshot processing
                all_rows = sorted(
                    [r for r in rows_data if r.get("strike") is not None],
                    key=lambda r: r["strike"]
                )
                below = [r for r in all_rows if r["strike"] < uprice]
                above = [r for r in all_rows if r["strike"] >= uprice]
                window_rows = below[-20:] + above[:20]
                
                # Calculate totals
                call_gex = [r.get("cg", 0) or 0 for r in window_rows]
                put_gex = [r.get("pg", 0) or 0 for r in window_rows]
                net_gex = [r.get("net", 0) or 0 for r in window_rows]
                
                total_call_gex = sum(call_gex)
                total_put_gex = sum(put_gex)
                net_gex_total = sum(net_gex)
                
                # Find key strike (closest to underlying)
                key_strike = min(all_rows, key=lambda r: abs(r["strike"] - uprice)) if all_rows else None
                key_strike_value = key_strike["strike"] if key_strike else None
                
                # Get key strike metrics
                key_call_gex = key_strike.get("cg", 0) if key_strike else None
                key_put_gex = key_strike.get("pg", 0) if key_strike else None
                key_call_oi = key_strike.get("call_oi", 0) if key_strike else None
                key_put_oi = key_strike.get("put_oi", 0) if key_strike else None
                key_call_vol = key_strike.get("call_vol", 0) if key_strike else None
                key_put_vol = key_strike.get("put_vol", 0) if key_strike else None
                
                # Update the snapshot with recalculated values
                con.execute("""
                    UPDATE snapshot
                    SET uprice = ?,
                        key_strike = ?,
                        key_call_gex = ?,
                        key_put_gex = ?,
                        key_call_oi = ?,
                        key_put_oi = ?,
                        key_call_vol = ?,
                        key_put_vol = ?,
                        total_call_gex = ?,
                        total_put_gex = ?,
                        net_gex = ?
                    WHERE ndate = ? AND ntime = ? AND symbol = 'SPX'
                """, (
                    uprice,
                    key_strike_value,
                    key_call_gex,
                    key_put_gex,
                    key_call_oi,
                    key_put_oi,
                    key_call_vol,
                    key_put_vol,
                    total_call_gex,
                    total_put_gex,
                    net_gex_total,
                    ndate,
                    ntime
                ))
                
                con.commit()
            
            ndate_str = str(ndate)
            date_str = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
            time_str = f"{ntime // 100:02d}:{ntime % 100:02d}"
            
            response = BaseController.success_response(data={
                "ndate": ndate,
                "ntime": ntime,
                "date": date_str,
                "time": time_str,
                "symbol": symbol,
                "rebuilt_values": {
                    "uprice": uprice,
                    "key_strike": key_strike_value,
                    "key_call_gex": key_call_gex,
                    "key_put_gex": key_put_gex,
                    "key_call_oi": key_call_oi,
                    "key_put_oi": key_put_oi,
                    "key_call_vol": key_call_vol,
                    "key_put_vol": key_put_vol,
                    "total_call_gex": total_call_gex,
                    "total_put_gex": total_put_gex,
                    "net_gex": net_gex_total
                },
                "message": "Snapshot rebuilt successfully from JSON data blob"
            })
            
            if request.args.get('test_mode') == '1':
                response['test_metadata'] = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'test_mode': True,
                    'dao_used': 'AdminController',
                    'query_time_ms': 0,
                    'row_count': 1
                }
            
            return BaseController.json_response(response)
        except Exception as e:
            return BaseController.json_response(
                BaseController.error_response(str(e))
            )
