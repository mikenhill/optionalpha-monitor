"""Snapshot DAO for GEX snapshot data.

Handles both live (OptionAlpha market.gex) and historical (market.histgex) data formats.
Contains data transformation rules for computing summary fields from raw JSON.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from dao.base_dao import BaseDAO
from dao.database import get_connection


class SnapshotDAO(BaseDAO):
    """DAO for snapshot table operations.
    
    Handles:
    - Live data format (market.gex API): symbol, last, low, high, data[]
    - Historical data format (market.histgex API): symbol, ndate, ntime, uprice, data[]
    - Data transformation: computes summary fields from raw JSON
    """
    
    def __init__(
        self,
        ndate: Optional[int] = None,
        ntime: Optional[int] = None,
        symbol: Optional[str] = None,
        uprice: Optional[float] = None,
        raw_json: Optional[str] = None,
        capture_ts: Optional[str] = None,
        source: Optional[str] = None,
        sentiment: Optional[float] = None,
        gex_ratio: Optional[float] = None,
        net_gex: Optional[float] = None,
        kcs: Optional[float] = None,
        dominance: Optional[float] = None,
        total_call_gex: Optional[float] = None,
        total_put_gex: Optional[float] = None,
        key_strike: Optional[float] = None,
        key_call_gex: Optional[float] = None,
        key_put_gex: Optional[float] = None,
        total_call_oi: Optional[int] = None,
        total_put_oi: Optional[int] = None,
        key_call_oi: Optional[int] = None,
        key_put_oi: Optional[int] = None,
        total_call_vol: Optional[int] = None,
        total_put_vol: Optional[int] = None,
        key_call_vol: Optional[int] = None,
        key_put_vol: Optional[int] = None,
        key2_strike: Optional[float] = None,
        key2_abs: Optional[float] = None,
        key2_call_vol: Optional[int] = None,
        key2_put_vol: Optional[int] = None,
        flip: Optional[float] = None,
        is_premarket: Optional[bool] = None,
        hmm_state: Optional[int] = None,
        hmm_label: Optional[str] = None
    ):
        self.ndate = ndate
        self.ntime = ntime
        self.symbol = symbol
        self.uprice = uprice
        self.raw_json = raw_json
        self.capture_ts = capture_ts
        self.source = source
        self.sentiment = sentiment
        self.gex_ratio = gex_ratio
        self.net_gex = net_gex
        self.kcs = kcs
        self.dominance = dominance
        self.total_call_gex = total_call_gex
        self.total_put_gex = total_put_gex
        self.key_strike = key_strike
        self.key_call_gex = key_call_gex
        self.key_put_gex = key_put_gex
        self.total_call_oi = total_call_oi
        self.total_put_oi = total_put_oi
        self.key_call_oi = key_call_oi
        self.key_put_oi = key_put_oi
        self.total_call_vol = total_call_vol
        self.total_put_vol = total_put_vol
        self.key_call_vol = key_call_vol
        self.key_put_vol = key_put_vol
        self.key2_strike = key2_strike
        self.key2_abs = key2_abs
        self.key2_call_vol = key2_call_vol
        self.key2_put_vol = key2_put_vol
        self.flip = flip
        self.is_premarket = is_premarket
        self.hmm_state = hmm_state
        self.hmm_label = hmm_label
    
    @classmethod
    def fromJson(cls, json_data: Dict[str, Any]) -> 'SnapshotDAO':
        """Deserialize OptionAlpha API response to SnapshotDAO.
        
        Handles two formats:
        1. Live data (market.gex): {"t": "res", "api": "market.gex", "data": {...}}
        2. Historical data (market.histgex): {"t": "res", "api": "market.histgex", "data": {...}}
        
        Args:
            json_data: OptionAlpha API response
            
        Returns:
            SnapshotDAO instance
            
        Raises:
            ValueError: If json_data is invalid
            KeyError: If required fields are missing
        """
        if not isinstance(json_data, dict):
            raise ValueError("json_data must be a dictionary")
        
        # Extract the data wrapper
        if 'data' in json_data and isinstance(json_data['data'], dict):
            data = json_data['data']
        else:
            data = json_data
        
        # Determine data source
        api_type = json_data.get('api', '')
        is_live = api_type == 'market.gex'
        is_hist = api_type == 'market.histgex'
        
        # Extract common fields
        symbol = data.get('symbol', 'SPX')
        
        # Live data: derive ndate/ntime from capture time
        if is_live:
            uprice = data.get('last')
            capture_ts = datetime.utcnow().isoformat()
            ndate = int(datetime.utcnow().strftime('%Y%m%d'))
            ntime = int(datetime.utcnow().strftime('%H%M'))
            source = 'gex'
        # Historical data: use explicit ndate/ntime
        elif is_hist:
            ndate = data.get('ndate')
            ntime = data.get('ntime')
            uprice = data.get('uprice')
            capture_ts = datetime.utcnow().isoformat()
            source = 'histgex'
        else:
            # Direct JSON (e.g., from database)
            ndate = data.get('ndate')
            ntime = data.get('ntime')
            uprice = data.get('uprice')
            capture_ts = data.get('capture_ts')
            source = data.get('source')
        
        # Store raw JSON (the full OptionAlpha response)
        raw_json = json.dumps(data)
        
        # Compute summary fields from raw data
        summary = cls._compute_flat_summary(data)
        
        # Create instance
        return cls(
            ndate=ndate,
            ntime=ntime,
            symbol=symbol,
            uprice=uprice,
            raw_json=raw_json,
            capture_ts=capture_ts,
            source=source,
            sentiment=summary.get('sentiment_pct'),
            gex_ratio=summary.get('gex_ratio'),
            net_gex=summary.get('net_gex'),
            kcs=summary.get('kcs'),
            dominance=summary.get('dominance'),
            total_call_gex=summary.get('total_call_gex'),
            total_put_gex=summary.get('total_put_gex'),
            key_strike=summary.get('key_strike'),
            key_call_gex=summary.get('key_call_gex'),
            key_put_gex=summary.get('key_put_gex'),
            total_call_oi=summary.get('total_call_oi'),
            total_put_oi=summary.get('total_put_oi'),
            key_call_oi=summary.get('key_call_oi'),
            key_put_oi=summary.get('key_put_oi'),
            total_call_vol=summary.get('total_call_vol'),
            total_put_vol=summary.get('total_put_vol'),
            key_call_vol=summary.get('key_call_vol'),
            key_put_vol=summary.get('key_put_vol'),
            key2_strike=summary.get('key2_strike'),
            key2_abs=summary.get('key2_abs'),
            key2_call_vol=summary.get('key2_call_vol'),
            key2_put_vol=summary.get('key2_put_vol'),
            flip=summary.get('flip'),
            is_premarket=cls._is_premarket(ntime) if ntime else None
        )
    
    def toJson(self) -> Dict[str, Any]:
        """Serialize SnapshotDAO to JSON-compatible dictionary.
        
        Returns:
            Dictionary representation of snapshot
        """
        return {
            'ndate': self.ndate,
            'ntime': self.ntime,
            'symbol': self.symbol,
            'uprice': self.uprice,
            'raw_json': self.raw_json,
            'capture_ts': self.capture_ts,
            'source': self.source,
            'sentiment': self.sentiment,
            'gex_ratio': self.gex_ratio,
            'net_gex': self.net_gex,
            'kcs': self.kcs,
            'dominance': self.dominance,
            'total_call_gex': self.total_call_gex,
            'total_put_gex': self.total_put_gex,
            'key_strike': self.key_strike,
            'key_call_gex': self.key_call_gex,
            'key_put_gex': self.key_put_gex,
            'total_call_oi': self.total_call_oi,
            'total_put_oi': self.total_put_oi,
            'key_call_oi': self.key_call_oi,
            'key_put_oi': self.key_put_oi,
            'total_call_vol': self.total_call_vol,
            'total_put_vol': self.total_put_vol,
            'key_call_vol': self.key_call_vol,
            'key_put_vol': self.key_put_vol,
            'key2_strike': self.key2_strike,
            'key2_abs': self.key2_abs,
            'key2_call_vol': self.key2_call_vol,
            'key2_put_vol': self.key2_put_vol,
            'flip': self.flip,
            'is_premarket': self.is_premarket,
            'hmm_state': self.hmm_state,
            'hmm_label': self.hmm_label
        }
    
    @classmethod
    def find_by_id(cls, rowid: int) -> Optional['SnapshotDAO']:
        """Find snapshot by rowid.
        
        Args:
            rowid: Database row ID
            
        Returns:
            SnapshotDAO instance if found, None otherwise
        """
        with get_connection() as con:
            cursor = con.execute(
                'SELECT * FROM snapshot WHERE rowid = ?',
                (rowid,)
            )
            row = cursor.fetchone()
            if row:
                return cls._from_db_row(row)
        return None
    
    @classmethod
    def find_by_date_time(cls, ndate: int, ntime: int, symbol: str = 'SPX') -> Optional['SnapshotDAO']:
        """Find snapshot by date and time.
        
        Args:
            ndate: Date in YYYYMMDD format
            ntime: Time in HHMM format
            symbol: Symbol (default: SPX)
            
        Returns:
            SnapshotDAO instance if found, None otherwise
        """
        with get_connection() as con:
            cursor = con.execute(
                'SELECT * FROM snapshot WHERE ndate = ? AND ntime = ? AND symbol = ?',
                (ndate, ntime, symbol)
            )
            row = cursor.fetchone()
            if row:
                return cls._from_db_row(row)
        return None
    
    @classmethod
    def find_by_date(cls, ndate: int, symbol: str = 'SPX') -> list:
        """Find all snapshots for a given date.
        
        Args:
            ndate: Date in YYYYMMDD format
            symbol: Symbol (default: SPX)
            
        Returns:
            List of SnapshotDAO instances
        """
        with get_connection() as con:
            cursor = con.execute(
                'SELECT * FROM snapshot WHERE ndate = ? AND symbol = ? ORDER BY ntime',
                (ndate, symbol)
            )
            return [cls._from_db_row(row) for row in cursor.fetchall()]
    
    def save(self) -> 'SnapshotDAO':
        """Insert or update snapshot in database.
        
        Uses INSERT OR REPLACE to handle both insert and update based on
        the composite primary key (ndate, ntime, symbol).
        
        Returns:
            The saved SnapshotDAO instance
        """
        with get_connection() as con:
            cursor = con.execute('''
                INSERT OR REPLACE INTO snapshot (
                    ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                    sentiment, gex_ratio, net_gex, kcs, dominance,
                    total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                    total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                    total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                    key2_strike, key2_abs, key2_call_vol, key2_put_vol,
                    flip, is_premarket, hmm_state, hmm_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.ndate, self.ntime, self.symbol, self.uprice, self.raw_json,
                self.capture_ts, self.source, self.sentiment, self.gex_ratio,
                self.net_gex, self.kcs, self.dominance, self.total_call_gex,
                self.total_put_gex, self.key_strike, self.key_call_gex, self.key_put_gex,
                self.total_call_oi, self.total_put_oi, self.key_call_oi, self.key_put_oi,
                self.total_call_vol, self.total_put_vol, self.key_call_vol, self.key_put_vol,
                self.key2_strike, self.key2_abs, self.key2_call_vol, self.key2_put_vol,
                self.flip, self.is_premarket, self.hmm_state, self.hmm_label
            ))
            con.commit()
        return self
    
    def delete(self) -> bool:
        """Delete snapshot from database.
        
        Uses composite primary key (ndate, ntime, symbol) to identify the record.
        
        Returns:
            True if deleted, False otherwise
        """
        if not self.ndate or not self.ntime or not self.symbol:
            return False
        
        with get_connection() as con:
            cursor = con.execute(
                'DELETE FROM snapshot WHERE ndate = ? AND ntime = ? AND symbol = ?',
                (self.ndate, self.ntime, self.symbol)
            )
            con.commit()
            return cursor.rowcount > 0
    
    @classmethod
    def _from_db_row(cls, row) -> 'SnapshotDAO':
        """Create SnapshotDAO from database row.
        
        Args:
            row: sqlite3.Row object
            
        Returns:
            SnapshotDAO instance
        """
        return cls(
            ndate=row['ndate'],
            ntime=row['ntime'],
            symbol=row['symbol'],
            uprice=row['uprice'],
            raw_json=row['raw_json'],
            capture_ts=row['capture_ts'],
            source=row['source'],
            sentiment=row['sentiment'],
            gex_ratio=row['gex_ratio'],
            net_gex=row['net_gex'],
            kcs=row['kcs'],
            dominance=row['dominance'],
            total_call_gex=row['total_call_gex'],
            total_put_gex=row['total_put_gex'],
            key_strike=row['key_strike'],
            key_call_gex=row['key_call_gex'],
            key_put_gex=row['key_put_gex'],
            total_call_oi=row['total_call_oi'],
            total_put_oi=row['total_put_oi'],
            key_call_oi=row['key_call_oi'],
            key_put_oi=row['key_put_oi'],
            total_call_vol=row['total_call_vol'],
            total_put_vol=row['total_put_vol'],
            key_call_vol=row['key_call_vol'],
            key_put_vol=row['key_put_vol'],
            key2_strike=row['key2_strike'],
            key2_abs=row['key2_abs'],
            key2_call_vol=row['key2_call_vol'],
            key2_put_vol=row['key2_put_vol'],
            flip=row['flip'],
            is_premarket=row['is_premarket'],
            hmm_state=row['hmm_state'],
            hmm_label=row['hmm_label']
        )
    
    @staticmethod
    def _compute_flat_summary(data: dict) -> dict:
        """Compute all flat summary fields for a GEX snapshot (40-strike window).
        
        This matches the calculation used in gex_viewer.py for consistency.
        """
        # Handle both dict with 'data' key and direct list
        if isinstance(data, dict):
            rows = data.get("data") or []
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        
        uprice = data.get("uprice", 0) if isinstance(data, dict) else 0
        if not rows:
            return {"uprice": uprice}
        
        valid = [r for r in rows if r.get("strike") is not None]
        below = [r for r in valid if r["strike"] < uprice]
        above = [r for r in valid if r["strike"] >= uprice]
        window_rows = below[-20:] + above[:20]
        if not window_rows:
            return {"uprice": uprice}
        
        net_gex = [r.get("net", 0) or 0 for r in window_rows]
        call_gex = [r.get("cg", 0) or 0 for r in window_rows]
        put_gex = [r.get("pg", 0) or 0 for r in window_rows]
        
        total_call_oi = int(sum(r.get("coi", 0) or 0 for r in window_rows))
        total_put_oi = int(sum(r.get("poi", 0) or 0 for r in window_rows))
        total_call_vol = int(sum(r.get("cvol", 0) or 0 for r in window_rows))
        total_put_vol = int(sum(r.get("pvol", 0) or 0 for r in window_rows))
        
        pos_bars = sum(1 for n in net_gex if n > 0)
        sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50
        
        # Ratio flips sign based on which side is larger
        total_call_gex_sum = sum(call_gex)
        total_put_gex_sum = abs(sum(put_gex))
        if total_call_gex_sum > total_put_gex_sum:
            gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
        else:
            gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0
        
        net_g = sum(net_gex)
        
        key_stats = SnapshotDAO._compute_key_strike_stats(window_rows, uprice)
        
        # Flip level: cumulative net crosses zero within the 40-strike window
        by_strike = sorted(window_rows, key=lambda r: r["strike"])
        cumulative = 0.0
        flip = None
        prev_strike, prev_cum = None, 0.0
        for r in by_strike:
            cumulative += r.get("net", 0) or 0
            if prev_strike is not None and prev_cum * cumulative < 0:
                denom = abs(cumulative) + abs(prev_cum)
                flip = round(prev_strike + (r["strike"] - prev_strike) * abs(prev_cum) / denom, 1) if denom else r["strike"]
                break
            prev_strike, prev_cum = r["strike"], cumulative
        
        return {
            "uprice": uprice,
            "net_gex": net_g,
            "total_call_gex": total_call_gex_sum,
            "total_put_gex": sum(put_gex),
            "sentiment_pct": sentiment_pct,
            "gex_ratio": gex_ratio,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_call_vol": total_call_vol,
            "total_put_vol": total_put_vol,
            "flip": flip,
            **key_stats,
        }
    
    @staticmethod
    def _compute_key_strike_stats(window_rows: list, uprice: float) -> dict:
        """Compute key strike statistics.
        
        Finds the strike with maximum absolute gamma exposure.
        """
        if not window_rows:
            return {
                "key_strike": None,
                "key_call_gex": 0,
                "key_put_gex": 0,
                "key_call_oi": 0,
                "key_put_oi": 0,
                "key_call_vol": 0,
                "key_put_vol": 0,
                "kcs": 0,
                "dominance": 0,
                "key2_strike": None,
                "key2_abs": 0,
                "key2_call_vol": 0,
                "key2_put_vol": 0,
            }
        
        # Find key strike (max absolute gamma)
        key_row = max(window_rows, key=lambda r: r.get("abs", 0) or 0)
        
        # Find secondary key (second max absolute gamma)
        sorted_by_abs = sorted(window_rows, key=lambda r: r.get("abs", 0) or 0, reverse=True)
        key2_row = sorted_by_abs[1] if len(sorted_by_abs) > 1 else None
        
        # Compute KCS (key strike concentration)
        total_abs = sum(r.get("abs", 0) or 0 for r in window_rows)
        key_abs = key_row.get("abs", 0) or 0
        kcs = round(key_abs / total_abs * 100, 1) if total_abs else 0
        
        # Compute dominance (key strike volume vs total)
        key_vol = (key_row.get("cvol", 0) or 0) + (key_row.get("pvol", 0) or 0)
        total_vol = sum((r.get("cvol", 0) or 0) + (r.get("pvol", 0) or 0) for r in window_rows)
        dominance = round(key_vol / total_vol * 100, 1) if total_vol else 0
        
        return {
            "key_strike": key_row.get("strike"),
            "key_call_gex": key_row.get("cg", 0) or 0,
            "key_put_gex": key_row.get("pg", 0) or 0,
            "key_call_oi": key_row.get("coi", 0) or 0,
            "key_put_oi": key_row.get("poi", 0) or 0,
            "key_call_vol": key_row.get("cvol", 0) or 0,
            "key_put_vol": key_row.get("pvol", 0) or 0,
            "kcs": kcs,
            "dominance": dominance,
            "key2_strike": key2_row.get("strike") if key2_row else None,
            "key2_abs": key2_row.get("abs", 0) or 0 if key2_row else 0,
            "key2_call_vol": key2_row.get("cvol", 0) or 0 if key2_row else 0,
            "key2_put_vol": key2_row.get("pvol", 0) or 0 if key2_row else 0,
        }
    
    @staticmethod
    def _is_premarket(ntime: int) -> bool:
        """Determine if snapshot is pre-market (before 9:30 ET).
        
        Args:
            ntime: Time in HHMM format
            
        Returns:
            True if pre-market, False otherwise
        """
        return ntime < 930
