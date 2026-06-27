"""Regenerate trade signals for all historical dates in the snapshot table.

Calls the /api/trade-signals/generate endpoint for each unique date,
or can be run standalone to call the internal logic directly.
"""
import sqlite3
import sys
import os

# Add project dir to path so we can import gex_viewer internals
sys.path.insert(0, os.path.dirname(__file__))


def main():
    db_path = os.path.join(os.path.dirname(__file__), "gex.db")
    con = sqlite3.connect(db_path)

    # Get all unique dates from snapshot table (historical only, RTH only)
    dates = con.execute(
        "SELECT DISTINCT ndate FROM snapshot WHERE symbol='SPX' ORDER BY ndate"
    ).fetchall()
    con.close()

    print(f"Found {len(dates)} dates to process")

    # Import the internal functions from gex_viewer
    from gex_viewer import (
        _generate_trade_signal, _db
    )

    total_generated = 0
    total_skipped = 0

    for (ndate,) in dates:
        with _db() as con:
            snap_rows = con.execute(
                "SELECT ntime, uprice, net_gex, sentiment, gex_ratio, kcs, dominance, "
                "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                "key2_strike, key2_abs, flip, hmm_label, is_premarket "
                "FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                (ndate,)
            ).fetchall()

        if not snap_rows:
            total_skipped += 1
            continue

        snap_cols = ["ntime", "uprice", "net_gex", "sentiment_pct", "gex_ratio", "kcs",
                     "key_dominance_pct", "total_call_gex", "total_put_gex", "key_strike",
                     "key_call_gex", "key_put_gex", "total_call_oi", "total_put_oi",
                     "key_call_oi", "key_put_oi", "total_call_vol", "total_put_vol",
                     "key_call_vol", "key_put_vol", "key2_strike", "key2_abs", "flip",
                     "hmm_label", "is_premarket"]
        snaps = [dict(zip(snap_cols, r)) for r in snap_rows]

        # Load existing signals for prev_outcome chain
        with _db() as con:
            existing = con.execute(
                "SELECT ntime, action, short_strike, structure FROM trade_signals "
                "WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
                (ndate,)
            ).fetchall()
        sig_by_time = {r[0]: {"action": r[1], "short_strike": r[2], "structure": r[3]}
                       for r in existing}

        date_generated = 0
        for i, snap in enumerate(snaps):
            ntime = snap["ntime"]
            prev_snap = snaps[i - 1] if i > 0 else None
            prev_sig = sig_by_time.get(snaps[i - 1]["ntime"]) if i > 0 else None
            signal = _generate_trade_signal(snap, prev_snap, prev_sig)

            # Calculate outcome based on next snapshot
            next_spx = None
            next_ntime = None
            outcome = None
            outcome_points = None

            if i < len(snaps) - 1:
                next_snap = snaps[i + 1]
                next_spx = next_snap.get("uprice")
                next_ntime = next_snap.get("ntime")
                curr_spx = snap.get("uprice")
                action = signal.get("action")
                short_strike = signal.get("short_strike")

                if curr_spx and next_spx:
                    spx_move = next_spx - curr_spx
                    if action == "STAY_OUT":
                        if abs(spx_move) < 10:
                            outcome = "CORRECT"
                            outcome_points = 0
                        else:
                            outcome = "MISSED"
                            outcome_points = abs(spx_move)
                    elif short_strike:
                        if "PUT" in str(signal.get("structure", "")):
                            if next_spx > short_strike:
                                outcome = "WIN"
                                outcome_points = abs(spx_move)
                            elif next_spx < short_strike - 5:
                                outcome = "LOSS"
                                outcome_points = -abs(spx_move)
                            else:
                                outcome = "NEUTRAL"
                                outcome_points = spx_move
                        elif "CALL" in str(signal.get("structure", "")):
                            if next_spx < short_strike:
                                outcome = "WIN"
                                outcome_points = abs(spx_move)
                            elif next_spx > short_strike + 5:
                                outcome = "LOSS"
                                outcome_points = -abs(spx_move)
                            else:
                                outcome = "NEUTRAL"
                                outcome_points = spx_move
                        else:
                            outcome = "NEUTRAL"
                            outcome_points = spx_move

            from datetime import datetime
            ts = datetime.utcnow().isoformat()
            with _db() as wcon:
                wcon.execute(
                    "INSERT OR IGNORE INTO trade_signals "
                    "(ndate, ntime, symbol, generated_ts, regime, setup_type, action, "
                    "short_strike, wing_strike, short_strike2, wing_strike2, "
                    "structure, rationale, invalidation, caution, prev_outcome, "
                    "is_llm_enhanced, next_spx, next_ntime, outcome, outcome_points) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ndate, ntime, "SPX", ts,
                     signal.get("regime"), signal.get("setup_type"), signal.get("action"),
                     signal.get("short_strike"), signal.get("wing_strike"),
                     signal.get("short_strike2"), signal.get("wing_strike2"),
                     signal.get("structure"), signal.get("rationale"),
                     signal.get("invalidation"), signal.get("caution"),
                     signal.get("prev_outcome"), 0, next_spx, next_ntime, outcome, outcome_points)
                )
                # If row already existed (IGNORE), update only next_spx/outcome if not yet set
                wcon.execute(
                    "UPDATE trade_signals SET next_spx=?, next_ntime=?, outcome=?, outcome_points=? "
                    "WHERE ndate=? AND ntime=? AND symbol='SPX' AND outcome IS NULL",
                    (next_spx, next_ntime, outcome, outcome_points, ndate, ntime)
                )
            date_generated += 1

        total_generated += date_generated
        print(f"  {ndate}: {date_generated} signals generated")

    print(f"\nDone: {total_generated} signals generated across {len(dates) - total_skipped} dates ({total_skipped} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
