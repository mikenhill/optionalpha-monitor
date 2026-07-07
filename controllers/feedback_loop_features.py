"""
Trade Signal Feedback Loop Feature Calculation

This module implements the core feature calculation functions for the trade signal feedback loop.
These functions calculate performance-based features that influence ML model training.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json


def calculate_trade_signal_features(ndate: int, ntime: int, symbol: str = 'SPX') -> Dict:
    """
    Calculate trade signal performance features for a specific snapshot.
    
    Args:
        ndate: Date in YYYYMMDD format
        ntime: Time in HHMM format
        symbol: Ticker symbol (default 'SPX')
    
    Returns:
        Dictionary containing calculated features
    """
    features = {}
    
    # Calculate success rates for ALL signal types
    features.update(calculate_all_signal_success_rates(ndate, ntime))
    
    # Calculate wall strength score
    features['wall_strength_score'] = calculate_wall_strength_score(ndate, ntime)
    
    # Calculate signal reliability score
    features['signal_reliability_score'] = calculate_signal_reliability_score(ndate, ntime)
    
    # Calculate recent signal performance
    features.update(calculate_recent_signal_performance(ndate, ntime))
    
    # Detect market regime features
    features.update(detect_market_regime_features(ndate, ntime))
    
    return features


def calculate_all_signal_success_rates(ndate: int, ntime: int) -> Dict:
    """
    Calculate historical success rates for ALL signal types.
    
    Returns:
        Dict with success rate features for all signal types
    """
    with sqlite3.connect('gex.db') as con:
        # CALL_WALL success rates
        call_success_7d = calculate_success_rate(
            con, ndate, ntime, 'CALL_WALL', days=7
        )
        call_success_30d = calculate_success_rate(
            con, ndate, ntime, 'CALL_WALL', days=30
        )
        
        # PUT_WALL success rates
        put_success_7d = calculate_success_rate(
            con, ndate, ntime, 'PUT_WALL', days=7
        )
        put_success_30d = calculate_success_rate(
            con, ndate, ntime, 'PUT_WALL', days=30
        )
        
        # PIN (Iron Butterfly) success rates
        butterfly_success_7d = calculate_success_rate(
            con, ndate, ntime, 'PIN', days=7
        )
        butterfly_success_30d = calculate_success_rate(
            con, ndate, ntime, 'PIN', days=30
        )
        
        # POS_GAMMA (Iron Condor) success rates
        condor_success_7d = calculate_success_rate(
            con, ndate, ntime, 'POS_GAMMA', days=7
        )
        condor_success_30d = calculate_success_rate(
            con, ndate, ntime, 'POS_GAMMA', days=30
        )
        
        # PUT_PILLAR success rates
        pillar_success_7d = calculate_success_rate(
            con, ndate, ntime, 'PUT_PILLAR', days=7
        )
        pillar_success_30d = calculate_success_rate(
            con, ndate, ntime, 'PUT_PILLAR', days=30
        )
        
        # No Trade decision accuracy
        notrade_success_7d = calculate_success_rate(
            con, ndate, ntime, 'NEG_GAMMA', days=7
        )
        notrade_success_30d = calculate_success_rate(
            con, ndate, ntime, 'NEG_GAMMA', days=30
        )
        
        return {
            'call_wall_success_rate_7d': call_success_7d,
            'call_wall_success_rate_30d': call_success_30d,
            'put_wall_success_rate_7d': put_success_7d,
            'put_wall_success_rate_30d': put_success_30d,
            'butterfly_success_rate_7d': butterfly_success_7d,
            'butterfly_success_rate_30d': butterfly_success_30d,
            'condor_success_rate_7d': condor_success_7d,
            'condor_success_rate_30d': condor_success_30d,
            'pillar_success_rate_7d': pillar_success_7d,
            'pillar_success_rate_30d': pillar_success_30d,
            'notrade_success_rate_7d': notrade_success_7d,
            'notrade_success_rate_30d': notrade_success_30d
        }


def calculate_success_rate(con: sqlite3.Connection, ndate: int, ntime: int, 
                          setup_type: str, days: int) -> float:
    """
    Calculate success rate for a specific setup type over N days.
    
    Args:
        con: Database connection
        ndate: Current date
        ntime: Current time
        setup_type: 'CALL_WALL' or 'PUT_WALL'
        days: Number of days to look back
    
    Returns:
        Success rate (0.0 to 1.0)
    """
    # Calculate date N days ago
    current_date = datetime.strptime(str(ndate), '%Y%m%d')
    start_date = current_date - timedelta(days=days)
    start_date_int = int(start_date.strftime('%Y%m%d'))
    
    query = """
        SELECT outcome, COUNT(*) 
        FROM trade_signals 
        WHERE setup_type = ? 
        AND ndate BETWEEN ? AND ?
        AND outcome IS NOT NULL
        GROUP BY outcome
    """
    
    cursor = con.execute(query, (setup_type, start_date_int, ndate))
    results = cursor.fetchall()
    
    total_signals = sum(count for _, count in results)
    if total_signals == 0:
        return 0.5  # Default to 50% if no history
    
    successful_signals = sum(count for outcome, count in results 
                           if outcome in ['WIN', 'CORRECT'])
    
    return successful_signals / total_signals


def calculate_wall_strength_score(ndate: int, ntime: int) -> float:
    """
    Calculate composite wall strength score based on historical performance.
    
    Returns:
        Wall strength score (0.0 to 1.0)
    """
    with sqlite3.connect('gex.db') as con:
        # Get recent wall performance
        query = """
            SELECT ts.setup_type, ts.outcome, ts.short_strike, ts.wing_strike
            FROM trade_signals ts
            WHERE ts.ndate <= ? AND (ts.ndate > ? - 100)
            AND ts.setup_type IN ('CALL_WALL', 'PUT_WALL')
            AND ts.outcome IS NOT NULL
            ORDER BY ts.ndate DESC, ts.ntime DESC
            LIMIT 50
        """
        
        cursor = con.execute(query, (ndate, ndate))
        recent_walls = cursor.fetchall()
        
        if not recent_walls:
            return 0.5  # Default strength
        
        # Calculate strength based on success rate only for now
        success_rate = sum(1 for _, outcome, *_ in recent_walls 
                         if outcome in ['WIN', 'CORRECT']) / len(recent_walls)
        
        # Could enhance later with GEX magnitude if needed
        strength_score = success_rate
        
        return min(max(strength_score, 0.0), 1.0)


def calculate_strike_wall_score(ndate: int, ntime: int, setup_type: str, short_strike: float) -> float:
    """
    Calculate strike-specific wall performance score.
    
    This is more granular than setup-type success rates - it tracks performance
    of a specific strike level (e.g., CALL_WALL at 7550 vs 7520).
    
    Args:
        ndate: Current date
        ntime: Current time
        setup_type: 'CALL_WALL' or 'PUT_WALL'
        short_strike: The strike level to evaluate
    
    Returns:
        Strike wall score (0.0 to 1.0), higher = stronger wall
    """
    with sqlite3.connect('gex.db') as con:
        # Look back 90 days for same strike level
        current_date = datetime.strptime(str(ndate), '%Y%m%d')
        start_date = current_date - timedelta(days=90)
        start_date_int = int(start_date.strftime('%Y%m%d'))
        
        query = """
            SELECT outcome, COUNT(*) 
            FROM trade_signals 
            WHERE setup_type = ? 
            AND short_strike = ?
            AND ndate BETWEEN ? AND ?
            AND outcome IS NOT NULL
            AND outcome != 'NEUTRAL'
            GROUP BY outcome
        """
        
        cursor = con.execute(query, (setup_type, short_strike, start_date_int, ndate))
        results = cursor.fetchall()
        
        wins = sum(count for outcome, count in results if outcome in ['WIN', 'CORRECT'])
        losses = sum(count for outcome, count in results if outcome in ['LOSS', 'MISSED'])
        total_decisive = wins + losses
        
        if total_decisive == 0:
            # No decisive history, default to setup-type success rate
            return calculate_success_rate(con, ndate, ntime, setup_type, days=30)
        
        # Use win rate among decisive outcomes
        return wins / total_decisive


def calculate_signal_reliability_score(ndate: int, ntime: int) -> float:
    """
    Calculate overall signal reliability score based on recent performance.
    
    Returns:
        Reliability score (0.0 to 1.0)
    """
    with sqlite3.connect('gex.db') as con:
        # Get recent signal performance across all types
        query = """
            SELECT outcome
            FROM trade_signals
            WHERE ndate >= ? - 30 AND ndate <= ?
            AND outcome IS NOT NULL
            ORDER BY ndate DESC, ntime DESC
            LIMIT 100
        """
        
        cursor = con.execute(query, (ndate, ndate))
        recent_signals = cursor.fetchall()
        
        if not recent_signals:
            return 0.5  # Default reliability
        
        # Calculate simple success rate (no confidence weighting available)
        successful_signals = sum(1 for (outcome,) in recent_signals 
                               if outcome in ['WIN', 'CORRECT'])
        
        reliability = successful_signals / len(recent_signals)
        return min(max(reliability, 0.0), 1.0)


def calculate_recent_signal_performance(ndate: int, ntime: int) -> Dict:
    """
    Calculate recent signal performance over different lookback periods.
    
    Returns:
        Dict with recent performance features
    """
    with sqlite3.connect('gex.db') as con:
        # Last 5 signals
        perf_5 = calculate_recent_performance(con, ndate, ntime, limit=5)
        
        # Last 20 signals
        perf_20 = calculate_recent_performance(con, ndate, ntime, limit=20)
        
        return {
            'recent_signal_performance_5': perf_5,
            'recent_signal_performance_20': perf_20
        }


def calculate_recent_performance(con: sqlite3.Connection, ndate: int, ntime: int, 
                                limit: int) -> float:
    """
    Calculate performance of last N signals.
    
    Args:
        con: Database connection
        ndate: Current date
        ntime: Current time
        limit: Number of recent signals to consider
    
    Returns:
        Performance score (-1.0 to 1.0)
    """
    query = """
        SELECT outcome_points
        FROM trade_signals
        WHERE (ndate < ? OR (ndate = ? AND ntime < ?))
        AND outcome_points IS NOT NULL
        ORDER BY ndate DESC, ntime DESC
        LIMIT ?
    """
    
    cursor = con.execute(query, (ndate, ndate, ntime, limit))
    results = cursor.fetchall()
    
    if not results:
        return 0.0
    
    # Normalize points to -1 to 1 range
    points = [points for (points,) in results]
    max_abs = max(abs(p) for p in points) if points else 1.0
    
    if max_abs == 0:
        return 0.0
    
    normalized_points = [p / max_abs for p in points]
    return sum(normalized_points) / len(normalized_points)


def detect_market_regime_features(ndate: int, ntime: int) -> Dict:
    """
    Detect current market regime features that affect signal reliability.
    
    Returns:
        Dict with regime features (0 or 1)
    """
    with sqlite3.connect('gex.db') as con:
        # Get recent market data (need to derive GEX from JSON)
        query = """
            SELECT price, data
            FROM gex_strike_window
            WHERE ndate >= ? - 5 AND ndate <= ?
            AND price IS NOT NULL
            ORDER BY ndate, ntime
        """
        
        cursor = con.execute(query, (ndate, ndate))
        market_data = cursor.fetchall()
        
        if len(market_data) < 10:
            return {
                'high_volatility_regime': 0,
                'trending_market': 0,
                'choppy_market': 1,  # Default to choppy
                'macro_event_risk': 0
            }
        
        prices = [row[0] for row in market_data if row[0]]
        
        # Extract GEX from JSON data
        call_gex = []
        put_gex = []
        for _, json_data in market_data:
            try:
                import json
                data = json.loads(json_data)
                if 'strikes' in data:
                    total_call = sum(s.get('cg', 0) for s in data['strikes'])
                    total_put = sum(s.get('pg', 0) for s in data['strikes'])
                    call_gex.append(total_call)
                    put_gex.append(total_put)
            except:
                continue
        
        # Detect high volatility regime
        volatility = calculate_volatility(prices)
        high_volatility = 1 if volatility > 0.02 else 0  # 2% daily volatility threshold
        
        # Detect trending vs choppy market
        trending = detect_trending_market(prices)
        choppy = 1 - trending
        
        # Detect macro event risk (simplified - could be enhanced with economic calendar)
        macro_risk = detect_macro_event_risk(ndate, call_gex, put_gex)
        
        return {
            'high_volatility_regime': high_volatility,
            'trending_market': trending,
            'choppy_market': choppy,
            'macro_event_risk': macro_risk
        }


def calculate_volatility(prices: List[float]) -> float:
    """Calculate price volatility as standard deviation of returns."""
    if len(prices) < 2:
        return 0.0
    
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
    
    if not returns:
        return 0.0
    
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    
    return variance ** 0.5


def detect_trending_market(prices: List[float]) -> int:
    """
    Detect if market is trending vs choppy.
    
    Returns:
        1 if trending, 0 if choppy
    """
    if len(prices) < 10:
        return 0
    
    # Simple trend detection using linear regression slope
    n = len(prices)
    x_sum = sum(range(n))
    y_sum = sum(prices)
    xy_sum = sum(i * price for i, price in enumerate(prices))
    x2_sum = sum(i * i for i in range(n))
    
    slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
    
    # Normalize slope by price level
    avg_price = y_sum / n
    normalized_slope = slope / avg_price if avg_price > 0 else 0
    
    # Threshold for trending
    return 1 if abs(normalized_slope) > 0.001 else 0


def detect_macro_event_risk(ndate: int, call_gex: List[float], put_gex: List[float]) -> int:
    """
    Detect macro event risk based on GEX patterns.
    
    Returns:
        1 if high macro risk, 0 otherwise
    """
    if not call_gex or not put_gex:
        return 0
    
    # High macro risk if both call and put GEX are elevated
    avg_call = sum(call_gex) / len(call_gex)
    avg_put = sum(put_gex) / len(put_gex)
    
    # Thresholds could be calibrated
    high_gex_threshold = 5e8  # 500M
    
    if avg_call > high_gex_threshold and avg_put > high_gex_threshold:
        return 1
    
    return 0


def persist_trade_signal_features(ndate: int, ntime: int, symbol: str = 'SPX'):
    """
    Calculate and persist trade signal features for a snapshot.
    
    Args:
        ndate: Date in YYYYMMDD format
        ntime: Time in HHMM format
        symbol: Ticker symbol
    """
    features = calculate_trade_signal_features(ndate, ntime, symbol)
    
    with sqlite3.connect('gex.db') as con:
        con.execute("""
            INSERT OR REPLACE INTO trade_signal_features
            (ndate, ntime, symbol,
             call_wall_success_rate_7d, call_wall_success_rate_30d,
             put_wall_success_rate_7d, put_wall_success_rate_30d,
             butterfly_success_rate_7d, butterfly_success_rate_30d,
             condor_success_rate_7d, condor_success_rate_30d,
             pillar_success_rate_7d, pillar_success_rate_30d,
             notrade_success_rate_7d, notrade_success_rate_30d,
             wall_strength_score, signal_reliability_score,
             recent_signal_performance_5, recent_signal_performance_20,
             high_volatility_regime, trending_market, choppy_market, macro_event_risk,
             calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ndate, ntime, symbol,
            features.get('call_wall_success_rate_7d', 0.5),
            features.get('call_wall_success_rate_30d', 0.5),
            features.get('put_wall_success_rate_7d', 0.5),
            features.get('put_wall_success_rate_30d', 0.5),
            features.get('butterfly_success_rate_7d', 0.5),
            features.get('butterfly_success_rate_30d', 0.5),
            features.get('condor_success_rate_7d', 0.5),
            features.get('condor_success_rate_30d', 0.5),
            features.get('pillar_success_rate_7d', 0.5),
            features.get('pillar_success_rate_30d', 0.5),
            features.get('notrade_success_rate_7d', 0.5),
            features.get('notrade_success_rate_30d', 0.5),
            features.get('wall_strength_score', 0.5),
            features.get('signal_reliability_score', 0.5),
            features.get('recent_signal_performance_5', 0.0),
            features.get('recent_signal_performance_20', 0.0),
            features.get('high_volatility_regime', 0),
            features.get('trending_market', 0),
            features.get('choppy_market', 1),
            features.get('macro_event_risk', 0),
            datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        ))


