"""
GEX calculation functions for the new gex_strike_window table.
Each metric has a separate function for clarity and testability.
"""

import math

def calculate_sentiment(strikes):
    """Calculate sentiment percentage.
    
    Sentiment = percentage of strikes with positive net GEX.
    
    Args:
        strikes: List of strike dictionaries with 'net' field
        
    Returns:
        int: Sentiment percentage (0-100)
    """
    if not strikes:
        return 50
    
    pos_bars = sum(1 for r in strikes if (r.get("net", 0) or 0) > 0)
    return round(pos_bars / len(strikes) * 100)


def calculate_gex_ratio(strikes):
    """Calculate GEX ratio.
    
    GEX ratio = call_gex / put_gex (with sign flip based on which absolute value is larger)
    Example: 2b neg and 3b pos = 3b / 2b = 1.5x (positive)
             3b neg and 2b pos = -3b / 2b = -1.5x (negative)
    
    Args:
        strikes: List of strike dictionaries with 'cg' and 'pg' fields
        
    Returns:
        float: GEX ratio
    """
    if not strikes:
        return 0
    
    call_gex = sum(r.get("cg", 0) or 0 for r in strikes)
    put_gex = sum(r.get("pg", 0) or 0 for r in strikes)
    
    abs_call = abs(call_gex)
    abs_put = abs(put_gex)
    
    if abs_call > abs_put:
        return round((call_gex / abs_put) * 100, 1) if abs_put else 0
    else:
        return round((-abs_put / call_gex) * 100, 1) if call_gex else 0


def calculate_net_gex(strikes):
    """Calculate net GEX.
    
    Net GEX = call_gex + put_gex (put_gex is already negative)
    
    Args:
        strikes: List of strike dictionaries with 'cg' and 'pg' fields
        
    Returns:
        float: Net GEX
    """
    if not strikes:
        return 0
    
    call_gex = sum(r.get("cg", 0) or 0 for r in strikes)
    put_gex = sum(r.get("pg", 0) or 0 for r in strikes)
    return call_gex + put_gex


def calculate_kcs(strikes, uprice):
    """Calculate KCS (Key Call Support).
    
    KCS = weighted score based on GEX share, OI share, volume share, and proximity.
    Formula: (0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * proximity * 100
    
    Args:
        strikes: List of strike dictionaries
        uprice: SPX price
        
    Returns:
        float: KCS value (0-15 range typically)
    """
    if not strikes:
        return 0
    
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in strikes)
    total_oi = sum((r.get("coi", 0) or 0) + (r.get("poi", 0) or 0) for r in strikes)
    total_vol = sum((r.get("cvol", 0) or 0) + (r.get("pvol", 0) or 0) for r in strikes)
    
    if total_abs == 0:
        return 0
    
    # Find key strike (max abs * proximity weighted)
    key_row = max(strikes, key=lambda r: abs(r.get("abs", 0) or 0) * math.exp(-abs(r["strike"] - uprice) / 25.0))
    key_strike = key_row["strike"]
    key_abs = abs(key_row.get("abs", 0) or 0)
    key_cg = key_row.get("cg", 0) or 0
    key_pg = key_row.get("pg", 0) or 0
    key_coi = key_row.get("coi", 0) or 0
    key_poi = key_row.get("poi", 0) or 0
    key_cvol = key_row.get("cvol", 0) or 0
    key_pvol = key_row.get("pvol", 0) or 0
    
    distance = abs(key_strike - uprice)
    prox = math.exp(-distance / 25.0)
    gex_share = key_abs / total_abs if total_abs else 0.0
    oi_share = (key_coi + key_poi) / total_oi if total_oi else 0.0
    vol_share = (key_cvol + key_pvol) / total_vol if total_vol else 0.0
    
    kcs = round((0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * prox * 100, 2)
    return kcs


def calculate_dominance(strikes, uprice):
    """Calculate dominance.
    
    Dominance = key_abs / total_abs (key strike's share of total absolute GEX)
    
    Args:
        strikes: List of strike dictionaries
        uprice: SPX price
        
    Returns:
        float: Dominance percentage (0-100)
    """
    if not strikes:
        return 0
    
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in strikes)
    if total_abs == 0:
        return 0
    
    # Find key strike (max abs * proximity weighted)
    key_row = max(strikes, key=lambda r: abs(r.get("abs", 0) or 0) * math.exp(-abs(r["strike"] - uprice) / 25.0))
    key_abs = abs(key_row.get("abs", 0) or 0)
    
    dominance_pct = round(key_abs / total_abs * 100, 2)
    return dominance_pct


