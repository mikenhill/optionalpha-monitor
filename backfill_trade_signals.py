#!/usr/bin/env python3
"""
Backfill trade signals for all historical dates to create training data.
Works directly with the database (no HTTP API required).
"""
import sqlite3
from pathlib import Path
import sys

DB_PATH = Path("gex.db")


def get_available_dates():
    """Get all dates with historical snapshots."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        'SELECT DISTINCT ndate FROM gex_snapshots WHERE symbol="SPX" ORDER BY ndate'
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def load_snapshots_for_date(ndate):
    """Load all snapshots for a date from gex_snapshots."""
    con = sqlite3.connect(DB_PATH)
    cursor = con.execute(
        "SELECT * FROM gex_snapshots WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
        (ndate,)
    )
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    con.close()
    
    return [dict(zip(col_names, r)) for r in rows]


def generate_signals_for_date(ndate):
    """Generate trade signals for a single date (direct DB access)."""
    # Import the signal generation functions from gex_viewer
    sys.path.insert(0, str(Path(__file__).parent))
    from gex_viewer import _classify_gex_setup, _generate_trade_signal, _persist_trade_signal
    
    snaps = load_snapshots_for_date(ndate)
    if not snaps:
        return 0
    
    # Load existing signals for prev_outcome chain
    con = sqlite3.connect(DB_PATH)
    existing = con.execute(
        "SELECT ntime, action, short_strike, structure FROM trade_signals "
        "WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
        (ndate,)
    ).fetchall()
    con.close()
    
    sig_by_time = {r[0]: {"action": r[1], "short_strike": r[2], "structure": r[3]}
                   for r in existing}
    
    generated = 0
    for i, snap in enumerate(snaps):
        ntime = snap["ntime"]
        prev_snap = snaps[i - 1] if i > 0 else None
        prev_sig = sig_by_time.get(snaps[i - 1]["ntime"]) if i > 0 else None
        signal = _generate_trade_signal(snap, prev_snap, prev_sig)
        
        # Calculate intraday outcome based on next snapshot
        next_spx = None
        next_ntime = None
        outcome = None
        outcome_points = None
        
        if i < len(snaps) - 1:  # Has next snapshot
            next_snap = snaps[i + 1]
            next_spx = next_snap.get("uprice")
            next_ntime = next_snap.get("ntime")
            curr_spx = snap.get("uprice")
            action = signal.get("action")
            short_strike = signal.get("short_strike")
            WING = 10
            
            if action == "STAY_OUT":
                move = abs(next_spx - curr_spx) if next_spx and curr_spx else 0
                if move < 5:
                    outcome = "MISSED"
                    outcome_points = 0
                elif move > 15:
                    outcome = "CORRECT"
                    outcome_points = move
                else:
                    outcome = "NEUTRAL"
                    outcome_points = 0
            elif action == "SHORT_PUT_SPREAD" and short_strike:
                if next_spx >= short_strike:
                    outcome = "WIN"
                    outcome_points = next_spx - curr_spx
                else:
                    outcome = "LOSS"
                    outcome_points = curr_spx - next_spx
            elif action == "SHORT_CALL_SPREAD" and short_strike:
                if next_spx <= short_strike:
                    outcome = "WIN"
                    outcome_points = curr_spx - next_spx
                else:
                    outcome = "LOSS"
                    outcome_points = next_spx - curr_spx
            elif action == "IRON_BUTTERFLY" and short_strike:
                dist = abs(next_spx - short_strike)
                if dist <= 5:
                    outcome = "WIN"
                    outcome_points = 5 - dist
                elif dist <= WING:
                    outcome = "PARTIAL"
                    outcome_points = WING - dist
                else:
                    outcome = "LOSS"
                    outcome_points = -(dist - WING)
            else:
                outcome = "NEUTRAL"
                outcome_points = 0
        
        _persist_trade_signal(ndate, ntime, signal, next_spx, next_ntime, outcome, outcome_points)
        sig_by_time[ntime] = signal
        generated += 1
    
    return generated


def main():
    print("Fetching available dates...")
    dates = get_available_dates()
    print(f"Found {len(dates)} dates")
    
    print("\nGenerating trade signals (direct DB access, no server required)...")
    success = 0
    for i, ndate in enumerate(dates):
        ndate_str = str(ndate)
        date_iso = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]}"
        
        try:
            count = generate_signals_for_date(ndate)
            print(f"  {date_iso}: {count} signals generated")
            success += 1
        except Exception as e:
            import traceback
            print(f"  {date_iso}: ERROR - {e}")
            traceback.print_exc()
        
        # Progress update every 10 dates
        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{len(dates)} dates processed ({success} successful)")
    
    print(f"\nDone. Generated signals for {success}/{len(dates)} dates.")
    print("You can now run train_trade_classifier.py to train the model.")


if __name__ == "__main__":
    main()