def backfill_trade_signal_features(start_date: int = None, end_date: int = None):
    """
    Backfill trade signal features for historical data.
    
    Args:
        start_date: Start date in YYYYMMDD format (optional)
        end_date: End date in YYYYMMDD format (optional)
    """
    with sqlite3.connect('gex.db') as con:
        # Get date range if not provided
        if not start_date:
            cursor = con.execute("SELECT MIN(ndate) FROM trade_signals WHERE outcome IS NOT NULL")
            start_date = cursor.fetchone()[0]
        
        if not end_date:
            cursor = con.execute("SELECT MAX(ndate) FROM trade_signals")
            end_date = cursor.fetchone()[0]
        
        # Get all snapshots that need features
        query = """
            SELECT DISTINCT ndate, ntime, symbol
            FROM trade_signals
            WHERE ndate BETWEEN ? AND ?
            AND outcome IS NOT NULL
            ORDER BY ndate, ntime
        """
        
        cursor = con.execute(query, (start_date, end_date))
        snapshots = cursor.fetchall()
        
        print(f"Backfilling features for {len(snapshots)} snapshots...")
        
        for i, (ndate, ntime, symbol) in enumerate(snapshots):
            try:
                persist_trade_signal_features(ndate, ntime, symbol)
                
                if (i + 1) % 100 == 0:
                    print(f"Processed {i + 1}/{len(snapshots)} snapshots...")
                    
            except Exception as e:
                print(f"Error processing {ndate} {ntime}: {e}")
        
        print(f"✅ Backfill completed for {len(snapshots)} snapshots")


if __name__ == "__main__":
    # Test the feature calculation
    print("Testing trade signal feature calculation...")
    
    # Test with recent data
    test_date = 20260706
    test_time = 1246
    
    try:
        features = calculate_trade_signal_features(test_date, test_time)
        print("✅ Feature calculation successful")
        print(f"Calculated {len(features)} features:")
        for key, value in features.items():
            print(f"  {key}: {value}")
        
        # Persist test features
        persist_trade_signal_features(test_date, test_time)
        print("✅ Feature persistence successful")
        
    except Exception as e:
        print(f"❌ Error: {e}")