def calculate_key_strike_stats(strikes, uprice):
    """Calculate key strike statistics.
    
    Args:
        strikes: List of strike dictionaries
        uprice: SPX price
        
    Returns:
        dict: Key strike statistics including:
            - key_strike: strike price
            - key_call_gex: call GEX at key strike
            - key_put_gex: put GEX at key strike
            - key_call_oi: call OI at key strike
            - key_put_oi: put OI at key strike
            - key_call_vol: call volume at key strike
            - key_put_vol: put volume at key strike
            - key2_strike: secondary key strike (highest abs weighted by proximity)
            - key2_abs: absolute GEX at secondary key
            - key2_call_vol: call volume at secondary key
            - key2_put_vol: put volume at secondary key
    """
    if not strikes:
        return {
            "key_strike": 0,
            "key_call_gex": 0,
            "key_put_gex": 0,
            "key_call_oi": 0,
            "key_put_oi": 0,
            "key_call_vol": 0,
            "key_put_vol": 0,
            "key2_strike": 0,
            "key2_abs": 0,
            "key2_call_vol": 0,
            "key2_put_vol": 0
        }
    
    # Find key strike (max abs * proximity weighted)
    key_row = max(strikes, key=lambda r: abs(r.get("abs", 0) or 0) * math.exp(-abs(r["strike"] - uprice) / 25.0))
    
    # Find secondary key strike (excluding the key strike)
    other_rows = [r for r in strikes if r["strike"] != key_row["strike"]]
    key2_row = max(other_rows, key=lambda r: abs(r.get("abs", 0) or 0) * math.exp(-abs(r["strike"] - uprice) / 25.0)) if other_rows else None
    
    return {
        "key_strike": key_row.get("strike", 0),
        "key_call_gex": key_row.get("cg", 0) or 0,
        "key_put_gex": key_row.get("pg", 0) or 0,
        "key_call_oi": key_row.get("coi", 0) or 0,
        "key_put_oi": key_row.get("poi", 0) or 0,
        "key_call_vol": key_row.get("cvol", 0) or 0,
        "key_put_vol": key_row.get("pvol", 0) or 0,
        "key2_strike": key2_row.get("strike", 0) if key2_row else 0,
        "key2_abs": abs(key2_row.get("abs", 0) or 0) if key2_row else 0,
        "key2_call_vol": key2_row.get("cvol", 0) or 0 if key2_row else 0,
        "key2_put_vol": key2_row.get("pvol", 0) or 0 if key2_row else 0
    }


def calculate_total_oi_and_vol(strikes):
    """Calculate total OI and volume.
    
    Args:
        strikes: List of strike dictionaries
        
    Returns:
        dict: Total call/put OI and volume
    """
    if not strikes:
        return {
            "total_call_oi": 0,
            "total_put_oi": 0,
            "total_call_vol": 0,
            "total_put_vol": 0
        }
    
    return {
        "total_call_oi": sum(r.get("coi", 0) or 0 for r in strikes),
        "total_put_oi": sum(r.get("poi", 0) or 0 for r in strikes),
        "total_call_vol": sum(r.get("cvol", 0) or 0 for r in strikes),
        "total_put_vol": sum(r.get("pvol", 0) or 0 for r in strikes)
    }


def calculate_total_gex(strikes):
    """Calculate total call and put GEX.
    
    Args:
        strikes: List of strike dictionaries
        
    Returns:
        dict: Total call/put GEX
    """
    if not strikes:
        return {
            "total_call_gex": 0,
            "total_put_gex": 0
        }
    
    return {
        "total_call_gex": sum(r.get("cg", 0) or 0 for r in strikes),
        "total_put_gex": sum(r.get("pg", 0) or 0 for r in strikes)
    }


def calculate_raw_aggregates(strikes):
    """Calculate raw aggregate sums across all strikes.
    
    Args:
        strikes: List of strike dictionaries with 'pcmag', 'cotm', 'potm' fields
        
    Returns:
        dict: Summed raw aggregate values
    """
    if not strikes:
        return {"pcmag": 0, "cotm": 0, "potm": 0}
    
    return {
        "pcmag": sum(r.get("pcmag", 0) or 0 for r in strikes),
        "cotm": sum(r.get("cotm", 0) or 0 for r in strikes),
        "potm": sum(r.get("potm", 0) or 0 for r in strikes),
    }


def calculate_flip_level(strikes):
    """Calculate GEX flip level.
    
    Flip level is the strike where cumulative net GEX crosses zero within the 40-strike window.
    Sort by strike, walk upward accumulating net GEX; flip = first zero crossing.
    
    Args:
        strikes: List of strike dictionaries with 'strike' and 'net' fields
        
    Returns:
        float: Flip level strike price, or None if no zero crossing found
    """
    if not strikes:
        return None
    
    sorted_strikes = sorted(strikes, key=lambda r: r["strike"])
    prev_cum = 0
    prev_strike = sorted_strikes[0]["strike"]
    
    for r in sorted_strikes:
        cum = prev_cum + (r.get("net", 0) or 0)
        if (prev_cum < 0 and cum >= 0) or (prev_cum > 0 and cum <= 0):
            denom = abs(cum - prev_cum)
            flip = round(prev_strike + (r["strike"] - prev_strike) * abs(prev_cum) / denom, 1) if denom else r["strike"]
            return flip
        prev_cum = cum
        prev_strike = r["strike"]
    
    return None
