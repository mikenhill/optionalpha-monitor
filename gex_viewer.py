"""
GEX Viewer — Interactive intraday GEX + SPX educator
======================================================
Flask server that serves an interactive HTML page for stepping through a
trading day 30 minutes at a time, showing SPX price with GEX levels overlaid
and the GEX bar chart alongside teaching points explaining GEX-price dynamics.

Usage
-----
  python gex_viewer.py
  # Then open http://localhost:5050 in a browser
"""

import bisect
import json
import math
import sqlite3
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, redirect, make_response

app = Flask(__name__)

# Import MVC controllers for Phase 2 refactoring
from controllers.dates_controller import DatesController
from controllers.snapshot_controller import SnapshotController
from controllers.admin_controller import AdminController
from controllers.percentiles_controller import PercentilesController
from controllers.trade_signals_controller import TradeSignalsController
from controllers.narrative_controller import NarrativeController
from controllers.csv_controller import CsvController
from controllers.spx_controller import SpxController

BASE_DIR  = Path(__file__).resolve().parent
GEX_DIR   = BASE_DIR / "results" / "histgex"
DB_PATH   = BASE_DIR / "gex.db"
MODEL_PATH = BASE_DIR / "trade_rf_model.pkl"
SCALER_PATH = BASE_DIR / "trade_rf_scaler.pkl"

# Global cache for RF model and scaler
_rf_model = None
_rf_scaler = None


def _load_rf_model():
    """Load the Random Forest model and scaler (cached)."""
    global _rf_model, _rf_scaler
    if _rf_model is None and MODEL_PATH.exists() and SCALER_PATH.exists():
        _rf_model = joblib.load(MODEL_PATH)
        _rf_scaler = joblib.load(SCALER_PATH)
    return _rf_model, _rf_scaler


def _prepare_rf_features(snap: dict) -> np.ndarray:
    """Prepare features for RF prediction (matching training script)."""
    # Base features
    features = {
        'uprice': snap.get('uprice', 0) or 0,
        'net_gex': snap.get('net_gex', 0) or 0,
        'sentiment': snap.get('sentiment', snap.get('sentiment_pct', 50)) or 50,
        'gex_ratio': snap.get('gex_ratio', 1) or 1,
        'kcs': snap.get('kcs', 0) or 0,
        'dominance': snap.get('dominance', snap.get('key_dominance_pct', 0)) or 0,
        'total_call_gex': snap.get('total_call_gex', 0) or 0,
        'total_put_gex': snap.get('total_put_gex', 0) or 0,
        'total_call_oi': snap.get('total_call_oi', 0) or 0,
        'total_put_oi': snap.get('total_put_oi', 0) or 0,
        'total_call_vol': snap.get('total_call_vol', 0) or 0,
        'total_put_vol': snap.get('total_put_vol', 0) or 0,
        'key_strike': snap.get('key_strike', 0) or 0,
        'key_call_gex': snap.get('key_call_gex', 0) or 0,
        'key_put_gex': snap.get('key_put_gex', 0) or 0,
        'key_call_oi': snap.get('key_call_oi', 0) or 0,
        'key_put_oi': snap.get('key_put_oi', 0) or 0,
        'key_call_vol': snap.get('key_call_vol', 0) or 0,
        'key_put_vol': snap.get('key_put_vol', 0) or 0,
        'key2_strike': snap.get('key2_strike', 0) or 0,
        'key2_abs': snap.get('key2_abs', 0) or 0,
        'key2_call_vol': snap.get('key2_call_vol', 0) or 0,
        'key2_put_vol': snap.get('key2_put_vol', 0) or 0,
        'flip': snap.get('flip', 0) or 0,
        'hmm_state': 0  # Simplified for prediction
    }
    
    # Derived features
    features['net_oi'] = features['total_call_oi'] - features['total_put_oi']
    features['net_vol'] = features['total_call_vol'] - features['total_put_vol']
    features['key_net_gex'] = features['key_call_gex'] - features['key_put_gex']
    features['key_net_oi'] = features['key_call_oi'] - features['key_put_oi']
    features['dist_to_key'] = abs(features['uprice'] - features['key_strike'])
    features['dist_to_flip'] = abs(features['uprice'] - features['flip']) if features['flip'] else 0
    
    # Feature order must match training
    feature_cols = [
        'uprice', 'net_gex', 'sentiment', 'gex_ratio', 
        'kcs', 'dominance', 'total_call_gex', 'total_put_gex',
        'total_call_oi', 'total_put_oi', 'total_call_vol', 'total_put_vol',
        'key_strike', 'key_call_gex', 'key_put_gex',
        'key_call_oi', 'key_put_oi', 'key_call_vol', 'key_put_vol',
        'key2_strike', 'key2_abs', 'key2_call_vol', 'key2_put_vol',
        'flip', 'hmm_state',
        'net_oi', 'net_vol', 'key_net_gex', 'key_net_oi', 'dist_to_key', 'dist_to_flip'
    ]
    
    X = np.array([[features[col] for col in feature_cols]])
    return X


def _predict_rf_outcome(snap: dict) -> dict:
    """Predict trade outcome using Random Forest model.
    
    Returns dict with 'probability' (0-1) and 'prediction' (WIN/LOSS).
    """
    model, scaler = _load_rf_model()
    if model is None or scaler is None:
        return {'probability': 0.5, 'prediction': 'NEUTRAL', 'available': False}
    
    X = _prepare_rf_features(snap)
    X_scaled = scaler.transform(X)
    
    # Get probability of class 1 (WIN)
    proba = model.predict_proba(X_scaled)[0, 1]
    prediction = 'WIN' if proba > 0.5 else 'LOSS'
    
    return {
        'probability': float(proba),
        'prediction': prediction,
        'available': True
    }


def _db() -> sqlite3.Connection:
    """Open a SQLite connection, retrying on transient Drive-sync I/O errors.

    Tries WAL mode first; if the WAL/SHM files are locked by Google Drive
    (disk I/O error), waits briefly and retries up to 5 times, then falls
    back to DELETE journal mode which avoids WAL files entirely.
    """
    import time as _time
    wal = DB_PATH.with_suffix(".db-wal")
    shm = DB_PATH.with_suffix(".db-shm")
    last_exc = None
    for attempt in range(5):
        try:
            con = sqlite3.connect(str(DB_PATH), timeout=10)
            con.execute("PRAGMA journal_mode=WAL")
            con.row_factory = sqlite3.Row
            return con
        except sqlite3.OperationalError as exc:
            last_exc = exc
            if "disk I/O" in str(exc) or "database is locked" in str(exc):
                # Try to remove stale WAL/SHM left by Drive sync
                for f in (wal, shm):
                    try:
                        if f.exists() and f.stat().st_size == 0:
                            f.unlink()
                    except OSError:
                        pass
                _time.sleep(1.0 * (attempt + 1))
            else:
                raise
    # WAL unavailable — fall back to DELETE mode (no WAL files created)
    try:
        con = sqlite3.connect(str(DB_PATH), timeout=10)
        con.execute("PRAGMA journal_mode=DELETE")
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.OperationalError:
        raise last_exc


def _ensure_live_analysis_table() -> None:
    """Create the live_analysis table if it does not exist."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS live_analysis (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                saved_ts        TEXT NOT NULL,
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                spx_last        REAL,
                net_gex         REAL,
                key_strike      REAL,
                flip            REAL,
                regime          TEXT,
                thesis_text     TEXT,
                verdict         TEXT,
                signals_json    TEXT,
                intraday_summary TEXT,
                full_json       TEXT NOT NULL
            )
        """)
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_live_analysis_date_time "
            "ON live_analysis (ndate, ntime)"
        )


def _ensure_narratives_table() -> None:
    """Create the daily_narratives and trade_signals tables."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS daily_narratives (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ndate           INTEGER NOT NULL UNIQUE,
                narrative       TEXT NOT NULL,
                generated_at    TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                is_llm_enhanced INTEGER NOT NULL DEFAULT 0
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_daily_narratives_date "
            "ON daily_narratives (ndate)"
        )
        con.execute("""
            CREATE TABLE IF NOT EXISTS trade_signals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                symbol          TEXT NOT NULL DEFAULT 'SPX',
                generated_ts    TEXT NOT NULL,
                regime          TEXT,
                setup_type      TEXT,
                action          TEXT,
                short_strike    REAL,
                wing_strike     REAL,
                short_strike2   REAL,
                wing_strike2    REAL,
                structure       TEXT,
                rationale       TEXT,
                invalidation    TEXT,
                caution         TEXT,
                prev_outcome    TEXT,
                next_spx        REAL,
                next_ntime      INTEGER,
                outcome         TEXT,
                outcome_points  REAL,
                is_llm_enhanced INTEGER NOT NULL DEFAULT 0,
                UNIQUE(ndate, ntime, symbol)
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_trade_signals_date "
            "ON trade_signals (ndate, ntime)"
        )

        # Migration: add outcome columns if they don't exist
        cursor = con.execute("PRAGMA table_info(trade_signals)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        new_cols = [
            ("next_spx", "REAL"),
            ("next_ntime", "INTEGER"),
            ("outcome", "TEXT"),
            ("outcome_points", "REAL")
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                con.execute(f"ALTER TABLE trade_signals ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to trade_signals table")


def _classify_gex_setup(snap: dict) -> str:
    """Classify the GEX setup type for a snapshot using teaching material rules.

    Returns one of: PIN, PUT_PILLAR, CALL_WALL, NEG_GAMMA, POS_GAMMA, GEX_SLIDE, STAY_OUT
    """
    net_gex        = snap.get("net_gex", 0) or 0
    key_call_gex   = snap.get("key_call_gex", 0) or 0
    key_put_gex    = snap.get("key_put_gex", 0) or 0
    key_call_oi    = snap.get("key_call_oi", 0) or 0
    key_put_oi     = snap.get("key_put_oi", 0) or 0
    key_dominance  = snap.get("key_dominance_pct", snap.get("dominance", 0)) or 0
    sentiment      = snap.get("sentiment_pct", snap.get("sentiment", 50)) or 50
    kcs            = snap.get("kcs", 0) or 0
    key2_abs       = snap.get("key2_abs", 0) or 0
    key_abs        = abs(key_call_gex) + abs(key_put_gex)
    uprice         = snap.get("uprice", 0) or 0
    key_strike     = snap.get("key_strike") or 0
    flip           = snap.get("flip")
    hmm_label      = snap.get("hmm_label", "") or ""

    # STAY_OUT: pre-market or very low conviction
    if snap.get("is_premarket", 0):
        return "STAY_OUT"

    # NEG_GAMMA: strongly negative net GEX — acceleration risk, no premium selling
    if net_gex < -5_000_000_000:
        return "NEG_GAMMA"

    # GEX_SLIDE: low concentration, distributed gamma
    if key_dominance < 10 or kcs < 5:
        return "GEX_SLIDE"

    # PIN: balanced call & put at key strike, both large
    if key_abs > 0:
        call_ratio = abs(key_call_gex) / key_abs
        if 0.35 <= call_ratio <= 0.65 and kcs >= 12:
            return "PIN"

    # PUT_PILLAR: put-heavy at key strike acting as support
    if abs(key_put_gex) > abs(key_call_gex) * 1.5 and key_put_oi > key_call_oi:
        return "PUT_PILLAR"

    # CALL_WALL: call-heavy at key strike acting as resistance
    if abs(key_call_gex) > abs(key_put_gex) * 1.5 and key_call_oi > key_put_oi:
        return "CALL_WALL"

    # POS_GAMMA: positive/stable gamma environment
    if net_gex > 0 and sentiment > 55:
        return "POS_GAMMA"

    return "STAY_OUT"


def _generate_trade_signal(snap: dict, prev_snap: dict | None, prev_signal: dict | None) -> dict:
    """Generate a structured trade signal for one snapshot using GEX teaching rules.

    Returns a dict with: setup_type, action, structure, short_strike, wing_strike,
    short_strike2, wing_strike2, rationale, invalidation, caution, prev_outcome
    """
    setup_type  = _classify_gex_setup(snap)
    net_gex     = snap.get("net_gex", 0) or 0
    key_strike  = snap.get("key_strike") or 0
    key2_strike = snap.get("key2_strike") or 0
    uprice      = snap.get("uprice", 0) or 0
    flip        = snap.get("flip")
    kcs         = snap.get("kcs", 0) or 0
    sentiment   = snap.get("sentiment_pct", snap.get("sentiment", 50)) or 50
    hmm_label   = snap.get("hmm_label", "") or ""
    key_dominance = snap.get("key_dominance_pct", snap.get("dominance", 0)) or 0
    
    # Get feedback loop features for signal filtering
    ndate = snap.get("ndate")
    ntime = snap.get("ntime")
    feedback_features = _get_feedback_features(ndate, ntime) if ndate and ntime else {}
    
    # Apply feedback loop filtering
    if feedback_features:
        setup_type = _filter_signal_with_feedback(setup_type, feedback_features, snap)

    WING = 10  # default wing width in SPX points

    action = "STAY_OUT"
    structure = None
    short_strike = None
    wing_strike = None
    short_strike2 = None
    wing_strike2 = None
    rationale = ""
    invalidation = ""
    caution = ""

    if setup_type == "PIN":
        action = "IRON_BUTTERFLY"
        structure = "Short Iron Butterfly"
        short_strike = key_strike
        wing_strike = key_strike + WING
        short_strike2 = key_strike
        wing_strike2 = key_strike - WING
        rationale = (
            f"PIN setup: balanced call/put GEX at {key_strike} with KCS={kcs:.1f}. "
            f"Price ({uprice:.0f}) near key strike. Iron butterfly profits if price pins at {key_strike} at expiry. "
            f"Entry: wait for price to stretch slightly beyond {key_strike} then enter on reversion."
        )
        invalidation = (
            f"Thesis fails if price breaks and holds beyond {key_strike + WING} (call side) or "
            f"{key_strike - WING} (put side) with momentum. Also fails if KCS drops sharply intraday."
        )
        caution = (
            f"Check tomorrow's GEX — pin thesis only valid if key_strike is the same tomorrow. "
            f"Charm decay accelerates after midday. Regime: {hmm_label}."
        )

    elif setup_type == "PUT_PILLAR":
        action = "SHORT_PUT_SPREAD"
        structure = "Short Put Spread"
        short_strike = key_strike
        wing_strike = key_strike - WING
        rationale = (
            f"PUT_PILLAR: Put-heavy GEX at {key_strike} with strong put OI. "
            f"Level may act as support. Sell put spread at/just below pillar. "
            f"Entry: wait for price to touch or briefly break below {key_strike} then enter on rebound."
        )
        invalidation = (
            f"Pillar fails if price breaks {key_strike} with momentum and closes below. "
            f"Negative gamma acceleration below {key2_strike if key2_strike else key_strike - 20} would signal cascade risk."
        )
        caution = f"OI alone cannot confirm direction. Volume at {key_strike} must confirm. Regime: {hmm_label}."

    elif setup_type == "CALL_WALL":
        action = "SHORT_CALL_SPREAD"
        structure = "Short Call Spread"
        short_strike = key_strike
        wing_strike = key_strike + WING
        rationale = (
            f"CALL_WALL: Call-heavy GEX at {key_strike} may act as resistance. "
            f"Sell call spread at/just above wall. "
            f"Entry: wait for price to touch or briefly break above {key_strike} then enter on rejection."
        )
        invalidation = (
            f"Wall fails if price breaks {key_strike} on strong volume and holds above. "
            f"Sentiment > 70 would suggest directional breakout rather than rejection."
        )
        caution = f"Call wall can break on macro catalyst. Check economic calendar. Regime: {hmm_label}."

    elif setup_type == "NEG_GAMMA":
        action = "STAY_OUT"
        structure = "No Trade"
        rationale = (
            f"NEG_GAMMA: Net GEX = {net_gex/1e9:.2f}B — strongly negative. "
            f"Market maker hedging may amplify moves. Do not sell premium into negative gamma. "
            f"Risk of cascade below {f'{flip:.0f}' if flip else 'flip point'}."
        )
        invalidation = "N/A — no trade."
        caution = "Avoid all short premium strategies until GEX turns positive or neutral."

    elif setup_type == "GEX_SLIDE":
        action = "STAY_OUT"
        structure = "No Trade"
        rationale = (
            f"GEX_SLIDE: Low key dominance ({key_dominance:.0f}%) and KCS={kcs:.1f}. "
            f"Gamma spread across many strikes. No clean anchor level. Movement may be fast and disjointed."
        )
        invalidation = "N/A — no trade."
        caution = "Wait for KCS > 12 and dominance > 10% before considering entries."

    elif setup_type == "POS_GAMMA":
        action = "STAY_OUT"
        structure = "Observe / Iron Condor"
        rationale = (
            f"POS_GAMMA: Net GEX = {net_gex/1e9:.2f}B positive, sentiment {sentiment:.0f}%. "
            f"Stabilising environment. Wider iron condor possible if key strike is clear, "
            f"but no strong single-level signal. Key strike: {key_strike}."
        )
        invalidation = f"Fails if net GEX turns negative or sentiment drops below 45%."
        caution = f"Positive gamma dampens moves — set tighter profit targets. Regime: {hmm_label}."

    else:  # STAY_OUT default
        action = "STAY_OUT"
        structure = "No Trade"
        rationale = "Insufficient GEX conviction or pre-market snapshot. No trade recommended."
        invalidation = "N/A"
        caution = "Wait for RTH open and clearer GEX setup."

    # Assess previous signal outcome
    prev_outcome = None
    if prev_signal and prev_snap:
        prev_action = prev_signal.get("action", "STAY_OUT")
        prev_short  = prev_signal.get("short_strike")
        prev_struct = prev_signal.get("structure", "No Trade")
        curr_uprice = uprice
        prev_uprice = prev_snap.get("uprice", uprice) or uprice

        if prev_action == "STAY_OUT":
            # Assess whether staying out was correct
            move = abs(curr_uprice - prev_uprice)
            if move > 15:
                prev_outcome = f"Previous signal: STAY_OUT — price moved {move:.0f}pts ({prev_uprice:.0f}→{curr_uprice:.0f}). Staying out avoided a {move:.0f}pt move."
            elif move < 5:
                prev_outcome = f"Previous signal: STAY_OUT — price was flat ({prev_uprice:.0f}→{curr_uprice:.0f}, {move:.0f}pts). Missed opportunity: iron condor/butterfly would have profited."
            else:
                prev_outcome = f"Previous signal: STAY_OUT — price moved {move:.0f}pts ({prev_uprice:.0f}→{curr_uprice:.0f}). Ambiguous — directional move but modest."
        elif prev_short:
            move_toward = None
            if prev_action == "SHORT_PUT_SPREAD":
                # Pillar held if price stayed above short_strike
                if curr_uprice >= prev_short:
                    prev_outcome = f"Previous PUT_PILLAR at {prev_short:.0f}: pillar held — price is {curr_uprice:.0f} (above {prev_short:.0f}). Spread likely profitable."
                else:
                    prev_outcome = f"Previous PUT_PILLAR at {prev_short:.0f}: pillar BROKE — price is {curr_uprice:.0f} (below {prev_short:.0f}). Spread at risk."
            elif prev_action == "SHORT_CALL_SPREAD":
                if curr_uprice <= prev_short:
                    prev_outcome = f"Previous CALL_WALL at {prev_short:.0f}: wall held — price is {curr_uprice:.0f} (below {prev_short:.0f}). Spread likely profitable."
                else:
                    prev_outcome = f"Previous CALL_WALL at {prev_short:.0f}: wall BROKE — price is {curr_uprice:.0f} (above {prev_short:.0f}). Spread at risk."
            elif prev_action == "IRON_BUTTERFLY":
                dist = abs(curr_uprice - prev_short)
                if dist <= 5:
                    prev_outcome = f"Previous PIN at {prev_short:.0f}: price pinning ({curr_uprice:.0f}, {dist:.0f}pts away). Iron butterfly performing well."
                elif dist <= WING:
                    prev_outcome = f"Previous PIN at {prev_short:.0f}: price drifted {dist:.0f}pts from pin ({curr_uprice:.0f}). Butterfly still intact but margin reduced."
                else:
                    prev_outcome = f"Previous PIN at {prev_short:.0f}: price moved {dist:.0f}pts away ({curr_uprice:.0f}). Butterfly likely at or near max loss."
            else:
                prev_outcome = f"Previous signal: {prev_struct} — price moved {prev_uprice:.0f}→{curr_uprice:.0f}."

    # Get RF prediction
    rf_pred = _predict_rf_outcome(snap)
    
    # Hybrid decision: override rule-based action if RF predicts LOSS
    rule_based_action = action
    rule_based_structure = structure
    rf_override = False
    
    if rf_pred.get('available') and action != "STAY_OUT":
        if rf_pred['prediction'] == "LOSS":
            # Override to STAY_OUT when RF predicts loss
            action = "STAY_OUT"
            structure = "No Trade (RF Override)"
            rf_override = True
            # Update rationale to explain override
            original_rationale = rationale
            rationale = (
                f"RF Override: Rule-based signal was {rule_based_action} ({rule_based_structure}), "
                f"but Random Forest predicts LOSS (probability {rf_pred['probability']:.2%}). "
                f"Skipping trade to avoid predicted loss."
            )
            invalidation = "N/A — trade skipped due to RF override."
            caution = f"Original rule-based rationale: {original_rationale}"

    return {
        "setup_type":    setup_type,
        "action":        action,
        "structure":     structure,
        "short_strike":  short_strike,
        "wing_strike":   wing_strike,
        "short_strike2": short_strike2,
        "wing_strike2":  wing_strike2,
        "rationale":     rationale,
        "invalidation":  invalidation,
        "caution":       caution,
        "prev_outcome":  prev_outcome,
        "regime":        hmm_label,
        "rf_prediction": rf_pred,
        "rf_override":   rf_override,
        "rule_based_action": rule_based_action,
    }


def _persist_trade_signal(ndate: int, ntime: int, signal: dict, next_spx: float = None, next_ntime: int = None, outcome: str = None, outcome_points: float = None) -> None:
    """Save a trade signal to the trade_signals table."""
    from datetime import datetime
    ts = datetime.utcnow().isoformat()
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO trade_signals "
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


def _generate_daily_narrative(date_iso: str) -> str:
    """Generate a rule-based trading narrative for a given date.

    Walks through snapshots chronologically, applies trading rules,
    and generates a narrative that reads like a trading diary.
    """
    from datetime import datetime

    ndate = int(date_iso.replace("-", ""))

    # Get all snapshots for this day in chronological order
    with _db() as con:
        rows = con.execute(
            "SELECT ntime FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
            (ndate,)
        ).fetchall()

    if not rows:
        return "No snapshots available for this date."

    ntimes = [r[0] for r in rows]

    # Load snapshots and summarize
    snapshots = []
    for ntime in ntimes:
        data = load_gex_snapshot(date_iso, ntime)
        if data:
            snap = summarise_snapshot(data)
            if snap.get("uprice"):
                snapshots.append({"ntime": ntime, "snap": snap})

    if not snapshots:
        return "No valid snapshots available for this date."

    # Generate narrative
    narrative_lines = []
    narrative_lines.append(f"# Trading Diary - {date_iso}\n")

    # Track state
    current_position = None  # "long", "short", or None
    entry_price = None
    entry_time = None
    entry_reason = None
    trades = []

    # Morning setup (first RTH snapshot)
    rth_snaps = [s for s in snapshots if s["ntime"] >= 935]
    if rth_snaps:
        first = rth_snaps[0]
        s = first["snap"]
        narrative_lines.append("## Morning Setup\n")
        narrative_lines.append(f"**Time:** {fmtTime(first['ntime'])}\n")
        narrative_lines.append(f"**SPX:** {s['uprice']:.2f}\n")
        narrative_lines.append(f"**Net GEX:** {fmtBig(s.get('net_gex', 0))}\n")
        narrative_lines.append(f"**Regime:** {s.get('hmm_label', 'N/A')}\n")
        narrative_lines.append(f"**Key Strike:** {s.get('key_strike', 'N/A')}\n")
        narrative_lines.append(f"**Flip:** {s.get('flip', 'N/A')}\n")
        narrative_lines.append(f"**KCS:** {s.get('kcs', 0):.1f}\n")
        narrative_lines.append(f"**Sentiment:** {s.get('sentiment_pct', 0):.0f}%\n")

        # Morning thesis
        narrative_lines.append("\n**Thesis:**\n")
        if s.get('net_gex', 0) < 0:
            narrative_lines.append("Negative GEX environment. Looking for short opportunities below the flip point with put wall support.\n")
        else:
            narrative_lines.append("Positive GEX environment. Looking for long opportunities above the flip point with call wall support.\n")

        # Regime context
        regime = s.get('hmm_label', '')
        if 'Positive Stable' in regime:
            narrative_lines.append("Regime suggests stable bullish conditions. Favor long entries with tight stops.\n")
        elif 'Negative Volatile' in regime:
            narrative_lines.append("Regime suggests volatile bearish conditions. Favor short entries with wider stops.\n")
        elif 'Positive Weakening' in regime:
            narrative_lines.append("Regime suggests weakening bullish conditions. Be selective with long entries, watch for reversal.\n")
        elif 'Negative Trending' in regime:
            narrative_lines.append("Regime suggests bearish trend. Favor short entries on rallies.\n")

        # Initial trade decision
        narrative_lines.append("\n**Initial Trade Decision:**\n")
        if s.get('net_gex', 0) < -10_000_000_000:  # Strongly negative
            narrative_lines.append("Strong negative GEX. Entering short position below flip point.\n")
            current_position = "short"
            entry_price = s['uprice']
            entry_time = first['ntime']
            entry_reason = "Strong negative GEX"
        elif s.get('net_gex', 0) > 10_000_000_000:  # Strongly positive
            narrative_lines.append("Strong positive GEX. Entering long position above flip point.\n")
            current_position = "long"
            entry_price = s['uprice']
            entry_time = first['ntime']
            entry_reason = "Strong positive GEX"
        else:
            narrative_lines.append("Mixed GEX signal. No initial position. Waiting for clearer setup.\n")

    # Intraday updates
    narrative_lines.append("\n## Intraday Updates\n")
    for i, snap_data in enumerate(rth_snaps[1:], 1):
        prev = rth_snaps[i-1]
        curr = snap_data
        s = curr["snap"]
        prev_s = prev["snap"]

        price_change = s['uprice'] - prev_s['uprice']
        narrative_lines.append(f"\n### {fmtTime(curr['ntime'])}\n")
        narrative_lines.append(f"SPX: {s['uprice']:.2f} ({price_change:+.2f})\n")
        narrative_lines.append(f"Net GEX: {fmtBig(s.get('net_gex', 0))}\n")
        narrative_lines.append(f"Regime: {s.get('hmm_label', 'N/A')}\n")

        # Review previous trade
        if current_position:
            pnl = 0
            if current_position == "long":
                pnl = s['uprice'] - entry_price
            else:
                pnl = entry_price - s['uprice']

            narrative_lines.append(f"**Position Review:** {current_position.upper()} @ {entry_price:.2f}, PnL: {pnl:+.2f}\n")

            # Exit rules
            exit_triggered = False
            if current_position == "long" and s.get('net_gex', 0) < 0:
                narrative_lines.append("GEX turned negative. Exiting long position.\n")
                trades.append({"direction": "long", "entry": entry_price, "exit": s['uprice'], "pnl": pnl, "reason": "GEX turn negative"})
                current_position = None
                entry_price = None
                exit_triggered = True
            elif current_position == "short" and s.get('net_gex', 0) > 0:
                narrative_lines.append("GEX turned positive. Exiting short position.\n")
                trades.append({"direction": "short", "entry": entry_price, "exit": s['uprice'], "pnl": pnl, "reason": "GEX turn positive"})
                current_position = None
                entry_price = None
                exit_triggered = True
            elif pnl < -15:  # Stop loss
                narrative_lines.append("Stop loss hit. Exiting position.\n")
                trades.append({"direction": current_position, "entry": entry_price, "exit": s['uprice'], "pnl": pnl, "reason": "Stop loss"})
                current_position = None
                entry_price = None
                exit_triggered = True
            elif pnl > 30:  # Take profit
                narrative_lines.append("Target reached. Taking profit.\n")
                trades.append({"direction": current_position, "entry": entry_price, "exit": s['uprice'], "pnl": pnl, "reason": "Take profit"})
                current_position = None
                entry_price = None
                exit_triggered = True

            if not exit_triggered:
                narrative_lines.append("Holding position. No exit signal.\n")
        else:
            narrative_lines.append("**Position:** Flat\n")

            # Entry rules
            flip_val = s.get('flip')
            if s.get('net_gex', 0) < -10_000_000_000 and (flip_val is None or s['uprice'] < flip_val):
                narrative_lines.append("Short signal: Negative GEX below flip. Entering short.\n")
                current_position = "short"
                entry_price = s['uprice']
                entry_time = curr['ntime']
                entry_reason = "Negative GEX below flip"
            elif s.get('net_gex', 0) > 10_000_000_000 and (flip_val is None or s['uprice'] > flip_val):
                narrative_lines.append("Long signal: Positive GEX above flip. Entering long.\n")
                current_position = "long"
                entry_price = s['uprice']
                entry_time = curr['ntime']
                entry_reason = "Positive GEX above flip"

    # EOD review
    narrative_lines.append("\n## End-of-Day Review\n")
    if rth_snaps:
        last = rth_snaps[-1]
        s = last["snap"]
        narrative_lines.append(f"**Close:** {s['uprice']:.2f}\n")
        narrative_lines.append(f"**Final Net GEX:** {fmtBig(s.get('net_gex', 0))}\n")
        narrative_lines.append(f"**Final Regime:** {s.get('hmm_label', 'N/A')}\n")

    # Trade summary
    narrative_lines.append("\n**Trade Summary:**\n")
    if trades:
        total_pnl = sum(t['pnl'] for t in trades)
        win_count = sum(1 for t in trades if t['pnl'] > 0)
        narrative_lines.append(f"Total Trades: {len(trades)}\n")
        narrative_lines.append(f"Win Rate: {win_count/len(trades)*100:.1f}%\n")
        narrative_lines.append(f"Total PnL: {total_pnl:+.2f} points\n")
        narrative_lines.append("\n**Individual Trades:**\n")
        for i, t in enumerate(trades, 1):
            narrative_lines.append(f"{i}. {t['direction'].upper()} {t['entry']:.2f} → {t['exit']:.2f} ({t['pnl']:+.2f}) - {t['reason']}\n")
    else:
        narrative_lines.append("No trades executed today.\n")

    # Lessons learned
    narrative_lines.append("\n**Key Observations:**\n")
    if rth_snaps:
        first_gex = rth_snaps[0]['snap'].get('net_gex', 0)
        last_gex = rth_snaps[-1]['snap'].get('net_gex', 0)
        if first_gex < 0 and last_gex < 0:
            narrative_lines.append("GEX remained negative throughout the day. Short bias was correct.\n")
        elif first_gex > 0 and last_gex > 0:
            narrative_lines.append("GEX remained positive throughout the day. Long bias was correct.\n")
        elif first_gex < 0 and last_gex > 0:
            narrative_lines.append("GEX flipped from negative to positive. Trend reversal occurred.\n")
        elif first_gex > 0 and last_gex < 0:
            narrative_lines.append("GEX flipped from positive to negative. Trend reversal occurred.\n")

    return "\n".join(narrative_lines)


def _ensure_percentile_history_table() -> None:
    """Create the percentile_history table for time-slot specific percentiles."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS percentile_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                metric_name     TEXT NOT NULL,
                value           REAL NOT NULL,
                percentile      REAL NOT NULL,
                UNIQUE(ndate, ntime, metric_name)
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_percentile_history_metric "
            "ON percentile_history (metric_name, ndate, ntime)"
        )


def _populate_percentile_history() -> dict:
    """Pre-compute time-slot percentiles for all historical snapshots.

    For each snapshot, calculate percentile rank against all snapshots at the same ntime.
    Returns stats about the population run.
    """
    import json
    with _db() as con:
        # Get all distinct (ndate, ntime) pairs from snapshot
        pairs = con.execute(
            "SELECT DISTINCT ndate, ntime FROM snapshot WHERE symbol='SPX' ORDER BY ndate, ntime"
        ).fetchall()
        if not pairs:
            return {"status": "no_data", "snapshots": 0}

        # Group by ntime to build time-slot distributions
        by_ntime = {}
        for ndate, ntime in pairs:
            if ntime not in by_ntime:
                by_ntime[ntime] = []
            by_ntime[ntime].append(ndate)

        # For each time slot, compute distributions for all metrics
        populated = 0
        for ntime, dates in by_ntime.items():
            # Load all snapshots for this time slot
            slot_values = {}
            for ndate in dates:
                date_iso = f"{str(ndate)[:4]}-{str(ndate)[4:6]}-{str(ndate)[6:]}"
                data = load_gex_snapshot(date_iso, ntime)
                if not data:
                    continue
                snap = summarise_snapshot(data)
                if not snap.get("uprice"):
                    continue

                # Map to metric names
                metrics = {
                    "spx_last": snap.get("uprice"),
                    "sentiment_pct": snap.get("sentiment_pct"),
                    "gex_ratio": snap.get("gex_ratio"),
                    "net_gex": snap.get("net_gex"),
                    "kcs": snap.get("kcs"),
                    "total_call_gex": snap.get("call_gex"),
                    "total_put_gex": snap.get("put_gex"),
                    "key_strike": snap.get("key_strike"),
                    "key_call_gex": snap.get("key_call_gex"),
                    "key_put_gex": snap.get("key_put_gex"),
                    "total_call_oi": snap.get("total_call_oi"),
                    "total_put_oi": snap.get("total_put_oi"),
                    "key_call_oi": snap.get("key_call_oi"),
                    "key_put_oi": snap.get("key_put_oi"),
                    "total_call_vol": snap.get("total_call_vol"),
                    "total_put_vol": snap.get("total_put_vol"),
                    "key_call_vol": snap.get("key_call_vol"),
                    "key_put_vol": snap.get("key_put_vol"),
                    "key2_strike": snap.get("key2_strike"),
                    "key2_abs": snap.get("key2_abs"),
                    "key2_call_vol": snap.get("key2_call_vol"),
                    "key2_put_vol": snap.get("key2_put_vol"),
                    "flip": snap.get("flip"),
                }

                for metric_name, value in metrics.items():
                    if value is not None:
                        if metric_name not in slot_values:
                            slot_values[metric_name] = []
                        slot_values[metric_name].append((ndate, value))

            # Compute percentiles for this time slot
            for metric_name, values in slot_values.items():
                sorted_vals = sorted([v for _, v in values])
                for ndate, value in values:
                    # Calculate percentile rank
                    rank = sum(1 for v in sorted_vals if v <= value)
                    percentile = round(rank / len(sorted_vals) * 100, 1)
                    con.execute(
                        "INSERT OR REPLACE INTO percentile_history (ndate, ntime, metric_name, value, percentile) VALUES (?, ?, ?, ?, ?)",
                        (ndate, ntime, metric_name, value, percentile)
                    )
                    populated += 1

        return {"status": "populated", "snapshots": len(pairs), "metrics": populated}


def _ensure_metric_history_table() -> None:
    """Create the metric_history table for histogram data."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS metric_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ndate           INTEGER NOT NULL,
                metric_name     TEXT NOT NULL,
                value           REAL NOT NULL,
                UNIQUE(ndate, metric_name)
            )
        """)
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_metric_history_metric "
            "ON metric_history (metric_name, ndate)"
        )


def _populate_metric_history() -> dict:
    """Populate metric_history with EOD values from snapshot flat columns.

    Returns stats about the population run.
    """
    with _db() as con:
        # Get the last RTH snapshot per date (skip pre-market-only days)
        rows = con.execute(
            "SELECT ndate, MAX(ntime) FROM snapshot "
            "WHERE symbol='SPX' AND ntime>=930 AND net_gex IS NOT NULL "
            "GROUP BY ndate ORDER BY ndate"
        ).fetchall()
        if not rows:
            return {"status": "no_data", "dates": 0}

        populated = 0
        for ndate, last_ntime in rows:
            row = con.execute(
                "SELECT uprice, sentiment, gex_ratio, net_gex, kcs, "
                "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip "
                "FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'",
                (ndate, last_ntime)
            ).fetchone()
            if not row:
                continue

            (uprice, sentiment, gex_ratio, net_gex, kcs,
             total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
             total_call_oi, total_put_oi, key_call_oi, key_put_oi,
             total_call_vol, total_put_vol, key_call_vol, key_put_vol,
             key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip) = row

            metrics = {
                "spx_last": uprice,
                "sentiment_pct": sentiment,
                "gex_ratio": gex_ratio,
                "net_gex": net_gex,
                "kcs": kcs,
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
                "key2_strike": key2_strike,
                "key2_abs": key2_abs,
                "key2_call_vol": key2_call_vol,
                "key2_put_vol": key2_put_vol,
                "flip": flip,
            }

            for metric_name, value in metrics.items():
                if value is not None:
                    con.execute(
                        "INSERT OR REPLACE INTO metric_history (ndate, metric_name, value) VALUES (?, ?, ?)",
                        (ndate, metric_name, value)
                    )
                    populated += 1

        return {"status": "populated", "dates": len(rows), "metrics": populated}


def _ensure_snapshot_premarket() -> None:
    """Add is_premarket and source columns to snapshot if missing; back-fill values."""
    with _db() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(snapshot)").fetchall()]
        if "is_premarket" not in cols:
            con.execute("ALTER TABLE snapshot ADD COLUMN is_premarket INTEGER NOT NULL DEFAULT 0")
            con.execute("UPDATE snapshot SET is_premarket=1 WHERE ntime < 935")
        if "source" not in cols:
            con.execute("ALTER TABLE snapshot ADD COLUMN source TEXT NOT NULL DEFAULT 'histgex'")


GEX_SNAPSHOTS_SUMMARY_COLS = [
    ("sentiment", "REAL"),
    ("gex_ratio", "REAL"),
    ("net_gex", "REAL"),
    ("kcs", "REAL"),
    ("dominance", "REAL"),
    ("total_call_gex", "REAL"),
    ("total_put_gex", "REAL"),
    ("key_strike", "REAL"),
    ("key_call_gex", "REAL"),
    ("key_put_gex", "REAL"),
    ("total_call_oi", "INTEGER"),
    ("total_put_oi", "INTEGER"),
    ("key_call_oi", "INTEGER"),
    ("key_put_oi", "INTEGER"),
    ("total_call_vol", "INTEGER"),
    ("total_put_vol", "INTEGER"),
    ("key_call_vol", "INTEGER"),
    ("key_put_vol", "INTEGER"),
    ("key2_strike", "REAL"),
    ("key2_abs", "REAL"),
    ("key2_call_vol", "INTEGER"),
    ("key2_put_vol", "INTEGER"),
    ("flip", "REAL"),
    ("hmm_state", "INTEGER"),
    ("hmm_label", "TEXT"),
    ("raw_json", "TEXT"),
]


def _ensure_snapshot_summary_columns() -> None:
    """Add flat summary columns to snapshot so historical rows match snapshot."""
    with _db() as con:
        existing = {r[1] for r in con.execute("PRAGMA table_info(snapshot)").fetchall()}
        for col, dtype in GEX_SNAPSHOTS_SUMMARY_COLS:
            if col not in existing:
                con.execute(f"ALTER TABLE snapshot ADD COLUMN {col} {dtype}")


def _drop_legacy_snapshots_table() -> None:
    """Remove the legacy 'snapshots' table left over from the pre-SQLite migration."""
    with _db() as con:
        con.execute("DROP TABLE IF EXISTS snapshots")


def _backfill_snapshot_summary(limit: int | None = None, force: bool = False) -> dict:
    """Compute and store flat summary columns for existing snapshot rows.

    Histgex rows are recomputed from the stored JSON; live_promoted rows are
    copied from the matching snapshot row.

    If limit is provided, only backfill that many rows (useful for quick tests).
    If force is True, re-backfill all rows (not just those with net_gex IS NULL).
    """
    import json
    updated = 0
    copied = 0
    with _db() as con:
        where_clause = "" if force else "WHERE symbol='SPX' AND net_gex IS NULL"
        rows = con.execute(
            f"SELECT ndate, ntime, uprice, raw_json, source FROM snapshot "
            f"{where_clause} "
            f"LIMIT {limit}" if limit is not None else ""
        ).fetchall()

    update_sql = """
        UPDATE snapshot SET
            sentiment=?, gex_ratio=?, net_gex=?, kcs=?, dominance=?,
            total_call_gex=?, total_put_gex=?, key_strike=?, key_call_gex=?, key_put_gex=?,
            total_call_oi=?, total_put_oi=?, key_call_oi=?, key_put_oi=?,
            total_call_vol=?, total_put_vol=?, key_call_vol=?, key_put_vol=?,
            key2_strike=?, key2_abs=?, key2_call_vol=?, key2_put_vol=?, flip=?,
            hmm_state=?, hmm_label=?, raw_json=?
        WHERE ndate=? AND ntime=? AND symbol='SPX'
    """

    for row in rows:
        ndate, ntime, uprice, data_json, source = row
        snap = None
        if data_json and data_json != "[]":
            try:
                parsed = json.loads(data_json)
                data_list = parsed.get("data") if isinstance(parsed, dict) else parsed
                snap = _compute_flat_summary({"uprice": uprice, "data": data_list})
            except Exception:
                snap = None
        elif source == "gex":
            with _db() as con:
                live = con.execute(
                    "SELECT uprice, sentiment, gex_ratio, net_gex, kcs, dominance, "
                    "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                    "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                    "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                    "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, "
                    "hmm_state, hmm_label, raw_json "
                    "FROM snapshot WHERE ndate=? AND ntime=?",
                    (ndate, ntime),
                ).fetchone()
            if live:
                snap = dict(live)
                snap["uprice"] = snap.pop("spx_last", uprice)
                snap["sentiment_pct"] = snap.pop("sentiment", None)
                snap["key_dominance_pct"] = snap.pop("dominance", None)
                copied += 1
        if not snap or snap.get("uprice") is None:
            continue

        with _db() as con:
            con.execute(
                update_sql,
                (
                    snap.get("sentiment_pct"), snap.get("gex_ratio"), snap.get("net_gex"),
                    snap.get("kcs"), snap.get("key_dominance_pct"),
                    snap.get("total_call_gex"), snap.get("total_put_gex"), snap.get("key_strike"),
                    snap.get("key_call_gex"), snap.get("key_put_gex"),
                    snap.get("total_call_oi"), snap.get("total_put_oi"),
                    snap.get("key_call_oi"), snap.get("key_put_oi"),
                    snap.get("total_call_vol"), snap.get("total_put_vol"),
                    snap.get("key_call_vol"), snap.get("key_put_vol"),
                    snap.get("key2_strike"), snap.get("key2_abs"),
                    snap.get("key2_call_vol"), snap.get("key2_put_vol"), snap.get("flip"),
                    snap.get("hmm_state"), snap.get("hmm_label"), data_json, ndate, ntime,
                ),
            )
        updated += 1

    return {"updated": updated, "copied": copied}


def _backfill_snapshot_gex_ratio() -> dict:
    """Recompute gex_ratio for all snapshot rows using the corrected formula."""
    from controllers.gex_calculations import calculate_gex_ratio
    
    updated = 0
    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, raw_json FROM snapshot WHERE raw_json IS NOT NULL"
        ).fetchall()

    for ndate, ntime, raw_json in rows:
        try:
            import json
            data = json.loads(raw_json)
            strikes = data.get("data", [])
            
            if strikes:
                # Use the corrected centralized calculation function
                gex_ratio = calculate_gex_ratio(strikes)
                
                with _db() as con:
                    con.execute(
                        "UPDATE snapshot SET gex_ratio=? WHERE ndate=? AND ntime=?",
                        (gex_ratio, ndate, ntime)
                    )
                updated += 1
        except Exception:
            # Skip rows that can't be processed
            continue

    return {"updated": updated}


def _backfill_snapshot_nulls() -> dict:
    """Set default values (0) for null computed columns in snapshot."""
    updated = 0
    with _db() as con:
        # Update null net_gex to 0
        updated += con.execute(
            "UPDATE snapshot SET net_gex=0 WHERE net_gex IS NULL"
        ).rowcount
        # Update null sentiment to 50
        updated += con.execute(
            "UPDATE snapshot SET sentiment=50 WHERE sentiment IS NULL"
        ).rowcount
        # Update null gex_ratio to 0
        updated += con.execute(
            "UPDATE snapshot SET gex_ratio=0 WHERE gex_ratio IS NULL"
        ).rowcount
        # Update null kcs to 0
        updated += con.execute(
            "UPDATE snapshot SET kcs=0 WHERE kcs IS NULL"
        ).rowcount
        # Update null dominance to 0
        updated += con.execute(
            "UPDATE snapshot SET dominance=0 WHERE dominance IS NULL"
        ).rowcount
    return {"updated": updated}


def _backfill_snapshot_nulls() -> dict:
    """Set default values (0) for null computed columns in snapshot."""
    updated = 0
    with _db() as con:
        # Update null net_gex to 0
        updated += con.execute(
            "UPDATE snapshot SET net_gex=0 WHERE net_gex IS NULL"
        ).rowcount
        # Update null sentiment to 50
        updated += con.execute(
            "UPDATE snapshot SET sentiment=50 WHERE sentiment IS NULL"
        ).rowcount
        # Update null gex_ratio to 0
        updated += con.execute(
            "UPDATE snapshot SET gex_ratio=0 WHERE gex_ratio IS NULL"
        ).rowcount
        # Update null kcs to 0
        updated += con.execute(
            "UPDATE snapshot SET kcs=0 WHERE kcs IS NULL"
        ).rowcount
        # Update null dominance to 0
        updated += con.execute(
            "UPDATE snapshot SET dominance=0 WHERE dominance IS NULL"
        ).rowcount
    return {"updated": updated}


def _backfill_hmm_labels_for_snapshot(only_null: bool = False) -> dict:
    """Run HMM sequence prediction for historical dates and store labels.

    Only updates RTH snapshots (ntime >= 935). Pre-market rows keep hmm_label=NULL.

    If only_null=True, only dates with at least one RTH row lacking a label are
    processed, which is useful for filling labels after new snapshots are added
    without retraining the model.
    """
    import json
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_net_gex,
        calculate_kcs,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
    )
    
    with _db() as con:
        if only_null:
            dates = [r[0] for r in con.execute(
                "SELECT DISTINCT ndate FROM gex_strike_window "
                "WHERE symbol='SPX' AND source='gex' AND ntime>=935 AND hmm_label IS NULL ORDER BY ndate"
            ).fetchall()]
        else:
            dates = [r[0] for r in con.execute(
                "SELECT DISTINCT ndate FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND ntime>=935 ORDER BY ndate"
            ).fetchall()]
    updated = 0
    for ndate in dates:
        with _db() as con:
            rows = con.execute(
                "SELECT ntime, price, data "
                "FROM gex_strike_window WHERE ndate=? AND symbol='SPX' AND source='gex' AND ntime>=935 ORDER BY ntime",
                (ndate,),
            ).fetchall()
        snaps = []
        for ntime, uprice, data_json in rows:
            if not uprice or not data_json:
                continue
            try:
                strikes = json.loads(data_json)
            except:
                continue
            if not strikes:
                continue
            
            # Calculate HMM features using gex_calculations module
            sentiment = calculate_sentiment(strikes)
            net_gex = calculate_net_gex(strikes)
            kcs = calculate_kcs(strikes, uprice)
            key_stats = calculate_key_strike_stats(strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(strikes)
            
            snaps.append({
                "uprice": uprice,
                "net_gex": net_gex,
                "kcs": kcs,
                "sentiment_pct": sentiment,
                "key_strike": key_stats["key_strike"],
                "total_put_vol": total_oi_vol["total_put_vol"],
            })
        
        if not snaps:
            continue
        hmm_results = predict_hmm_sequence(snaps)
        for (ntime, *_), hmm in zip(rows, hmm_results):
            state = hmm.get("state")
            label = hmm.get("label")
            with _db() as con:
                con.execute(
                    "UPDATE gex_strike_window SET hmm_state=?, hmm_label=? "
                    "WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'",
                    (state, label, ndate, ntime),
                )
            updated += 1
    return {"updated": updated}


def _promote_live_to_historical() -> dict:
    """Promote prior-day snapshot rows into snapshot at server startup.

    Any snapshot row whose ndate < today (ET) that does not already exist
    in snapshot is inserted with source='live_promoted'.
    All flat summary columns are copied from snapshot so the historical tab
    renders identical values to the live tab.
    Returns {"promoted": N, "skipped": N}.
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt
    today_ndate = int(_dt.now(ZoneInfo("America/New_York")).strftime("%Y%m%d"))
    promoted = 0
    skipped = 0
    try:
        with _db() as con:
            rows = con.execute(
                "SELECT ndate, ntime, uprice, sentiment, gex_ratio, net_gex, kcs, dominance, "
                "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, "
                "hmm_state, hmm_label, raw_json "
                "FROM snapshot WHERE ndate < ? ORDER BY ndate, ntime",
                (today_ndate,),
            ).fetchall()
        for row in rows:
            (ndate, ntime, spx_last, sentiment, gex_ratio, net_gex, kcs, dominance,
             total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
             total_call_oi, total_put_oi, key_call_oi, key_put_oi,
             total_call_vol, total_put_vol, key_call_vol, key_put_vol,
             key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
             hmm_state, hmm_label, raw_json) = row
            with _db() as con:
                exists = con.execute(
                    "SELECT 1 FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'",
                    (ndate, ntime),
                ).fetchone()
            if exists:
                skipped += 1
                continue
            # Live-promoted rows keep data as empty JSON list; the flat columns are the source of truth.
            with _db() as con:
                con.execute(
                    "INSERT OR IGNORE INTO snapshot "
                    "(ndate, ntime, symbol, uprice, data, is_premarket, source, "
                    "sentiment, gex_ratio, net_gex, kcs, dominance, "
                    "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                    "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                    "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                    "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, "
                    "hmm_state, hmm_label, raw_json) "
                    "VALUES (?, ?, 'SPX', ?, '[]', ?, 'gex', "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ndate, ntime, spx_last or 0, 1 if ntime < 935 else 0,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                     hmm_state, hmm_label, raw_json),
                )
            promoted += 1
    except Exception as e:
        print(f"[WARNING] _promote_live_to_historical failed: {e}")
    if promoted:
        print(f"[INFO] Promoted {promoted} prior-day live snapshots to historical (skipped {skipped})")
    return {"promoted": promoted, "skipped": skipped}


def _ensure_spx_ohlc_table() -> None:
    """Create spx_ohlc_5min table if it does not exist."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS spx_ohlc_5min (
                ndate INTEGER NOT NULL,
                ntime INTEGER NOT NULL,
                open  REAL,
                high  REAL,
                low   REAL,
                close REAL,
                PRIMARY KEY (ndate, ntime)
            )
        """)


def _update_spx_ohlc_from_yfinance() -> dict:
    """Fetch missing SPX 5-min bars from yfinance and append to spx_ohlc_5min.

    Yahoo Finance provides up to 60 days of 5-min intraday data for ^GSPC.
    Only fetches bars for dates not already in the table.
    Returns a summary dict.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"status": "error", "reason": "yfinance not installed"}

    from datetime import datetime, timedelta, timezone

    with _db() as con:
        row = con.execute("SELECT MAX(ndate) FROM spx_ohlc_5min").fetchone()
    last_ndate = row[0] if row and row[0] else 20260101

    # Convert ndate to date string
    last_str = str(last_ndate)
    last_dt  = datetime(int(last_str[:4]), int(last_str[4:6]), int(last_str[6:8]))
    start_dt = last_dt + timedelta(days=1)
    end_dt   = datetime.now() + timedelta(days=1)

    if start_dt.date() >= end_dt.date():
        return {"status": "skipped", "reason": "already up to date", "last_date": last_ndate}

    try:
        ticker = yf.Ticker("^GSPC")
        df = ticker.history(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            interval="5m",
            auto_adjust=True,
        )
    except Exception as e:
        return {"status": "error", "reason": str(e)}

    if df is None or df.empty:
        return {"status": "skipped", "reason": "no new data from yfinance"}

    rows = []
    for ts, row in df.iterrows():
        try:
            # Handle timezone-aware timestamps
            if hasattr(ts, "tz_localize"):
                dt = ts.to_pydatetime()
            else:
                dt = ts.to_pydatetime()
            ndate = int(dt.strftime("%Y%m%d"))
            ntime = dt.hour * 100 + dt.minute
            rows.append((ndate, ntime, float(row["Open"]), float(row["High"]),
                          float(row["Low"]), float(row["Close"])))
        except Exception:
            continue

    if not rows:
        return {"status": "skipped", "reason": "no parseable rows"}

    with _db() as con:
        con.executemany(
            "INSERT OR IGNORE INTO spx_ohlc_5min (ndate,ntime,open,high,low,close) VALUES (?,?,?,?,?,?)",
            rows
        )

    inserted = len(rows)
    new_dates = len(set(r[0] for r in rows))
    return {"status": "ok", "inserted": inserted, "new_dates": new_dates}


def _ensure_ml_labels_current() -> dict:
    """Append ml_labels rows for any dates that have GEX snapshots but no labels yet.

    Uses spx_ohlc_5min for precise OHLC. Skips today (labels not yet complete).
    Returns a summary dict.
    """
    import json, statistics
    from collections import defaultdict
    from datetime import datetime, date as ddate

    today_ndate = int(datetime.now().strftime("%Y%m%d"))

    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ml_labels (
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                spx_at_snap     REAL,
                spx_next        REAL,
                spx_eod         REAL,
                range_to_eod    REAL,
                move_to_next    REAL,
                move_to_eod     REAL,
                pct_to_next     REAL,
                pct_to_eod      REAL,
                direction_next  TEXT,
                direction_eod   TEXT,
                flip_level      REAL,
                flip_breached   INTEGER,
                range_regime    TEXT,
                hmm_label       TEXT,
                PRIMARY KEY (ndate, ntime)
            )
        """)

        # Find GEX snapshot dates that have no ml_labels yet (exclude today)
        missing = con.execute("""
            SELECT DISTINCT g.ndate FROM gex_strike_window g
            WHERE g.symbol='SPX' AND g.source='gex' AND g.ntime>=935
              AND g.ndate < ?
              AND NOT EXISTS (SELECT 1 FROM ml_labels m WHERE m.ndate=g.ndate)
            ORDER BY g.ndate
        """, (today_ndate,)).fetchall()

        if not missing:
            return {"status": "skipped", "reason": "ml_labels already current"}

        missing_dates = [r[0] for r in missing]

        # Load OHLC bars for those dates
        placeholders = ",".join("?" * len(missing_dates))
        bars_raw = con.execute(
            f"SELECT ndate, ntime, open, high, low, close FROM spx_ohlc_5min WHERE ndate IN ({placeholders}) ORDER BY ndate, ntime",
            missing_dates
        ).fetchall()

        bars_by_date = defaultdict(dict)
        for nd, nt, o, h, l, c in bars_raw:
            bars_by_date[nd][nt] = {"open": o, "high": h, "low": l, "close": c}

        # Load GEX snapshots for missing dates
        snaps = con.execute(
            f"SELECT ndate, ntime, price, data FROM gex_strike_window "
            f"WHERE symbol='SPX' AND source='gex' AND ntime>=935 AND ntime<=1555 "
            f"AND ndate IN ({placeholders}) ORDER BY ndate, ntime",
            missing_dates
        ).fetchall()

        # Flip level is always calculated on-the-fly from raw strike data in gex_strike_window
        flip_cache = {}

    # Compute 20-day rolling median range for range_regime
    with _db() as con:
        all_dates = [r[0] for r in con.execute(
            "SELECT DISTINCT ndate FROM spx_ohlc_5min ORDER BY ndate"
        ).fetchall()]
        date_ranges = {}
        for nd in all_dates:
            day_bars = con.execute(
                "SELECT high, low FROM spx_ohlc_5min WHERE ndate=? AND ntime>=935 AND ntime<=1600",
                (nd,)
            ).fetchall()
            if day_bars:
                date_ranges[nd] = max(r[0] for r in day_bars) - min(r[1] for r in day_bars)

    def range_regime_label(nd, rng):
        if not rng:
            return "NORMAL"
        idx = all_dates.index(nd) if nd in all_dates else 0
        window = [date_ranges[d] for d in all_dates[max(0, idx - 20):idx] if d in date_ranges]
        if not window:
            return "NORMAL"
        med = statistics.median(window)
        if rng < med * 0.7:
            return "TIGHT"
        elif rng > med * 1.4:
            return "WIDE"
        return "NORMAL"

    def next_bar_time(ntime):
        h, m = divmod(ntime, 100)
        m += 5
        if m >= 60:
            m -= 60
            h += 1
        return h * 100 + m

    def ntime_plus(ntime, minutes):
        h = ntime // 100
        m = ntime % 100 + minutes
        h += m // 60
        m  = m % 60
        return h * 100 + m

    def find_bar_close(day, target_ntime, tolerance=15):
        if target_ntime in day:
            return day[target_ntime]["close"]
        candidates = {t: v for t, v in day.items() if abs(t - target_ntime) <= tolerance}
        if not candidates:
            return None
        return candidates[min(candidates, key=lambda t: abs(t - target_ntime))]["close"]

    def bars_in_window(day, start_ntime, minutes):
        end_ntime = ntime_plus(start_ntime, minutes)
        return {t: v for t, v in day.items() if start_ntime <= t <= min(end_ntime, 1600)}

    def flip_held_in_window(window_bars, flip_level, spx_at_snap):
        if not flip_level or not window_bars:
            return None
        above = spx_at_snap >= flip_level
        for v in window_bars.values():
            if above and v["high"] < flip_level:
                return 0
            if not above and v["low"] > flip_level:
                return 0
        return 1

    def direction(pct, thresh):
        if pct is None:
            return None
        return "UP" if pct > thresh else ("DOWN" if pct < -thresh else "FLAT")

    def get_flip_from_strikes(strikes, uprice):
        if not strikes:
            return None
        sorted_s = sorted(strikes, key=lambda r: r.get("strike", 0))
        cum = 0
        prev_cum = None
        for s in sorted_s:
            net = s.get("net", 0) or 0
            if prev_cum is not None and ((prev_cum > 0 and cum + net <= 0) or (prev_cum < 0 and cum + net >= 0)):
                return s.get("strike")
            prev_cum = cum
            cum += net
        return None

    label_rows = []
    for ndate, ntime, uprice, data_json in snaps:
        if not uprice:
            continue
        try:
            strikes = json.loads(data_json) if data_json else []
        except Exception:
            strikes = []

        day = bars_by_date.get(ndate, {})
        if not day:
            # Fall back to using gex snapshot prices if no OHLC available
            continue

        # SPX at snapshot
        bar = day.get(ntime) or day.get(min(day.keys(), key=lambda t: abs(t - ntime), default=ntime))
        spx_at_snap = bar["close"] if bar else uprice

        # Next bar
        nb = next_bar_time(ntime)
        spx_next = day.get(nb, {}).get("close") or day.get(next_bar_time(nb), {}).get("close")

        # EOD price (last bar <= 1600)
        eod_bars = {t: v for t, v in day.items() if 1500 <= t <= 1600}
        spx_eod = eod_bars[max(eod_bars)]["close"] if eod_bars else None

        # Range from snapshot to EOD
        future_bars = {t: v for t, v in day.items() if t >= ntime and t <= 1600}
        range_to_eod = (
            max(v["high"] for v in future_bars.values()) - min(v["low"] for v in future_bars.values())
            if future_bars else None
        )

        move_to_next = (spx_next - spx_at_snap) if spx_next else None
        move_to_eod  = (spx_eod  - spx_at_snap) if spx_eod  else None
        pct_to_next  = round(move_to_next / spx_at_snap * 100, 4) if move_to_next and spx_at_snap else None
        pct_to_eod   = round(move_to_eod  / spx_at_snap * 100, 4) if move_to_eod  and spx_at_snap else None

        flip = flip_cache.get((ndate, ntime)) or get_flip_from_strikes(strikes, uprice)
        flip_breached = None
        if flip and future_bars:
            highs = [v["high"] for v in future_bars.values()]
            lows  = [v["low"]  for v in future_bars.values()]
            flip_breached = 1 if (min(lows) <= flip <= max(highs)) else 0

        rr = range_regime_label(ndate, range_to_eod)

        # Multi-horizon outcomes
        w1 = bars_in_window(day, ntime, 60)
        w2 = bars_in_window(day, ntime, 120)
        spx_1hr = find_bar_close(day, ntime_plus(ntime, 60))
        spx_2hr = find_bar_close(day, ntime_plus(ntime, 120))
        pct_1hr = round((spx_1hr - spx_at_snap) / spx_at_snap * 100, 4) if spx_1hr else None
        pct_2hr = round((spx_2hr - spx_at_snap) / spx_at_snap * 100, 4) if spx_2hr else None
        range_1hr = (max(v["high"] for v in w1.values()) - min(v["low"] for v in w1.values())) if w1 else None
        range_2hr = (max(v["high"] for v in w2.values()) - min(v["low"] for v in w2.values())) if w2 else None
        fh1 = flip_held_in_window(w1, flip, spx_at_snap)
        fh2 = flip_held_in_window(w2, flip, spx_at_snap)

        # Trade viability flags (2hr horizon)
        IC_THRESH = 30.0
        tv_ic  = (1 if range_2hr is not None and range_2hr < IC_THRESH and fh2 == 1 else 0) if range_2hr is not None else None
        tv_sps = (1 if pct_2hr is not None and pct_2hr >  0.10 else 0) if pct_2hr is not None else None
        tv_scs = (1 if pct_2hr is not None and pct_2hr < -0.10 else 0) if pct_2hr is not None else None
        tv_lcs = (1 if pct_2hr is not None and pct_2hr >  0.35 else 0) if pct_2hr is not None else None
        tv_lps = (1 if pct_2hr is not None and pct_2hr < -0.35 else 0) if pct_2hr is not None else None

        label_rows.append((
            ndate, ntime, spx_at_snap, spx_next, spx_eod,
            range_to_eod, move_to_next, move_to_eod,
            pct_to_next, pct_to_eod,
            direction(pct_to_next, 0.10), direction(pct_to_eod, 0.20),
            flip, flip_breached, rr, None,
            pct_1hr, pct_2hr, range_1hr, range_2hr,
            direction(pct_1hr, 0.15), direction(pct_2hr, 0.20),
            fh1, fh2, tv_ic, tv_sps, tv_scs, tv_lcs, tv_lps,
        ))

    if not label_rows:
        return {"status": "skipped", "reason": "no new labels to add"}

    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ml_labels (
                ndate INTEGER NOT NULL, ntime INTEGER NOT NULL,
                spx_at_snap REAL, spx_next REAL, spx_eod REAL,
                range_to_eod REAL, move_to_next REAL, move_to_eod REAL,
                pct_to_next REAL, pct_to_eod REAL,
                direction_next TEXT, direction_eod TEXT,
                flip_level REAL, flip_breached INTEGER,
                range_regime TEXT, hmm_label TEXT,
                pct_1hr REAL, pct_2hr REAL, range_1hr REAL, range_2hr REAL,
                direction_1hr TEXT, direction_2hr TEXT,
                flip_held_1hr INTEGER, flip_held_2hr INTEGER,
                trade_viable_ic INTEGER, trade_viable_sps INTEGER,
                trade_viable_scs INTEGER, trade_viable_lcs INTEGER,
                trade_viable_lps INTEGER,
                PRIMARY KEY (ndate, ntime)
            )
        """)
        # Ensure new columns exist on already-created tables
        existing_cols = {r[1] for r in con.execute("PRAGMA table_info(ml_labels)").fetchall()}
        for col, dtype in [
            ("pct_1hr","REAL"),("pct_2hr","REAL"),("range_1hr","REAL"),("range_2hr","REAL"),
            ("direction_1hr","TEXT"),("direction_2hr","TEXT"),
            ("flip_held_1hr","INTEGER"),("flip_held_2hr","INTEGER"),
            ("trade_viable_ic","INTEGER"),("trade_viable_sps","INTEGER"),
            ("trade_viable_scs","INTEGER"),("trade_viable_lcs","INTEGER"),
            ("trade_viable_lps","INTEGER"),
        ]:
            if col not in existing_cols:
                con.execute(f"ALTER TABLE ml_labels ADD COLUMN {col} {dtype}")
        con.executemany("""
            INSERT OR REPLACE INTO ml_labels
            (ndate, ntime, spx_at_snap, spx_next, spx_eod,
             range_to_eod, move_to_next, move_to_eod,
             pct_to_next, pct_to_eod, direction_next, direction_eod,
             flip_level, flip_breached, range_regime, hmm_label,
             pct_1hr, pct_2hr, range_1hr, range_2hr,
             direction_1hr, direction_2hr, flip_held_1hr, flip_held_2hr,
             trade_viable_ic, trade_viable_sps, trade_viable_scs,
             trade_viable_lcs, trade_viable_lps)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, label_rows)

    return {"status": "ok", "inserted": len(label_rows), "dates": len(missing_dates)}


def _ensure_ml_predictions_table() -> None:
    """Create ml_predictions table for storing real-time predictions and their outcomes."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ml_predictions (
                ndate               INTEGER NOT NULL,
                ntime               INTEGER NOT NULL,
                predicted_at        TEXT NOT NULL,
                vol_regime_pred     TEXT,
                vol_regime_proba    REAL,
                direction_pred      TEXT,
                direction_proba     REAL,
                trade_pred          TEXT,
                trade_code          TEXT,
                confidence          TEXT,
                -- Actuals filled in by _backfill_prediction_outcomes()
                vol_regime_actual   TEXT,
                direction_1hr_actual TEXT,
                direction_2hr_actual TEXT,
                direction_eod_actual TEXT,
                trade_viable_actual INTEGER,
                vol_correct         INTEGER,
                direction_1hr_correct INTEGER,
                direction_2hr_correct INTEGER,
                outcome_filled_at   TEXT,
                PRIMARY KEY (ndate, ntime)
            )
        """)


def _save_prediction(ndate, ntime, signal: dict) -> None:
    """Persist a real-time ML prediction to ml_predictions table."""
    if not signal or signal.get("error"):
        return
    from datetime import datetime as _dt
    predicted_at = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO ml_predictions
            (ndate, ntime, predicted_at, vol_regime_pred, vol_regime_proba,
             direction_pred, direction_proba, trade_pred, trade_code, confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (ndate, ntime, predicted_at,
              signal.get("vol_regime"), signal.get("vol_regime_proba"),
              signal.get("direction"), signal.get("direction_proba"),
              signal.get("trade"), signal.get("trade_code"),
              signal.get("confidence")))


def _backfill_prediction_outcomes() -> dict:
    """Match stored predictions to actual ml_labels outcomes.

    Run on startup after _ensure_ml_labels_current() so yesterday's
    predictions get their actuals filled in automatically.
    """
    from datetime import datetime as _dt
    with _db() as con:
        # Find predictions with no outcome yet, where labels now exist
        rows = con.execute("""
            SELECT p.ndate, p.ntime,
                   p.vol_regime_pred, p.direction_pred, p.trade_code,
                   l.range_regime, l.direction_1hr, l.direction_2hr, l.direction_eod,
                   l.trade_viable_ic, l.trade_viable_sps, l.trade_viable_scs,
                   l.trade_viable_lcs, l.trade_viable_lps
            FROM ml_predictions p
            JOIN ml_labels l ON l.ndate=p.ndate AND l.ntime=p.ntime
            WHERE p.outcome_filled_at IS NULL
        """).fetchall()

    if not rows:
        return {"status": "skipped", "reason": "no pending predictions to fill"}

    filled = 0
    now_str = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")

    _TRADE_VIABLE_MAP = {
        "IC":  "trade_viable_ic",
        "IB":  "trade_viable_ic",
        "SPS": "trade_viable_sps",
        "SCS": "trade_viable_scs",
        "LCS": "trade_viable_lcs",
        "LPS": "trade_viable_lps",
    }

    with _db() as con:
        for row in rows:
            (ndate, ntime, vol_pred, dir_pred, trade_code,
             vol_actual, dir_1hr, dir_2hr, dir_eod,
             tv_ic, tv_sps, tv_scs, tv_lcs, tv_lps) = row

            viable_col = _TRADE_VIABLE_MAP.get(trade_code)
            viable_map = {"trade_viable_ic": tv_ic, "trade_viable_sps": tv_sps,
                          "trade_viable_scs": tv_scs, "trade_viable_lcs": tv_lcs,
                          "trade_viable_lps": tv_lps}
            trade_viable = viable_map.get(viable_col) if viable_col else None

            vol_correct   = 1 if vol_pred == vol_actual else 0
            dir1_correct  = 1 if dir_pred == dir_1hr else 0
            dir2_correct  = 1 if dir_pred == dir_2hr else 0

            con.execute("""
                UPDATE ml_predictions SET
                    vol_regime_actual=?, direction_1hr_actual=?,
                    direction_2hr_actual=?, direction_eod_actual=?,
                    trade_viable_actual=?, vol_correct=?,
                    direction_1hr_correct=?, direction_2hr_correct=?,
                    outcome_filled_at=?
                WHERE ndate=? AND ntime=?
            """, (vol_actual, dir_1hr, dir_2hr, dir_eod,
                  trade_viable, vol_correct, dir1_correct, dir2_correct,
                  now_str, ndate, ntime))
            filled += 1

    return {"status": "ok", "filled": filled}


def _compute_trade_performance(ndate: int, model_version: str = "default", force_retrain: bool = False) -> dict:
    """Compute trade signal performance metrics for a given date.

    Joins ml_predictions with trade_signals to calculate accuracy, financial metrics,
    and breakdowns by trade type and confidence level. Persists results to ml_trade_performance.

    Args:
        ndate: Date in YYYYMMDD format
        model_version: Identifier for the model version that made predictions
        force_retrain: Whether forced retrain was used

    Returns:
        Dict with computed metrics
    """
    from datetime import datetime as _dt

    with _db() as con:
        # Join ml_predictions with trade_signals to get predictions + actual outcomes
        rows = con.execute("""
            SELECT
                p.confidence,
                p.trade_code,
                p.vol_regime_pred, p.vol_regime_actual,
                p.direction_pred, p.direction_2hr_actual,
                t.outcome,
                t.outcome_points,
                t.action
            FROM ml_predictions p
            LEFT JOIN trade_signals t ON t.ndate=p.ndate AND t.ntime=p.ntime AND t.symbol='SPX'
            WHERE p.ndate=?
        """, (ndate,)).fetchall()

    if not rows:
        return {"status": "skipped", "reason": "no predictions found for this date"}

    # Initialize counters
    total = len(rows)
    high_conf = medium_conf = low_conf = 0
    trade_correct = trade_incorrect = trade_neutral = 0

    # Trade type counters
    trade_type_counts = {
        "IC": {"correct": 0, "total": 0},
        "SPS": {"correct": 0, "total": 0},
        "SCS": {"correct": 0, "total": 0},
        "LCS": {"correct": 0, "total": 0},
        "LPS": {"correct": 0, "total": 0},
    }

    # Confidence-specific accuracy
    high_conf_correct = high_conf_total = 0
    medium_conf_correct = medium_conf_total = 0

    # Financial metrics
    total_points = 0.0
    points_list = []

    # Vol regime accuracy
    vol_correct = vol_total = 0

    # Direction accuracy
    dir_correct = dir_total = 0

    for row in rows:
        confidence, trade_code, vol_pred, vol_actual, dir_pred, dir_actual, outcome, outcome_points, action = row

        # Count by confidence
        if confidence == "HIGH":
            high_conf += 1
            high_conf_total += 1
        elif confidence == "MEDIUM":
            medium_conf += 1
            medium_conf_total += 1
        else:
            low_conf += 1

        # Trade outcome classification
        if outcome in ("WIN", "CORRECT", "PARTIAL"):
            trade_correct += 1
            if confidence == "HIGH":
                high_conf_correct += 1
            elif confidence == "MEDIUM":
                medium_conf_correct += 1
        elif outcome in ("LOSS", "MISSED"):
            trade_incorrect += 1
        elif outcome == "NEUTRAL":
            trade_neutral += 1

        # Trade type breakdown
        if trade_code in trade_type_counts:
            trade_type_counts[trade_code]["total"] += 1
            if outcome in ("WIN", "CORRECT", "PARTIAL"):
                trade_type_counts[trade_code]["correct"] += 1

        # Financial metrics
        if outcome_points is not None:
            total_points += outcome_points
            points_list.append(outcome_points)

        # Vol regime accuracy
        if vol_pred and vol_actual:
            vol_total += 1
            if vol_pred == vol_actual:
                vol_correct += 1

        # Direction accuracy
        if dir_pred and dir_actual:
            dir_total += 1
            if dir_pred == dir_actual:
                dir_correct += 1

    # Calculate derived metrics
    high_conf_accuracy = (high_conf_correct / high_conf_total) if high_conf_total > 0 else None
    medium_conf_accuracy = (medium_conf_correct / medium_conf_total) if medium_conf_total > 0 else None
    avg_points = (total_points / len(points_list)) if points_list else None

    # Calculate max drawdown (largest losing streak)
    max_drawdown = None
    if points_list:
        cumulative = 0
        min_cumulative = 0
        for p in points_list:
            cumulative += p
            if cumulative < min_cumulative:
                min_cumulative = cumulative
        max_drawdown = abs(min_cumulative)

    # Get model training date
    training_date = None
    with _db() as con:
        model_row = con.execute(
            "SELECT trained_at FROM ml_models WHERE model_name='vol_regime' ORDER BY trained_at DESC LIMIT 1"
        ).fetchone()
        if model_row:
            training_date = model_row[0]

    # Computed timestamp
    computed_at = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Persist to database
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO ml_trade_performance
            (ndate, model_version, training_date, force_retrain,
             total_predictions, high_conf_predictions, medium_conf_predictions, low_conf_predictions,
             trade_correct, trade_incorrect, trade_neutral,
             ic_correct, ic_total, sps_correct, sps_total, scs_correct, scs_total,
             lcs_correct, lcs_total, lps_correct, lps_total,
             high_conf_accuracy, medium_conf_accuracy,
             total_outcome_points, avg_outcome_points, max_drawdown,
             vol_regime_correct, vol_regime_total, vol_regime_accuracy,
             direction_2hr_correct, direction_2hr_total, direction_2hr_accuracy,
             computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ndate, model_version, training_date, 1 if force_retrain else 0,
            total, high_conf, medium_conf, low_conf,
            trade_correct, trade_incorrect, trade_neutral,
            trade_type_counts["IC"]["correct"], trade_type_counts["IC"]["total"],
            trade_type_counts["SPS"]["correct"], trade_type_counts["SPS"]["total"],
            trade_type_counts["SCS"]["correct"], trade_type_counts["SCS"]["total"],
            trade_type_counts["LCS"]["correct"], trade_type_counts["LCS"]["total"],
            trade_type_counts["LPS"]["correct"], trade_type_counts["LPS"]["total"],
            high_conf_accuracy, medium_conf_accuracy,
            total_points, avg_points, max_drawdown,
            vol_correct, vol_total, (vol_correct / vol_total) if vol_total > 0 else None,
            dir_correct, dir_total, (dir_correct / dir_total) if dir_total > 0 else None,
            computed_at
        ))

    return {
        "status": "ok",
        "ndate": ndate,
        "total_predictions": total,
        "trade_accuracy": (trade_correct / (trade_correct + trade_incorrect)) if (trade_correct + trade_incorrect) > 0 else None,
        "total_outcome_points": total_points
    }


# Feature set used for ML models (subset of full PCA features — top ranked, non-redundant)
ML_FEATURES = [
    # Original GEX features
    "net_gex", "total_call_gex", "total_put_gex",
    "sentiment", "gex_ratio", "kcs", "dominance",
    "key_call_gex", "key_put_gex",
    "key_call_oi", "key_put_oi",
    "key_call_vol", "key_put_vol",
    "total_call_oi", "total_put_oi",
    "total_call_vol", "total_put_vol",
    "oi_ratio", "vol_ratio",
    "dist_to_key", "dist_to_flip",
    # Price momentum features
    "price_change", "price_change_pct",
    # Lagged GEX features (change from previous snapshot)
    "net_gex_change", "sentiment_change", "gex_ratio_change",
    # Time-of-day features
    "hour_sin", "hour_cos",
    # Trade Signal Feedback Loop Features
    "call_wall_success_rate_7d", "call_wall_success_rate_30d",
    "put_wall_success_rate_7d", "put_wall_success_rate_30d",
    "butterfly_success_rate_7d", "butterfly_success_rate_30d",
    "condor_success_rate_7d", "condor_success_rate_30d",
    "pillar_success_rate_7d", "pillar_success_rate_30d",
    "notrade_success_rate_7d", "notrade_success_rate_30d",
    "wall_strength_score", "signal_reliability_score",
    "recent_signal_performance_5", "recent_signal_performance_20",
    "high_volatility_regime", "trending_market", "choppy_market", "macro_event_risk",
]

# Trade recommendation matrix: (vol_regime, direction) → trade type
_TRADE_MATRIX = {
    ("TIGHT",  "NEUTRAL"): ("Iron Condor",        "IC"),
    ("TIGHT",  "FLAT"):    ("Iron Condor",         "IC"),
    ("TIGHT",  "UP"):      ("Short Put Spread",    "SPS"),
    ("TIGHT",  "DOWN"):    ("Short Call Spread",   "SCS"),
    ("WIDE",   "NEUTRAL"): ("Iron Butterfly",      "IB"),
    ("WIDE",   "UP"):      ("Long Call Spread",    "LCS"),
    ("WIDE",   "DOWN"):    ("Long Put Spread",     "LPS"),
}


def _ensure_ml_models_table() -> None:
    """Create ml_models table for storing trained model blobs."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ml_models (
                model_name  TEXT PRIMARY KEY,
                trained_at  TEXT NOT NULL,
                n_samples   INTEGER NOT NULL,
                features    TEXT NOT NULL,
                classes     TEXT NOT NULL,
                accuracy    REAL,
                model_blob  BLOB NOT NULL
            )
        """)
        # Create history table for tracking performance over time
        con.execute("""
            CREATE TABLE IF NOT EXISTS ml_model_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name  TEXT NOT NULL,
                trained_at  TEXT NOT NULL,
                n_samples   INTEGER NOT NULL,
                accuracy    REAL,
                features    TEXT NOT NULL,
                classes     TEXT NOT NULL,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _extract_gex_features(strikes, uprice, prev_price=None, prev_feats=None, ntime=None, ndate=None) -> dict:
    """Extract all ML features from a strike list and SPX price.

    Args:
        strikes: Strike data list
        uprice: Current SPX price
        prev_price: Previous snapshot price (for momentum features)
        prev_feats: Previous snapshot features dict (for lagged GEX features)
        ntime: Current time in HHMM format (for time-of-day encoding)

    Returns a dict keyed by ML_FEATURES names, or None if insufficient data.
    """
    from controllers.gex_calculations import (
        calculate_sentiment, calculate_gex_ratio, calculate_net_gex,
        calculate_kcs, calculate_dominance, calculate_key_strike_stats,
        calculate_total_oi_and_vol, calculate_total_gex, calculate_flip_level,
    )
    if not strikes or not uprice:
        return None

    sentiment    = calculate_sentiment(strikes)
    gex_ratio    = calculate_gex_ratio(strikes)
    net_gex      = calculate_net_gex(strikes)
    kcs          = calculate_kcs(strikes, uprice)
    dominance    = calculate_dominance(strikes, uprice)
    key_stats    = calculate_key_strike_stats(strikes, uprice)
    oi_vol       = calculate_total_oi_and_vol(strikes)
    total_gex    = calculate_total_gex(strikes)
    flip         = calculate_flip_level(strikes)

    tcoi  = oi_vol["total_call_oi"] or 0
    tpoi  = oi_vol["total_put_oi"]  or 0
    tcvol = oi_vol["total_call_vol"] or 0
    tpvol = oi_vol["total_put_vol"]  or 0

    # Price momentum features
    price_change = 0.0
    price_change_pct = 0.0
    if prev_price and prev_price > 0:
        price_change = uprice - prev_price
        price_change_pct = (price_change / prev_price) * 100

    # Lagged GEX features (change from previous snapshot)
    net_gex_change = 0.0
    sentiment_change = 0.0
    gex_ratio_change = 0.0
    if prev_feats:
        net_gex_change = net_gex - prev_feats.get("net_gex", net_gex)
        sentiment_change = sentiment - prev_feats.get("sentiment", sentiment)
        gex_ratio_change = gex_ratio - prev_feats.get("gex_ratio", gex_ratio)

    # Time-of-day encoding (cyclical)
    hour_sin = 0.0
    hour_cos = 0.0
    if ntime:
        import numpy as np
        hour = (ntime // 100) + (ntime % 100) / 60  # Convert HHMM to hours
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)

    # Get feedback loop features if available
    feedback_features = _get_feedback_features(ndate, ntime) if ntime else {}
    
    return {
        "net_gex":       net_gex,
        "total_call_gex": total_gex["total_call_gex"],
        "total_put_gex":  total_gex["total_put_gex"],
        "sentiment":     sentiment,
        "gex_ratio":     gex_ratio,
        "kcs":           kcs,
        "dominance":     dominance,
        "key_call_gex":  key_stats["key_call_gex"],
        "key_put_gex":   key_stats["key_put_gex"],
        "key_call_oi":   key_stats["key_call_oi"],
        "key_put_oi":    key_stats["key_put_oi"],
        "key_call_vol":  key_stats["key_call_vol"],
        "key_put_vol":  key_stats["key_put_vol"],
        "total_call_oi": tcoi,
        "total_put_oi":  tpoi,
        "total_call_vol": tcvol,
        "total_put_vol": tpvol,
        "oi_ratio":      round(tcoi / tpoi, 4) if tpoi else 0,
        "vol_ratio":     round(tcvol / tpvol, 4) if tpvol else 0,
        "dist_to_key":   abs(uprice - (key_stats["key_strike"] or uprice)),
        "dist_to_flip":  abs(uprice - flip) if flip else 0,
        "price_change":  price_change,
        "price_change_pct": price_change_pct,
        "net_gex_change": net_gex_change,
        "sentiment_change": sentiment_change,
        "gex_ratio_change": gex_ratio_change,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        # Trade Signal Feedback Loop Features
        "call_wall_success_rate_7d": feedback_features.get("call_wall_success_rate_7d", 0.5),
        "call_wall_success_rate_30d": feedback_features.get("call_wall_success_rate_30d", 0.5),
        "put_wall_success_rate_7d": feedback_features.get("put_wall_success_rate_7d", 0.5),
        "put_wall_success_rate_30d": feedback_features.get("put_wall_success_rate_30d", 0.5),
        "butterfly_success_rate_7d": feedback_features.get("butterfly_success_rate_7d", 0.5),
        "butterfly_success_rate_30d": feedback_features.get("butterfly_success_rate_30d", 0.5),
        "condor_success_rate_7d": feedback_features.get("condor_success_rate_7d", 0.5),
        "condor_success_rate_30d": feedback_features.get("condor_success_rate_30d", 0.5),
        "pillar_success_rate_7d": feedback_features.get("pillar_success_rate_7d", 0.5),
        "pillar_success_rate_30d": feedback_features.get("pillar_success_rate_30d", 0.5),
        "notrade_success_rate_7d": feedback_features.get("notrade_success_rate_7d", 0.5),
        "notrade_success_rate_30d": feedback_features.get("notrade_success_rate_30d", 0.5),
        "wall_strength_score": feedback_features.get("wall_strength_score", 0.5),
        "signal_reliability_score": feedback_features.get("signal_reliability_score", 0.5),
        "recent_signal_performance_5": feedback_features.get("recent_signal_performance_5", 0.0),
        "recent_signal_performance_20": feedback_features.get("recent_signal_performance_20", 0.0),
        "high_volatility_regime": feedback_features.get("high_volatility_regime", 0),
        "trending_market": feedback_features.get("trending_market", 0),
        "choppy_market": feedback_features.get("choppy_market", 1),
        "macro_event_risk": feedback_features.get("macro_event_risk", 0),
    }


def _filter_signal_with_feedback(setup_type: str, feedback_features: dict, snap: dict) -> str:
    """Filter trade signals based on feedback loop performance data.
    
    Uses both setup-type success rates AND strike-specific wall performance
    to avoid blocking good walls when another wall at a different strike failed.
    
    Args:
        setup_type: Original signal setup type (CALL_WALL, PIN, etc.)
        feedback_features: Dictionary of feedback performance metrics
        snap: Current snapshot data
    
    Returns:
        Filtered setup type (may be changed to NEG_GAMMA if conditions are poor)
    """
    # Extract key feedback metrics
    wall_strength = feedback_features.get("wall_strength_score", 0.5)
    signal_reliability = feedback_features.get("signal_reliability_score", 0.5)
    choppy_market = feedback_features.get("choppy_market", 0)
    high_volatility = feedback_features.get("high_volatility_regime", 0)
    
    # Get signal-specific success rates
    call_wall_success_7d = feedback_features.get("call_wall_success_rate_7d", 0.5)
    call_wall_success_30d = feedback_features.get("call_wall_success_rate_30d", 0.5)
    butterfly_success_7d = feedback_features.get("butterfly_success_rate_7d", 0.5)
    butterfly_success_30d = feedback_features.get("butterfly_success_rate_30d", 0.5)
    pillar_success_7d = feedback_features.get("pillar_success_rate_7d", 0.5)
    pillar_success_30d = feedback_features.get("pillar_success_rate_30d", 0.5)
    
    # Get current snapshot details for strike-specific filtering
    ndate = snap.get("ndate")
    ntime = snap.get("ntime")
    key_strike = snap.get("key_strike") or 0
    
    # Apply filtering rules
    
    # Rule 1: Filter CALL_WALL signals using strike-specific performance
    if setup_type == "CALL_WALL":
        # Calculate strike-specific wall score
        from controllers.feedback_loop_features import calculate_strike_wall_score
        strike_score = 0.5
        if ndate and ntime and key_strike:
            try:
                strike_score = calculate_strike_wall_score(ndate, ntime, "CALL_WALL", key_strike)
            except Exception:
                strike_score = call_wall_success_30d
        
        # Block if this specific strike has poor history
        if strike_score < 0.25:
            # Specific strike has poor track record (e.g., 7520 wall)
            return "NEG_GAMMA"
            
        # Block if setup-type is performing poorly AND market conditions are bad
        if (call_wall_success_30d < 0.3 and 
            signal_reliability < 0.35 and 
            choppy_market == 1):
            return "NEG_GAMMA"
            
        # Block extremely weak walls
        if wall_strength < 0.25:
            return "NEG_GAMMA"
    
    # Rule 2: Filter PIN (Iron Butterfly) signals during poor performance
    elif setup_type == "PIN":
        if butterfly_success_30d < 0.3:  # Poor butterfly performance
            return "NEG_GAMMA"
            
        if signal_reliability < 0.3 and choppy_market == 1:
            return "NEG_GAMMA"
    
    # Rule 3: Filter PUT_PILLAR signals using strike-specific performance
    elif setup_type == "PUT_PILLAR":
        from controllers.feedback_loop_features import calculate_strike_wall_score
        strike_score = 0.5
        if ndate and ntime and key_strike:
            try:
                strike_score = calculate_strike_wall_score(ndate, ntime, "PUT_PILLAR", key_strike)
            except Exception:
                strike_score = pillar_success_30d
        
        if strike_score < 0.2:
            return "NEG_GAMMA"
            
        if wall_strength < 0.3:  # Weak support levels
            return "NEG_GAMMA"
    
    # Rule 4: General market condition filtering
    if signal_reliability < 0.20:  # Extremely poor overall system performance
        return "NEG_GAMMA"
        
    if high_volatility == 1 and signal_reliability < 0.4:
        # Avoid directional signals during high volatility with poor reliability
        return "NEG_GAMMA"
    
    # If no filtering triggered, return original setup_type
    return setup_type


def _get_feedback_features(ndate: int, ntime: int) -> dict:
    """Retrieve trade signal feedback features for a specific snapshot.
    
    Args:
        ndate: Date in YYYYMMDD format
        ntime: Time in HHMM format
    
    Returns:
        Dictionary of feedback features or empty dict if not found
    """
    try:
        with _db() as con:
            cursor = con.execute("""
                SELECT * FROM trade_signal_features 
                WHERE ndate = ? AND ntime = ?
            """, (ndate, ntime))
            
            row = cursor.fetchone()
            if not row:
                return {}
            
            # Map columns to feature names
            columns = [
                'ndate', 'ntime', 'symbol',
                'call_wall_success_rate_7d', 'call_wall_success_rate_30d',
                'put_wall_success_rate_7d', 'put_wall_success_rate_30d',
                'butterfly_success_rate_7d', 'butterfly_success_rate_30d',
                'condor_success_rate_7d', 'condor_success_rate_30d',
                'pillar_success_rate_7d', 'pillar_success_rate_30d',
                'notrade_success_rate_7d', 'notrade_success_rate_30d',
                'wall_strength_score', 'signal_reliability_score',
                'recent_signal_performance_5', 'recent_signal_performance_20',
                'high_volatility_regime', 'trending_market', 'choppy_market', 'macro_event_risk',
                'calculated_at'
            ]
            
            return {columns[i]: row[i] for i in range(len(columns)) if i < len(row)}
            
    except Exception as e:
        # If feedback features aren't available, return empty dict
        # This allows the system to work without feedback loop initially
        return {}


def _train_ml_models() -> dict:
    """Train Vol Regime and Direction classifiers on ml_labels + GEX features.

    Stores model blobs in ml_models table. Returns a summary dict.
    Uses XGBoost for direction model, RandomForest for vol_regime.
    Includes price momentum, lagged GEX, and time-of-day features.
    Minimum 30 labelled samples required.
    """
    import pickle
    import numpy as np

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score
    except ImportError:
        return {"status": "error", "reason": "scikit-learn not installed"}

    try:
        import xgboost as xgb
    except ImportError:
        return {"status": "error", "reason": "xgboost not installed"}

    # Pull labelled snapshots joined to GEX features
    with _db() as con:
        rows = con.execute("""
            SELECT g.ndate, g.ntime, g.price, g.data,
                   l.range_regime, l.direction_2hr
            FROM gex_strike_window g
            JOIN ml_labels l ON l.ndate=g.ndate AND l.ntime=g.ntime
            WHERE g.symbol='SPX' AND g.source='gex' AND g.ntime>=935
              AND l.range_regime IS NOT NULL AND l.direction_2hr IS NOT NULL
            ORDER BY g.ndate, g.ntime
        """).fetchall()

    if len(rows) < 30:
        return {"status": "error", "reason": f"insufficient labelled data ({len(rows)} rows, need 30+)"}

    import json as _json
    X, y_regime, y_direction = [], [], []
    
    # Track previous snapshot for each row
    prev_price = None
    prev_feats = None
    prev_ndate = None
    
    for ndate, ntime, uprice, data_json, range_regime, direction_2hr in rows:
        try:
            strikes = _json.loads(data_json) if data_json else []
        except Exception:
            continue
        
        # Reset previous snapshot on new day
        if ndate != prev_ndate:
            prev_price = None
            prev_feats = None
            prev_ndate = ndate
        
        feats = _extract_gex_features(strikes, uprice, prev_price, prev_feats, ntime, ndate)
        if feats is None:
            continue
        
        X.append([feats[f] for f in ML_FEATURES])
        # Collapse NORMAL→TIGHT: model predicts WIDE (dangerous) vs TIGHT (safe to sell premium)
        regime_label = "WIDE" if range_regime == "WIDE" else "TIGHT"
        y_regime.append(regime_label)
        y_direction.append(direction_2hr)
        
        # Update previous snapshot for next iteration
        prev_price = uprice
        prev_feats = feats

    if len(X) < 30:
        return {"status": "error", "reason": f"insufficient valid feature rows ({len(X)})"}

    import numpy as np
    X = np.array(X, dtype=float)
    # Replace any NaN/inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    trained_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    results = {}

    # Train vol_regime with RandomForest (working well)
    clf_vol = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf_vol.fit(X_scaled, y_regime)
    try:
        cv_scores = cross_val_score(clf_vol, X_scaled, y_regime, cv=3, scoring="accuracy")
        vol_accuracy = round(float(cv_scores.mean()), 4)
    except Exception:
        vol_accuracy = None

    blob_vol = pickle.dumps({"clf": clf_vol, "scaler": scaler, "features": ML_FEATURES})
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO ml_models
            (model_name, trained_at, n_samples, features, classes, accuracy, model_blob)
            VALUES (?,?,?,?,?,?,?)
        """, ("vol_regime", trained_at, len(X), json.dumps(ML_FEATURES),
              json.dumps(sorted(set(y_regime))), vol_accuracy, blob_vol))

    results["vol_regime"] = {
        "samples": len(X), "classes": sorted(set(y_regime)), "accuracy": vol_accuracy
    }

    # Train direction with XGBoost (to improve accuracy)
    # Encode labels to numeric for XGBoost
    label_encoder = {label: idx for idx, label in enumerate(sorted(set(y_direction)))}
    y_direction_encoded = [label_encoder[y] for y in y_direction]
    
    clf_dir = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        objective='multi:softprob',
        num_class=len(label_encoder),
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1,
    )
    clf_dir.fit(X_scaled, y_direction_encoded)
    
    try:
        cv_scores = cross_val_score(clf_dir, X_scaled, y_direction_encoded, cv=3, scoring="accuracy")
        dir_accuracy = round(float(cv_scores.mean()), 4)
    except Exception:
        dir_accuracy = None

    blob_dir = pickle.dumps({"clf": clf_dir, "scaler": scaler, "features": ML_FEATURES, "label_encoder": label_encoder})
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO ml_models
            (model_name, trained_at, n_samples, features, classes, accuracy, model_blob)
            VALUES (?,?,?,?,?,?,?)
        """, ("direction", trained_at, len(X), json.dumps(ML_FEATURES),
              json.dumps(sorted(set(y_direction))), dir_accuracy, blob_dir))

    results["direction"] = {
        "samples": len(X), "classes": sorted(set(y_direction)), "accuracy": dir_accuracy
    }

    return {"status": "ok", "trained_at": trained_at, "models": results}


def _load_ml_model(model_name: str):
    """Load a trained ML model from DB. Returns (clf, scaler, features, label_encoder) or (None, None, None, None)."""
    import pickle
    with _db() as con:
        row = con.execute(
            "SELECT model_blob, features FROM ml_models WHERE model_name=?",
            (model_name,)
        ).fetchone()
    if not row:
        return None, None, None, None
    payload = pickle.loads(row[0])
    label_encoder = payload.get("label_encoder", None)
    return payload["clf"], payload["scaler"], payload["features"], label_encoder


def _predict_snapshot(strikes, uprice, ntime=None) -> dict:
    """Run Vol Regime + Direction predictions for a snapshot.

    Args:
        strikes: Strike data list
        uprice: Current SPX price
        ntime: Current time in HHMM format (for time-of-day encoding)

    Returns a dict with:
        vol_regime, vol_regime_proba   - TIGHT/NORMAL/WIDE + confidence
        direction, direction_proba     - UP/FLAT/DOWN + confidence
        trade, trade_code              - recommended trade type
        confidence                     - LOW/MEDIUM/HIGH (based on both probas)
        signal_text                    - compact badge text
    """
    import numpy as np

    # For real-time predictions, we don't have previous snapshot data
    feats = _extract_gex_features(strikes, uprice, prev_price=None, prev_feats=None, ntime=ntime, ndate=None)
    if feats is None:
        return {"error": "insufficient features"}

    X = np.array([[feats[f] for f in ML_FEATURES]], dtype=float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    results = {}
    for model_name in ("vol_regime", "direction"):
        clf, scaler, features, label_encoder = _load_ml_model(model_name)
        if clf is None:
            return {"error": f"{model_name} model not trained yet"}
        X_scaled = scaler.transform(X)
        pred_encoded = clf.predict(X_scaled)[0]
        proba = clf.predict_proba(X_scaled)[0]
        max_proba = float(max(proba))
        
        # Decode label if using XGBoost (has label_encoder)
        if label_encoder:
            # Reverse encoder: {idx: label}
            reverse_encoder = {idx: label for label, idx in label_encoder.items()}
            pred = reverse_encoder.get(pred_encoded, str(pred_encoded))
        else:
            pred = pred_encoded
        
        results[model_name] = {"label": pred, "confidence": max_proba}

    vol   = results["vol_regime"]["label"]
    dirn  = results["direction"]["label"]
    vc    = results["vol_regime"]["confidence"]
    dc    = results["direction"]["confidence"]
    min_conf = min(vc, dc)

    trade, trade_code = _TRADE_MATRIX.get((vol, dirn), ("No clear signal", "---"))

    if min_conf >= 0.65:
        conf_label = "HIGH"
        dots = "●●●"
    elif min_conf >= 0.45:
        conf_label = "MEDIUM"
        dots = "●●○"
    else:
        conf_label = "LOW"
        dots = "●○○"

    # Suppress trade recommendation for LOW confidence
    show_trade = conf_label in ("HIGH", "MEDIUM")
    if not show_trade:
        trade = "Low confidence"
        trade_code = "---"

    # Look up historical viable rate for this trade code
    viable_rate = None
    if trade_code not in ("---", None):
        _tc_col = {"IC": "trade_viable_ic", "IB": "trade_viable_ic",
                   "SPS": "trade_viable_sps", "SCS": "trade_viable_scs",
                   "LCS": "trade_viable_lcs", "LPS": "trade_viable_lps"}.get(trade_code)
        if _tc_col:
            try:
                with _db() as _con:
                    _r = _con.execute(
                        f"SELECT ROUND(AVG({_tc_col})*100,1) FROM ml_labels WHERE {_tc_col} IS NOT NULL"
                    ).fetchone()
                    viable_rate = _r[0] if _r else None
            except Exception:
                pass

    signal_text = f"[{vol}] [{dirn}] → {trade} {dots}"
    if viable_rate is not None:
        signal_text += f" {viable_rate}% hist"

    return {
        "vol_regime":        vol,
        "vol_regime_proba":  round(vc, 3),
        "direction":         dirn,
        "direction_proba":   round(dc, 3),
        "trade":             trade,
        "trade_code":        trade_code,
        "confidence":        conf_label,
        "viable_rate":       viable_rate,
        "signal_text":       signal_text,
    }


def _maybe_retrain_ml_models() -> dict:
    """Retrain ML models if they are missing or the labelled dataset has grown by 5+ new days."""
    with _db() as con:
        row = con.execute(
            "SELECT trained_at, n_samples FROM ml_models WHERE model_name='vol_regime'"
        ).fetchone()
        current_samples = con.execute(
            "SELECT COUNT(*) FROM ml_labels WHERE range_regime IS NOT NULL AND direction_eod IS NOT NULL"
        ).fetchone()[0]

    if row is None:
        return _train_ml_models()

    # Roughly 14 snapshots per trading day — retrain if grown by ~5 days worth
    trained_samples = row[1]
    if current_samples - trained_samples >= 70:
        return _train_ml_models()

    return {"status": "skipped", "reason": "models up to date", "samples": current_samples}


# =============================================================================
# Daily Analysis helpers
# =============================================================================

ANALYSIS_DIR = BASE_DIR / "analysis"


def _find_existing_analysis_report(ndate: int) -> Path | None:
    """Find the latest analysis-concise-YYYYMMDD-*.md file for a date."""
    prefix = f"analysis-concise-{ndate}-"
    candidates = sorted(ANALYSIS_DIR.glob(f"{prefix}*.md"), key=lambda p: p.name, reverse=True)
    return candidates[0] if candidates else None


def _save_analysis_report(ndate: int, ntime: int, content: str) -> Path:
    """Save a generated daily analysis report to the analysis directory."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"{ntime:04d}"
    path = ANALYSIS_DIR / f"analysis-concise-{ndate}-{suffix}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _fetch_yahoo_ohlc_for_date(date_iso: str) -> dict:
    """Fetch daily OHLC for a single date from Yahoo Finance (^GSPC).

    Returns {"open": ..., "high": ..., "low": ..., "close": ...} or empty dict on failure.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {}

    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        ticker = yf.Ticker("^GSPC")
        # Request a small window around the target date
        start = (dt - timedelta(days=3)).strftime("%Y-%m-%d")
        end = (dt + timedelta(days=3)).strftime("%Y-%m-%d")
        df = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)
        if df is None or df.empty:
            return {}

        # Yahoo index is timezone-aware; normalize to naive date
        target_str = date_iso
        for ts, row in df.iterrows():
            ts_date = ts.date() if hasattr(ts, "date") else ts
            if str(ts_date) == target_str:
                return {
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                }
        return {}
    except Exception:
        return {}


def _compute_concise_summary_from_strikes(strikes: list, last: float, ndate: int, ntime: int) -> dict:
    """Compute concise GEX summary metrics from a gex_strike_window snapshot.

    Mirrors process_gex_window.summarize_gex() using the 40-strike window already stored
    in the database. This keeps report generation fast and self-contained.
    """
    if not strikes or last is None:
        return {}

    def v(row, key):
        return row.get(key, 0) or 0

    rows = strikes
    positive_rows = [r for r in rows if v(r, "total") > 0]
    negative_rows = [r for r in rows if v(r, "total") < 0]

    PROX_BANDWIDTH = 50.0

    def proximity_weighted_abs(row):
        dist = abs(v(row, "strike") - last)
        decay = math.exp(-0.5 * (dist / PROX_BANDWIDTH) ** 2)
        return abs(v(row, "abs")) * decay

    sorted_by_abs = sorted(rows, key=proximity_weighted_abs, reverse=True)
    highest_abs_row = sorted_by_abs[0]
    second_highest_row = sorted_by_abs[1] if len(sorted_by_abs) > 1 else None

    # Key strike stats
    cg_abs = abs(v(highest_abs_row, "cg"))
    pg_abs = abs(v(highest_abs_row, "pg"))
    key_balance_total = cg_abs + pg_abs
    key_strike_balance = round((cg_abs - pg_abs) / key_balance_total * 100, 2) if key_balance_total else None

    total_abs_gex = sum(abs(v(r, "abs")) for r in rows)
    key_abs = abs(v(highest_abs_row, "abs"))
    key_strike_dominance_pct = round(key_abs / total_abs_gex * 100, 2) if total_abs_gex else None

    ks_coi = v(highest_abs_row, "coi")
    ks_poi = v(highest_abs_row, "poi")
    ks_oi_total = ks_coi + ks_poi
    key_strike_oi_balance = round((ks_coi - ks_poi) / ks_oi_total * 100, 2) if ks_oi_total else None

    ks_cvol = v(highest_abs_row, "cvol")
    ks_pvol = v(highest_abs_row, "pvol")
    ks_vol_total = ks_cvol + ks_pvol
    key_strike_vol_balance = round((ks_cvol - ks_pvol) / ks_vol_total * 100, 2) if ks_vol_total else None

    # Top OI / vol strikes
    top_oi_row = max(rows, key=lambda r: v(r, "coi") + v(r, "poi"))
    top_vol_row = max(rows, key=lambda r: v(r, "cvol") + v(r, "pvol"))

    # Totals
    positive_net_value = sum(v(r, "net") for r in positive_rows)
    negative_net_value = sum(v(r, "net") for r in negative_rows)
    total_call_gex = sum(v(r, "cg") for r in rows)
    total_put_gex = sum(v(r, "pg") for r in rows)
    net_gex = total_call_gex + total_put_gex

    # Flip level: cumulative net GEX crosses zero within the window
    from controllers.gex_calculations import calculate_flip_level
    flip = calculate_flip_level(rows)

    # KCS (Key Call Support) using the same formula as gex_calculations.py
    total_oi = sum(v(r, "coi") + v(r, "poi") for r in rows)
    total_vol = sum(v(r, "cvol") + v(r, "pvol") for r in rows)
    key_strike_price = v(highest_abs_row, "strike")
    distance = abs(key_strike_price - last)
    prox_kcs = math.exp(-distance / 25.0)
    gex_share = key_abs / total_abs_gex if total_abs_gex else 0.0
    oi_share = (ks_coi + ks_poi) / total_oi if total_oi else 0.0
    vol_share = (ks_cvol + ks_pvol) / total_vol if total_vol else 0.0
    kcs = round((0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * prox_kcs * 100, 2)

    if abs(total_call_gex) >= abs(total_put_gex):
        gex_ratio = abs(total_call_gex) / abs(total_put_gex) if total_put_gex else None
    else:
        gex_ratio = -(abs(total_put_gex) / abs(total_call_gex)) if total_call_gex else None

    # Weighted mean strikes
    put_gex_weights = [(v(r, "strike"), abs(v(r, "pg"))) for r in rows if v(r, "pg") != 0]
    total_put_gex_weight = sum(w for _, w in put_gex_weights)
    weighted_mean_put_strike_gex = round(sum(s * w for s, w in put_gex_weights) / total_put_gex_weight, 2) if total_put_gex_weight else None

    put_oi_weights = [(v(r, "strike"), v(r, "poi")) for r in rows if v(r, "poi") > 0]
    total_put_oi_weight = sum(w for _, w in put_oi_weights)
    weighted_mean_put_strike_oi = round(sum(s * w for s, w in put_oi_weights) / total_put_oi_weight, 2) if total_put_oi_weight else None

    put_vol_weights = [(v(r, "strike"), v(r, "pvol")) for r in rows if v(r, "pvol") > 0]
    total_put_vol_weight = sum(w for _, w in put_vol_weights)
    weighted_mean_put_strike_vol = round(sum(s * w for s, w in put_vol_weights) / total_put_vol_weight, 2) if total_put_vol_weight else None

    call_gex_weights = [(v(r, "strike"), abs(v(r, "cg"))) for r in rows if v(r, "cg") != 0]
    total_call_gex_weight = sum(w for _, w in call_gex_weights)
    weighted_mean_call_strike_gex = round(sum(s * w for s, w in call_gex_weights) / total_call_gex_weight, 2) if total_call_gex_weight else None

    call_oi_weights = [(v(r, "strike"), v(r, "coi")) for r in rows if v(r, "coi") > 0]
    total_call_oi_weight = sum(w for _, w in call_oi_weights)
    weighted_mean_call_strike_oi = round(sum(s * w for s, w in call_oi_weights) / total_call_oi_weight, 2) if total_call_oi_weight else None

    call_vol_weights = [(v(r, "strike"), v(r, "cvol")) for r in rows if v(r, "cvol") > 0]
    total_call_vol_weight = sum(w for _, w in call_vol_weights)
    weighted_mean_call_strike_vol = round(sum(s * w for s, w in call_vol_weights) / total_call_vol_weight, 2) if total_call_vol_weight else None

    def _spread(call, put):
        if call is not None and put is not None:
            return round(call - put, 2)
        return None

    return {
        "symbol": "SPX",
        "date": f"{str(ndate)[:4]}-{str(ndate)[4:6]}-{str(ndate)[6:8]} {ntime//100:02d}:{ntime%100:02d}",
        "last": round(last, 2),
        "nearest_strike": min(rows, key=lambda r: (abs(v(r, "strike") - last), r["strike"]))["strike"],
        "positive_gex_bars": len(positive_rows),
        "negative_gex_bars": len(negative_rows),
        "sentiment": round((len(positive_rows) / len(rows)) * 100, 4) if rows else 0,
        "gex_ratio": round(gex_ratio, 4) if gex_ratio is not None else None,
        "positive_gex_net_value": round(positive_net_value, 4),
        "negative_gex_net_value": round(negative_net_value, 4),
        "total_call_gex": round(total_call_gex, 4),
        "total_put_gex": round(total_put_gex, 4),
        "net_gex": round(net_gex, 4),
        "total_call_oi": sum(v(r, "coi") for r in rows),
        "total_put_oi": sum(v(r, "poi") for r in rows),
        "total_call_vol": sum(v(r, "cvol") for r in rows),
        "total_put_vol": sum(v(r, "pvol") for r in rows),
        "flip": flip,
        "key_strike": v(highest_abs_row, "strike"),
        "key_absolute": abs(v(highest_abs_row, "abs")),
        "key_net": v(highest_abs_row, "net"),
        "key_call_gex": v(highest_abs_row, "cg"),
        "key_put_gex": v(highest_abs_row, "pg"),
        "key_call_oi": ks_coi,
        "key_put_oi": ks_poi,
        "key_net_oi": ks_coi - ks_poi,
        "key_call_vol": ks_cvol,
        "key_put_vol": ks_pvol,
        "key_vol_net": ks_cvol - ks_pvol,
        "key_dominance_pct": key_strike_dominance_pct,
        "kcs": kcs,
        "dist_to_key": round(abs(last - v(highest_abs_row, "strike")), 2),
        "key_strike_balance": key_strike_balance,
        "key_strike_oi_balance": key_strike_oi_balance,
        "key_strike_vol_balance": key_strike_vol_balance,
        "key2_strike": v(second_highest_row, "strike") if second_highest_row else None,
        "key2_absolute": abs(v(second_highest_row, "abs")) if second_highest_row else None,
        "top_oi_strike": v(top_oi_row, "strike"),
        "top_oi_total": v(top_oi_row, "coi") + v(top_oi_row, "poi"),
        "top_vol_strike": v(top_vol_row, "strike"),
        "top_vol_total": v(top_vol_row, "cvol") + v(top_vol_row, "pvol"),
        "weighted_mean_put_strike_gex": weighted_mean_put_strike_gex,
        "weighted_mean_put_strike_oi": weighted_mean_put_strike_oi,
        "weighted_mean_put_strike_vol": weighted_mean_put_strike_vol,
        "weighted_mean_call_strike_gex": weighted_mean_call_strike_gex,
        "weighted_mean_call_strike_oi": weighted_mean_call_strike_oi,
        "weighted_mean_call_strike_vol": weighted_mean_call_strike_vol,
        "call_put_gex_strike_spread": _spread(weighted_mean_call_strike_gex, weighted_mean_put_strike_gex),
        "call_put_oi_strike_spread": _spread(weighted_mean_call_strike_oi, weighted_mean_put_strike_oi),
        "call_put_vol_strike_spread": _spread(weighted_mean_call_strike_vol, weighted_mean_put_strike_vol),
    }


def _get_historical_context(summary: dict) -> dict:
    """Load historical concise CSV rows and compute relative stats for the latest summary."""
    concise_path = BASE_DIR / "results" / "daily_gex_summary-concise.csv"
    ctx = {
        "history_count": 0,
        "sentiment_rank": None,
        "net_gex_rank": None,
        "key_absolute_rank": None,
        "dominance_rank": None,
        "prev_date": None,
        "prev_key_strike": None,
    }

    if not concise_path.exists():
        return ctx

    try:
        df = pd.read_csv(concise_path)
    except Exception:
        return ctx

    if df.empty:
        return ctx

    # Map concise CSV columns to our summary names
    numeric_cols = ["sentiment", "net_gex", "key_absolute", "key_dominance_pct"]
    for col in numeric_cols:
        if col in df.columns:
            # Handle B/M suffixes in CSV (e.g. "-2.79B", "3.57B")
            def _parse_number(x):
                if pd.isna(x):
                    return None
                s = str(x).strip()
                if not s:
                    return None
                try:
                    if s.endswith("B"):
                        return float(s[:-1]) * 1e9
                    if s.endswith("M"):
                        return float(s[:-1]) * 1e6
                    if s.endswith("K"):
                        return float(s[:-1]) * 1e3
                    return float(s)
                except ValueError:
                    return None
            df[col] = df[col].apply(_parse_number)

    ctx["history_count"] = len(df)

    def rank(series, value):
        clean = series.dropna()
        if clean.empty or value is None or pd.isna(value):
            return None
        # % of historical values <= current value
        return round((clean <= value).mean() * 100, 1)

    ctx["sentiment_rank"] = rank(df.get("sentiment"), summary.get("sentiment"))
    ctx["net_gex_rank"] = rank(df.get("net_gex"), summary.get("net_gex"))
    ctx["key_absolute_rank"] = rank(df.get("key_absolute"), summary.get("key_absolute"))
    ctx["dominance_rank"] = rank(df.get("key_dominance_pct"), summary.get("key_dominance_pct"))

    # Previous row by date
    if "date" in df.columns and len(df) > 1:
        prev = df.iloc[-2]
        ctx["prev_date"] = str(prev.get("date", ""))
        ctx["prev_key_strike"] = prev.get("key_strike")

    return ctx


def _get_ml_enrichment(strikes: list, uprice: float, ndate: int, ntime: int, summary: dict | None = None) -> dict:
    """Gather ML predictions and feedback-loop features for a snapshot."""
    enrichment = {
        "vol_regime": None,
        "direction": None,
        "rf_outcome": None,
        "hmm_label": None,
        "feedback": {},
    }

    try:
        ml_pred = _predict_snapshot(strikes, uprice, ntime)
        if ml_pred and "error" not in ml_pred:
            enrichment["vol_regime"] = {
                "label": ml_pred.get("vol_regime"),
                "proba": ml_pred.get("vol_regime_proba"),
            }
            enrichment["direction"] = {
                "label": ml_pred.get("direction"),
                "proba": ml_pred.get("direction_proba"),
            }
    except Exception:
        pass

    # RF outcome model
    try:
        from controllers.gex_calculations import calculate_key_strike_stats
        ks = calculate_key_strike_stats(strikes, uprice)
        snap_for_rf = {
            "uprice": uprice,
            "net_gex": sum(r.get("net", 0) or 0 for r in strikes),
            "sentiment": (summary or {}).get("sentiment", 50),
            "sentiment_pct": None,
            "gex_ratio": None,
            "kcs": None,
            "dominance": None,
            "key_dominance_pct": ks.get("key_dominance_pct") if hasattr(ks, "get") else None,
            "total_call_gex": sum(r.get("cg", 0) or 0 for r in strikes),
            "total_put_gex": sum(r.get("pg", 0) or 0 for r in strikes),
            "total_call_oi": sum(r.get("coi", 0) or 0 for r in strikes),
            "total_put_oi": sum(r.get("poi", 0) or 0 for r in strikes),
            "total_call_vol": sum(r.get("cvol", 0) or 0 for r in strikes),
            "total_put_vol": sum(r.get("pvol", 0) or 0 for r in strikes),
            "key_strike": ks.get("key_strike") if hasattr(ks, "get") else None,
            "key_call_gex": ks.get("key_call_gex") if hasattr(ks, "get") else None,
            "key_put_gex": ks.get("key_put_gex") if hasattr(ks, "get") else None,
            "key_call_oi": ks.get("key_call_oi") if hasattr(ks, "get") else None,
            "key_put_oi": ks.get("key_put_oi") if hasattr(ks, "get") else None,
            "key_call_vol": ks.get("key_call_vol") if hasattr(ks, "get") else None,
            "key_put_vol": ks.get("key_put_vol") if hasattr(ks, "get") else None,
            "key2_strike": ks.get("key2_strike") if hasattr(ks, "get") else None,
            "key2_abs": ks.get("key2_abs") if hasattr(ks, "get") else None,
            "key2_call_vol": ks.get("key2_call_vol") if hasattr(ks, "get") else None,
            "key2_put_vol": ks.get("key2_put_vol") if hasattr(ks, "get") else None,
            "flip": None,
        }
        rf = _predict_rf_outcome(snap_for_rf)
        if rf:
            enrichment["rf_outcome"] = rf
    except Exception:
        pass

    # Feedback loop features
    try:
        feedback = _get_feedback_features(ndate, ntime)
        if feedback:
            enrichment["feedback"] = feedback
    except Exception:
        pass

    # HMM label from gex_strike_window row
    try:
        with _db() as con:
            row = con.execute(
                "SELECT hmm_label FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'",
                (ndate, ntime),
            ).fetchone()
            if row:
                enrichment["hmm_label"] = row[0]
    except Exception:
        pass

    return enrichment


def _get_percentile_context_for_snapshot(ndate: int, ntime: int, stats: dict) -> dict:
    """Fetch pre-computed percentile ranks for the snapshot's time slot.

    stats: dict with keys net_gex, call_gex, put_gex, call_oi, put_oi, call_vol, put_vol, kcs, dominance
    Returns a dict with percentile info for each metric, or empty dict if no percentile_history data.
    """
    context = {}
    try:
        with _db() as con:
            # Check if we have percentile_history for this exact slot
            row = con.execute(
                "SELECT COUNT(*) FROM percentile_history WHERE ndate=? AND ntime=?",
                (ndate, ntime)
            ).fetchone()
            has_exact = row and row[0] > 0

            # Fallback: find the time slot with the most historical data
            if not has_exact:
                best_ntime = ntime
                best_size = 0
                for t in TIMES:
                    size = con.execute(
                        "SELECT COUNT(*) FROM percentile_history WHERE ntime=?", (t,)
                    ).fetchone()[0]
                    if size > best_size:
                        best_size = size
                        best_ntime = t
                cache_ntime = best_ntime
            else:
                cache_ntime = ntime

            def pct_for(metric_name, value, invert=False):
                if value is None:
                    return None
                if has_exact:
                    r = con.execute(
                        "SELECT percentile FROM percentile_history WHERE ndate=? AND ntime=? AND metric_name=?",
                        (ndate, ntime, metric_name)
                    ).fetchone()
                    if r:
                        p = r[0]
                        return round(100 - p, 1) if invert else round(p, 1)
                # Live-style percentile: compare current value to slot distribution
                below = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=? AND value<=?",
                    (cache_ntime, metric_name, value)
                ).fetchone()[0]
                total = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=?",
                    (cache_ntime, metric_name)
                ).fetchone()[0]
                if total == 0:
                    return None
                p = round(below / total * 100, 1)
                return round(100 - p, 1) if invert else p

            context = {
                "net_gex": pct_for("net_gex", stats.get("net_gex"), invert=True),
                "total_call_gex": pct_for("total_call_gex", stats.get("total_call_gex")),
                "total_put_gex": pct_for("total_put_gex", stats.get("total_put_gex")),
                "total_call_oi": pct_for("total_call_oi", stats.get("total_call_oi")),
                "total_put_oi": pct_for("total_put_oi", stats.get("total_put_oi")),
                "total_call_vol": pct_for("total_call_vol", stats.get("total_call_vol")),
                "total_put_vol": pct_for("total_put_vol", stats.get("total_put_vol")),
                "kcs": pct_for("kcs", stats.get("kcs")),
                "dominance": pct_for("dominance", stats.get("dominance")),
                "sample_size": con.execute(
                    "SELECT COUNT(DISTINCT ndate) FROM percentile_history WHERE ntime=?", (cache_ntime,)
                ).fetchone()[0],
                "ntime_used": cache_ntime,
            }
    except Exception:
        pass
    return context


def _get_trade_signal_for_snapshot(ndate: int, ntime: int, summary: dict, ml: dict) -> dict:
    """Generate the live trade signal for the snapshot using the same pipeline as the GEX page."""
    try:
        snap = {
            "ndate": ndate,
            "ntime": ntime,
            "uprice": summary.get("last", 0),
            "net_gex": summary.get("net_gex", 0) or 0,
            "gex_ratio": summary.get("gex_ratio", 1) or 1,
            "dominance": summary.get("key_dominance_pct", 0) or 0,
            "key_strike": summary.get("key_strike", 0),
            "key_call_gex": summary.get("key_call_gex", 0) or 0,
            "key_put_gex": summary.get("key_put_gex", 0) or 0,
            "key_call_oi": summary.get("key_call_oi", 0) or 0,
            "key_put_oi": summary.get("key_put_oi", 0) or 0,
            "key_dominance_pct": summary.get("key_dominance_pct", 0) or 0,
            "sentiment_pct": summary.get("sentiment", 50),
            "kcs": summary.get("kcs", 0) or 0,
            "key2_strike": summary.get("key2_strike", 0) or 0,
            "key2_abs": summary.get("key2_absolute", 0) or 0,
            "flip": summary.get("flip"),
            "is_premarket": 1 if ntime < 930 else 0,
            "hmm_label": ml.get("hmm_label", ""),
        }
        signal = _generate_trade_signal(snap, None, None)
        return signal or {}
    except Exception:
        return {}


def _get_oi_character(row: dict, price: float) -> str:
    """Classify a strike as CALL WALL, PUT PILLAR, or balanced based on OI."""
    coi = row.get("call_oi", 0) or 0
    poi = row.get("put_oi", 0) or 0
    total = coi + poi
    if total == 0:
        return "balanced"
    call_pct = coi / total
    put_pct = poi / total
    if call_pct >= 0.65 and row["strike"] >= price:
        return "CALL WALL"
    if put_pct >= 0.65 and row["strike"] <= price:
        return "PUT PILLAR"
    if call_pct >= 0.65:
        return "call-heavy"
    if put_pct >= 0.65:
        return "put-heavy"
    return "balanced"


def _build_lessons_section(primary_setup: str, summary: dict, trade_signal: dict) -> list:
    """Build the Lessons from GEX Teaching section based on setup and metrics."""
    lines = []
    lines.append("## I — Lessons from GEX Teaching Files")
    lines.append("")

    # General principles
    lines.append("### Core Principles")
    lines.append("- Gamma is potential energy — it is highest at at-the-money, short-dated strikes.")
    lines.append("- Market makers hedge continuously to stay delta-neutral; their hedging creates pressure at key strikes.")
    lines.append("- Open interest alone is not directional — it can be condors, hedges, or spreads (Captain Condor artifact).")
    lines.append("- GEX works best on normal days; it is less reliable on monthly expiration, FOMC, CPI, triple witching, and end-of-month/quarter/year.")
    lines.append("- Charm (delta decay) causes hedging flows to change over time even if price does not move.")
    lines.append("")

    # Setup-specific lesson + recommendation
    lines.append("### Setup-Specific Recommendation")
    key_strike = summary.get("key_strike", 0)
    key2_strike = summary.get("key2_strike")
    price = summary.get("last", 0)

    if primary_setup == "PIN":
        lines.append(
            "**PIN / MAGNET lesson:** When call and put gamma are balanced at one dominant strike, "
            "market makers are continuously buying and selling around that level as price oscillates. "
            "This creates a gravitational pull (pin) that can last for much of the session."
        )
        lines.append(f"- **Trade:** Short iron butterfly at {key_strike} (sell ATM call + put, buy OTM wings).")
        lines.append(f"- **Entry zone:** price within ~5 pts of {key_strike}; wait for a small stretch beyond and reversion.")
        lines.append(f"- **Zero-risk construction:** If price dips below {key_strike}, sell an ITM short put spread for credit; "
                     f"if it rebounds to {key_strike}, sell a short call spread. If combined credit >= wing width, max risk is zero.")
        lines.append(f"- **Key validation:** Tomorrow's GEX should also show {key_strike} as a key level; otherwise the pin degrades late in the session.")
        lines.append(f"- **Invalidation:** clean break of {key2_strike or 'key2'} with volume and momentum.")

    elif primary_setup == "PUT_PILLAR":
        lines.append(
            "**PUT PILLAR lesson:** A strike with outsized put gamma + put open interest acts as a support floor. "
            "As price drops toward it, market makers buy hedges, creating upward pressure."
        )
        lines.append(f"- **Trade:** Short put spread at/just below {key_strike} (sell put at {key_strike}, buy further OTM put).")
        lines.append(f"- **Entry zone:** price at or just below {key_strike} after a small overshoot.")
        lines.append(f"- **Thesis:** put pillar holds as support; both legs expire worthless; keep full credit.")
        lines.append(f"- **Invalidation:** price breaks {key_strike} with momentum and holds below.")

    elif primary_setup == "CALL_WALL":
        lines.append(
            "**CALL WALL lesson:** A strike with outsized call gamma + call open interest acts as a resistance ceiling. "
            "As price rises toward it, market makers sell hedges, creating downward pressure."
        )
        lines.append(f"- **Trade:** Short call spread at/just above {key_strike} (sell call at {key_strike}, buy further OTM call).")
        lines.append(f"- **Entry zone:** price at or just above {key_strike} after a small overshoot.")
        lines.append(f"- **Thesis:** call wall holds as resistance; both legs expire worthless; keep full credit.")
        lines.append(f"- **Invalidation:** price breaks {key_strike} on strong volume and holds above.")

    elif primary_setup == "NEG_GAMMA":
        lines.append(
            "**NEGATIVE GAMMA lesson:** When net GEX is strongly negative, market makers are short gamma. "
            "They sell into falls and buy into rallies, which can amplify moves in either direction (convexity / cascade risk)."
        )
        lines.append("- **Trade:** No short premium. Avoid credit spreads and iron butterflies.")
        lines.append("- **Opportunity:** Long directional spreads (long call or put spreads) in the direction of the break, but only on confirmed momentum.")
        lines.append(f"- **Caution:** If key2 ({key2_strike or 'key2'}) is close below key ({key_strike}), a break of both can produce a rapid move.")

    elif primary_setup == "GEX_SLIDE":
        lines.append(
            "**GEX SLIDE lesson:** When gamma is distributed across many strikes, there is no clean anchor. "
            "Price action tends to be fast, disjointed, and whipsaw-prone as hedging occurs at each strike touched."
        )
        lines.append("- **Trade:** No directional short-premium trade. Wait for KCS > 12 and dominance > 10%.")
        lines.append("- **Opportunity:** Far out-of-the-money directional scalps only if a clear intraday level emerges.")
        lines.append("- **Caution:** Do not force a pin or pillar trade when the profile is distributed.")

    elif primary_setup == "POS_GAMMA":
        lines.append(
            "**POSITIVE GAMMA lesson:** When net GEX is positive and sentiment is high, market makers are long gamma. "
            "They buy dips and sell rallies, which tends to dampen moves and create mean reversion."
        )
        lines.append(f"- **Trade:** Short premium near {key_strike} if a clear pin/wall/pillar exists; otherwise stay selective.")
        lines.append("- **Caution:** Positive gamma stabilises but does not eliminate directional moves on high-conviction news.")

    else:
        lines.append(
            "**NO CLEAR SETUP lesson:** When no dominant GEX level exists, the market is not broadcasting a high-probability "
            "gamma-driven trade. The highest-probability move is to do nothing."
        )
        lines.append("- **Trade:** No trade. Wait for a clear wall, pillar, pin, or negative gamma cascade setup.")
        lines.append("- **Caution:** Avoid forcing trades out of boredom or fear of missing out.")

    lines.append("")

    # Discipline checklist
    lines.append("### Discipline Checklist (from transcripts)")
    lines.append("- [ ] Why am I making this trade? Is the gamma profile still valid at entry?")
    lines.append("- [ ] Did I wait for price to stretch slightly beyond the key level before entering on reversion?")
    lines.append("- [ ] Is this a defined-risk structure (spread / butterfly / condor)? No naked shorts.")
    lines.append("- [ ] Have I checked tomorrow's GEX profile to confirm the same key strike?")
    lines.append("- [ ] Is today a normal day, or is it end-of-month, FOMC, CPI, or triple witching?")
    lines.append("- [ ] Am I in a state of peace / logic, or chasing/recovering from a previous loss?")
    lines.append("- [ ] Did I set a profit target and invalidation level before entering?")
    lines.append("")

    # Trade signal integration
    if trade_signal:
        action = trade_signal.get("action") or trade_signal.get("setup_type")
        structure = trade_signal.get("structure")
        caution = trade_signal.get("caution")
        if action and structure:
            lines.append("### Live Trade Signal Integration")
            lines.append(f"- **Action:** {action}")
            lines.append(f"- **Structure:** {structure}")
            if caution:
                lines.append(f"- **Caution:** {caution}")
            lines.append("- **Teaching note:** The live signal applies the same embedded rules plus feedback-loop filtering and RF outcome override. Use it as a confirmation, not a guarantee.")
            lines.append("")

    return lines


def _build_daily_analysis_report(
    summary: dict,
    ohlc: dict,
    history: dict,
    ml: dict,
    top_oi_rows: list,
    percentile_context: dict,
    trade_signal: dict,
) -> str:
    """Build a comprehensive markdown GEX report mirroring the GEX page plus teaching lessons."""

    def fmt_billions(val):
        if val is None:
            return "N/A"
        return f"{val / 1e9:.2f}B"

    def fmt_millions(val):
        if val is None:
            return "N/A"
        return f"{val / 1e6:.2f}M"

    def rank_text(metric, rank):
        if rank is None:
            return "N/A"
        if rank >= 80:
            return f"{rank}% — high/extreme vs history"
        elif rank <= 20:
            return f"{rank}% — low/extreme vs history"
        return f"{rank}% — middle of historical range"

    def fmt_int(val):
        if val is None:
            return "N/A"
        try:
            return f"{int(val):,}"
        except (TypeError, ValueError):
            return str(val)

    def pct_text(metric):
        val = percentile_context.get(metric)
        if val is None:
            return "N/A"
        return f"{val}% percentile ({percentile_context.get('sample_size', 0)} days at {percentile_context.get('ntime_used', 'this time')})"

    # --- Classify setup using the same function as live trade signals ---
    snap_for_setup = {
        "ndate": int(summary["date"][:4] + summary["date"][5:7] + summary["date"][8:10]),
        "ntime": int(summary["date"][11:13] + summary["date"][14:16]),
        "uprice": summary.get("last", 0),
        "net_gex": summary.get("net_gex", 0) or 0,
        "key_strike": summary.get("key_strike", 0),
        "key_call_gex": summary.get("key_call_gex", 0) or 0,
        "key_put_gex": summary.get("key_put_gex", 0) or 0,
        "key_call_oi": summary.get("key_call_oi", 0) or 0,
        "key_put_oi": summary.get("key_put_oi", 0) or 0,
        "key_dominance_pct": summary.get("key_dominance_pct", 0) or 0,
        "sentiment_pct": summary.get("sentiment", 50),
        "kcs": summary.get("kcs", 0) or 0,
        "key2_abs": summary.get("key2_absolute", 0) or 0,
        "flip": summary.get("flip"),
        "is_premarket": 0,
        "hmm_label": ml.get("hmm_label", ""),
    }
    primary_setup = _classify_gex_setup(snap_for_setup)

    # Map internal setup names to report labels
    setup_label_map = {
        "PIN": "PIN / MAGNET",
        "PUT_PILLAR": "PUT PILLAR",
        "CALL_WALL": "CALL WALL",
        "NEG_GAMMA": "NEGATIVE GAMMA ACCELERATION",
        "POS_GAMMA": "POSITIVE GAMMA STABILISING",
        "GEX_SLIDE": "GEX SLIDE",
        "STAY_OUT": "NO CLEAR SETUP",
    }
    setup_types = [setup_label_map.get(primary_setup, primary_setup)]

    # Pull out values used in the rest of the report
    key_net = summary.get("key_net") or 0
    key_call_gex = summary.get("key_call_gex") or 0
    key_put_gex = summary.get("key_put_gex") or 0
    key_abs = summary.get("key_absolute") or 0
    key2_abs = summary.get("key2_absolute") or 0
    net_gex = summary.get("net_gex") or 0
    sentiment = summary.get("sentiment") or 50
    key_dominance = summary.get("key_dominance_pct") or 0
    key_net_oi = summary.get("key_net_oi") or 0
    key_vol_net = summary.get("key_vol_net") or 0
    key_strike_balance = summary.get("key_strike_balance") or 0

    # Volume divergence
    volume_divergence = None
    if key_net_oi != 0 and key_vol_net != 0 and (key_net_oi > 0) != (key_vol_net > 0):
        volume_divergence = "VOLUME DIVERGENCE: intraday flow opposite to structural OI at key strike"

    # OI sandwich detection
    oi_sandwich = None
    if top_oi_rows and len(top_oi_rows) >= 2:
        strikes_sorted = sorted(top_oi_rows, key=lambda r: r["strike"])
        price = summary.get("last", 0)
        below = [r for r in strikes_sorted if r["strike"] < price]
        above = [r for r in strikes_sorted if r["strike"] > price]
        if below and above:
            put_floor = max(below, key=lambda r: r.get("put_oi", 0) + r.get("oi", 0))
            call_ceil = min(above, key=lambda r: r.get("call_oi", 0) + r.get("oi", 0))
            oi_sandwich = (
                f"OI SANDWICH: price {price} between put-heavy {put_floor['strike']} "
                f"and call-heavy {call_ceil['strike']}"
            )

    lines = []
    lines.append(f"# Daily GEX Analysis — {summary['date']}")
    lines.append("")
    lines.append(f"**SPX Last:** {summary['last']}  ")
    lines.append(f"**Key Strike:** {summary['key_strike']} | **Key2 Strike:** {summary.get('key2_strike', 'N/A')}  ")
    lines.append(f"**Setup Classification:** {', '.join(setup_types)}")
    lines.append("")

    # Section A
    lines.append("## A — Today's Values in Isolation")
    lines.append("")
    lines.append(f"- **SPX Last:** {summary['last']}")
    lines.append(f"- **Snapshot Time:** {summary['date']}")
    lines.append(f"- **Key Strike:** {summary['key_strike']} | **Key2 Strike:** {summary.get('key2_strike', 'N/A')}")
    lines.append(f"- **Setup Classification:** {', '.join(setup_types)}")
    lines.append(f"- **Distance to Key:** {summary.get('dist_to_key', 'N/A')} pts")
    lines.append(f"- **Sentiment:** {summary['sentiment']}% of strikes positive gamma")
    lines.append(f"- **Net GEX:** {fmt_billions(net_gex)} ({'stabilising' if net_gex > 0 else 'acceleration risk'})")
    lines.append(f"- **Total Call GEX:** {fmt_billions(summary.get('total_call_gex', 0))}")
    lines.append(f"- **Total Put GEX:** {fmt_billions(summary.get('total_put_gex', 0))}")
    lines.append(f"- **GEX Ratio:** {summary.get('gex_ratio', 'N/A')}")
    lines.append(f"- **KCS (Key Call Support):** {summary.get('kcs', 'N/A')}")
    lines.append(f"- **Dominance:** {key_dominance}% of total absolute GEX sits at the key strike")
    lines.append(f"- **Flip Level:** {summary.get('flip', 'N/A')}")
    lines.append(f"- **Key Absolute GEX:** {fmt_billions(key_abs)}")
    lines.append(f"- **Key Net GEX:** {fmt_billions(key_net)} | **Key Balance:** {key_strike_balance}%")
    lines.append(f"- **Key Call / Put GEX:** {fmt_billions(key_call_gex)} / {fmt_billions(key_put_gex)}")
    lines.append(f"- **Key OI:** Call {fmt_int(summary.get('key_call_oi'))} / Put {fmt_int(summary.get('key_put_oi'))} → Net OI {fmt_int(key_net_oi)}")
    lines.append(f"- **Key Volume:** Call {fmt_int(summary.get('key_call_vol'))} / Put {fmt_int(summary.get('key_put_vol'))} → Net Vol {fmt_int(key_vol_net)}")
    lines.append(f"- **Total Call OI:** {fmt_int(summary.get('total_call_oi'))}")
    lines.append(f"- **Total Put OI:** {fmt_int(summary.get('total_put_oi'))}")
    lines.append(f"- **Total Call Volume:** {fmt_int(summary.get('total_call_vol'))}")
    lines.append(f"- **Total Put Volume:** {fmt_int(summary.get('total_put_vol'))}")
    lines.append(f"- **Top OI Strike:** {summary.get('top_oi_strike', 'N/A')} (total {fmt_int(summary.get('top_oi_total'))})")
    lines.append(f"- **Top Vol Strike:** {summary.get('top_vol_strike', 'N/A')} (total {fmt_int(summary.get('top_vol_total'))})")
    lines.append(f"- **Weighted Mean Put Strike (GEX):** {summary.get('weighted_mean_put_strike_gex', 'N/A')}")
    if volume_divergence:
        lines.append(f"- **{volume_divergence}**")
    lines.append("")

    # Section B
    lines.append("## B — Today vs History")
    lines.append("")
    lines.append(f"Historical rows available: {history.get('history_count', 0)}")
    lines.append(f"- Sentiment: {rank_text('sentiment', history.get('sentiment_rank'))}")
    lines.append(f"- Net GEX: {rank_text('net_gex', history.get('net_gex_rank'))}")
    lines.append(f"- Key Absolute: {rank_text('key_absolute', history.get('key_absolute_rank'))}")
    lines.append(f"- Key Dominance: {rank_text('dominance', history.get('dominance_rank'))}")
    if history.get("prev_key_strike"):
        lines.append(f"- Previous session ({history['prev_date']}) key strike: {history['prev_key_strike']}")
    lines.append("")

    # Section C
    lines.append("## C — ML Enrichment")
    lines.append("")
    if ml.get("vol_regime"):
        vr = ml["vol_regime"]
        lines.append(f"- **Vol Regime:** {vr.get('label')} (confidence {vr.get('proba', 0):.2%})")
    if ml.get("direction"):
        dr = ml["direction"]
        lines.append(f"- **Direction:** {dr.get('label')} (confidence {dr.get('proba', 0):.2%})")
    if ml.get("rf_outcome"):
        rf = ml["rf_outcome"]
        lines.append(f"- **RF Outcome:** {rf.get('prediction')} (probability {rf.get('probability', 0):.2%})")
    if ml.get("hmm_label"):
        lines.append(f"- **HMM Regime:** {ml['hmm_label']}")
    fb = ml.get("feedback") or {}
    if fb:
        lines.append("- **Feedback Loop Features:**")
        for k, v in list(fb.items())[:6]:
            lines.append(f"  - {k}: {v}")
    lines.append("")

    # Section D
    lines.append("## D — Trade Logic & Invalidation")
    lines.append("")
    if primary_setup == "PUT_PILLAR":
        lines.append(
            f"**Put Pillar:** Short put spread at/just below {summary['key_strike']}. "
            f"Invalidates if price breaks {summary['key_strike']} with momentum and holds below."
        )
    elif primary_setup == "CALL_WALL":
        lines.append(
            f"**Call Wall:** Short call spread at/just above {summary['key_strike']}. "
            f"Invalidates if price breaks {summary['key_strike']} on strong volume and holds above."
        )
    elif primary_setup == "PIN":
        lines.append(
            f"**Pin/Magnet:** Short iron butterfly at {summary['key_strike']}. "
            f"Requires price within ~5 pts of key; invalidates on a clean break of {summary.get('key2_strike', 'key2')}."
        )
    elif primary_setup == "NEG_GAMMA":
        lines.append("**No short premium:** Negative gamma environment — avoid selling premium.")
    elif primary_setup == "GEX_SLIDE":
        lines.append("**No trade:** Gamma is distributed; wait for KCS > 12 and dominance > 10%.")
    elif primary_setup == "POS_GAMMA":
        lines.append("**Mean-reversion bias:** Positive gamma stabilises price around key strikes.")
    else:
        lines.append("**No trade:** No clear gamma-driven edge at this snapshot.")
    lines.append("")

    # Section E
    lines.append("## E — Caution Notes")
    lines.append("")
    lines.append("- Check tomorrow's GEX profile before pinning / iron butterfly theses.")
    lines.append("- Verify economic calendar for FOMC, CPI, or other binary events.")
    lines.append("- On monthly expiration / triple witching / end-of-quarter days, GEX signals are less reliable.")
    if ml.get("rf_outcome", {}).get("prediction") == "LOSS":
        lines.append("- **RF outcome model predicts LOSS — extra caution on any short-premium trade.**")
    lines.append("")

    # Section F — Full OI / Volume Structure (mirrors GEX page strike table)
    lines.append("## F — OI & Volume Structure (Top Strikes)")
    lines.append("")
    if top_oi_rows:
        lines.append("| Strike | Char | Call OI | Put OI | Total OI | Call Vol | Put Vol | Abs GEX | Notes |")
        lines.append("|--------|------|---------|--------|----------|----------|---------|---------|-------|")
        price = summary.get("last", 0)
        for r in top_oi_rows[:10]:
            char = _get_oi_character(r, price)
            note = ""
            if r["strike"] == summary.get("key_strike"):
                note = "KEY"
            elif r["strike"] == summary.get("key2_strike"):
                note = "KEY2"
            lines.append(
                f"| {r['strike']} | {char} | {r.get('call_oi', 0):,} | {r.get('put_oi', 0):,} | {r.get('oi', 0):,} "
                f"| {r.get('call_vol', 0):,} | {r.get('put_vol', 0):,} | {fmt_billions(r.get('abs_gex', 0))} | {note} |"
            )
        if oi_sandwich:
            lines.append("")
            lines.append(f"- **{oi_sandwich}**")
    else:
        lines.append("- No strike-level data available.")
    lines.append("")

    # Section G — Percentile Context (same mini-bars as GEX page)
    lines.append("## G — Percentile Context (vs History)")
    lines.append("")
    if percentile_context:
        lines.append(f"- **Sample:** {percentile_context.get('sample_size', 0)} historical days at time {percentile_context.get('ntime_used', 'N/A')}")
        lines.append(f"- **Net GEX:** {pct_text('net_gex')}")
        lines.append(f"- **Call GEX:** {pct_text('total_call_gex')}")
        lines.append(f"- **Put GEX:** {pct_text('total_put_gex')}")
        lines.append(f"- **Call OI:** {pct_text('total_call_oi')}")
        lines.append(f"- **Put OI:** {pct_text('total_put_oi')}")
        lines.append(f"- **Call Volume:** {pct_text('total_call_vol')}")
        lines.append(f"- **Put Volume:** {pct_text('total_put_vol')}")
        lines.append(f"- **KCS:** {pct_text('kcs')}")
        lines.append(f"- **Dominance:** {pct_text('dominance')}")
    else:
        lines.append("- Percentile context not available.")
    lines.append("")

    # Section H — Live Trade Signal (same as GEX page)
    lines.append("## H — Live Trade Signal")
    lines.append("")
    if trade_signal:
        lines.append(f"- **Setup Type:** {trade_signal.get('setup_type', 'N/A')}")
        lines.append(f"- **Action:** {trade_signal.get('action', 'N/A')}")
        lines.append(f"- **Structure:** {trade_signal.get('structure', 'N/A')}")
        if trade_signal.get("short_strike"):
            lines.append(f"- **Short Strike:** {trade_signal['short_strike']}")
        if trade_signal.get("wing_strike"):
            lines.append(f"- **Wing Strike:** {trade_signal['wing_strike']}")
        if trade_signal.get("short_strike2"):
            lines.append(f"- **Short Strike 2:** {trade_signal['short_strike2']}")
        if trade_signal.get("wing_strike2"):
            lines.append(f"- **Wing Strike 2:** {trade_signal['wing_strike2']}")
        if trade_signal.get("rationale"):
            lines.append(f"- **Rationale:** {trade_signal['rationale']}")
        if trade_signal.get("invalidation"):
            lines.append(f"- **Invalidation:** {trade_signal['invalidation']}")
        if trade_signal.get("caution"):
            lines.append(f"- **Caution:** {trade_signal['caution']}")
        if trade_signal.get("prev_outcome"):
            lines.append(f"- **Previous Outcome:** {trade_signal['prev_outcome']}")
    else:
        lines.append("- Trade signal not available for this snapshot.")
    lines.append("")

    # Section I — Lessons from Gex teaching files
    lines.extend(_build_lessons_section(primary_setup, summary, trade_signal))

    # Section J — OHLC
    lines.append("## J — OHLC")
    lines.append("")
    if ohlc:
        lines.append(f"- Open: {ohlc.get('open')} | High: {ohlc.get('high')} | Low: {ohlc.get('low')} | Close: {ohlc.get('close')}")
    else:
        lines.append("- OHLC not available from Yahoo Finance for this date.")
    lines.append("")

    return "\n".join(lines)


@app.route("/api/daily-analysis/report")
def api_daily_analysis_report():
    """Return the concise daily analysis report for a selected date.

    Query params:
        date: YYYY-MM-DD (required)

    Behavior:
        1. If an existing analysis-concise-YYYYMMDD-*.md file exists, return it.
        2. Otherwise, if gex_strike_window has a snapshot for the date, generate
           the report from the latest snapshot, save it, and return it.
        3. If no snapshot exists, return a no-data message.
    """
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"status": "error", "message": "date parameter required"}), 400

    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        ndate = int(dt.strftime("%Y%m%d"))
    except ValueError:
        return jsonify({"status": "error", "message": "date must be YYYY-MM-DD"}), 400

    # 1. Check for existing report
    existing = _find_existing_analysis_report(ndate)
    if existing:
        return jsonify({
            "status": "ok",
            "source": "cached",
            "path": str(existing),
            "content": existing.read_text(encoding="utf-8"),
        })

    # 2. Find latest snapshot for this date in gex_strike_window
    with _db() as con:
        row = con.execute(
            "SELECT ndate, ntime, price, data FROM gex_strike_window "
            "WHERE ndate=? AND symbol='SPX' AND source='gex' "
            "ORDER BY ntime DESC LIMIT 1",
            (ndate,),
        ).fetchone()

    if not row:
        return jsonify({
            "status": "no_data",
            "message": f"No live snapshot available for {date_iso}. "
                       f"Run optionalpha_daily.py to capture data first."
        }), 404

    ndate, ntime, uprice, data_json = row
    try:
        strikes = json.loads(data_json) if data_json else []
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to parse strike data: {e}"}), 500

    if not strikes or uprice is None:
        return jsonify({"status": "error", "message": "Snapshot has no strike data"}), 500

    # 3. Build summary, context, ML enrichment, OHLC
    summary = _compute_concise_summary_from_strikes(strikes, uprice, ndate, ntime)
    if not summary:
        return jsonify({"status": "error", "message": "Failed to compute GEX summary"}), 500

    history = _get_historical_context(summary)
    ohlc = _fetch_yahoo_ohlc_for_date(date_iso)

    # Top OI rows for OI sandwich / structure analysis
    def v(r, k):
        return r.get(k, 0) or 0

    top_oi_rows = sorted(strikes, key=lambda r: v(r, "coi") + v(r, "poi"), reverse=True)[:10]
    top_oi_rows = [
        {
            "strike": v(r, "strike"),
            "call_oi": v(r, "coi"),
            "put_oi": v(r, "poi"),
            "oi": v(r, "coi") + v(r, "poi"),
            "call_vol": v(r, "cvol"),
            "put_vol": v(r, "pvol"),
            "abs_gex": v(r, "abs"),
        }
        for r in top_oi_rows
    ]

    ml = _get_ml_enrichment(strikes, uprice, ndate, ntime, summary)

    # 4. Percentile context (same as GEX page percentile mini-bars)
    percentile_stats = {
        "net_gex": summary.get("net_gex"),
        "total_call_gex": summary.get("total_call_gex"),
        "total_put_gex": abs(summary.get("total_put_gex", 0)),
        "total_call_oi": summary.get("total_call_oi"),
        "total_put_oi": summary.get("total_put_oi"),
        "total_call_vol": summary.get("total_call_vol"),
        "total_put_vol": summary.get("total_put_vol"),
        "kcs": summary.get("kcs"),
        "dominance": summary.get("key_dominance_pct"),
    }
    percentile_context = _get_percentile_context_for_snapshot(ndate, ntime, percentile_stats)

    # 5. Trade signal (same pipeline as GEX page)
    trade_signal = _get_trade_signal_for_snapshot(ndate, ntime, summary, ml)

    # 6. Build and save report
    content = _build_daily_analysis_report(
        summary, ohlc, history, ml, top_oi_rows, percentile_context, trade_signal
    )
    saved_path = _save_analysis_report(ndate, ntime, content)

    return jsonify({
        "status": "ok",
        "source": "generated",
        "path": str(saved_path),
        "content": content,
    })


# =============================================================================


def _ensure_spx_open_prices_table() -> None:
    """Create spx_open_prices table for manually entered daily open prices."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS spx_open_prices (
                ndate       INTEGER PRIMARY KEY,
                open_price  REAL NOT NULL,
                set_ts      TEXT NOT NULL
            )
        """)


def _populate_spx_open_prices_from_csv() -> dict:
    """Fill spx_open_prices from the 09:30 open price in the SPX CSV file.

    Uses INSERT OR IGNORE so manually entered prices are never overwritten.
    Returns {"inserted": N, "errors": N}.
    """
    inserted = 0
    errors = 0
    from zoneinfo import ZoneInfo
    csv_path = BASE_DIR / "spx-5min.csv"
    if not csv_path.exists():
        return {"inserted": 0, "errors": 0, "reason": "CSV not found"}
    try:
        df = pd.read_csv(csv_path, thousands=",")
    except Exception as e:
        return {"inserted": 0, "errors": 1, "reason": str(e)}

    # The CSV Date column is MM/DD/YYYY and Time is HH:MM.
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df["Time"] = pd.to_datetime(df["Time"], format="%H:%M", errors="coerce").dt.time
    df = df.dropna(subset=["Date", "Time"])

    # 09:30 is the market open; its Open value is the daily official open.
    open_rows = df[df["Time"] == pd.to_datetime("09:30").time()]
    set_ts = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%dT%H:%M:%S")
    with _db() as con:
        for _, row in open_rows.iterrows():
            try:
                ndate = int(row["Date"].strftime("%Y%m%d"))
                open_price = float(row["Open"])
                con.execute(
                    "INSERT OR IGNORE INTO spx_open_prices (ndate, open_price, set_ts) VALUES (?, ?, ?)",
                    (ndate, open_price, set_ts),
                )
                if con.total_changes:
                    inserted += 1
            except Exception:
                errors += 1
    return {"inserted": inserted, "errors": errors}


@app.route("/api/spx/populate-open-prices")
def api_populate_spx_open_prices():
    """Trigger population of spx_open_prices from the CSV file."""
    result = _populate_spx_open_prices_from_csv()
    return jsonify(result)


def _ensure_hmm_tables() -> None:
    """Create hmm_model table and add hmm columns to snapshot."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS hmm_model (
                id          INTEGER PRIMARY KEY CHECK (id=1),
                trained_at  TEXT NOT NULL,
                n_samples   INTEGER NOT NULL,
                n_states    INTEGER NOT NULL,
                features    TEXT NOT NULL,
                state_labels TEXT NOT NULL,
                model_blob  BLOB NOT NULL
            )
        """)
        # REMOVED: snapshot table no longer exists
        # caps = [r[1] for r in con.execute("PRAGMA table_info(snapshot)").fetchall()]
        # if "hmm_state" not in caps:
        #     con.execute("ALTER TABLE snapshot ADD COLUMN hmm_state INTEGER")
        # if "hmm_label" not in caps:
        #     con.execute("ALTER TABLE snapshot ADD COLUMN hmm_label TEXT")


# HMM feature set (5 features covering the 5 independent PCA dimensions)
HMM_FEATURES = ["net_gex", "kcs", "sentiment_pct", "dist_to_key", "total_put_vol"]
HMM_N_STATES = 4


def _build_hmm_matrix() -> tuple:
    """Collect all RTH snapshots and build a normalised feature matrix.

    Reads from gex_strike_window table and calculates metrics on-the-fly.

    Returns (X_scaled, scaler, raw_df) or (None, None, None) if insufficient data.
    """
    import numpy as np
    import pandas as pd
    import json
    from sklearn.preprocessing import StandardScaler
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_net_gex,
        calculate_kcs,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
    )

    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, symbol, source, price, data "
            "FROM gex_strike_window "
            "WHERE symbol='SPX' AND source='gex' AND ntime>=930 "
            "ORDER BY ndate, ntime"
        ).fetchall()

    records = []
    for row in rows:
        ndate, ntime, symbol, source, uprice, data_json = row
        
        if not uprice or not data_json:
            continue
        
        try:
            strikes = json.loads(data_json)
        except:
            continue
        
        if not strikes:
            continue
        
        # Calculate HMM features using gex_calculations module
        sentiment = calculate_sentiment(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, uprice)
        key_stats = calculate_key_strike_stats(strikes, uprice)
        total_oi_vol = calculate_total_oi_and_vol(strikes)
        
        # Calculate distance feature
        key_strike = key_stats["key_strike"] or uprice
        dist_to_key = abs(uprice - key_strike)
        
        records.append({
            "net_gex":       net_gex / 1e9,
            "kcs":           kcs,
            "sentiment_pct": sentiment,
            "dist_to_key":   dist_to_key,
            "total_put_vol": total_oi_vol["total_put_vol"] / 1e3,
        })

    if len(records) < 20:
        return None, None, None

    df = pd.DataFrame(records)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[HMM_FEATURES].values)
    return X_scaled, scaler, df


def _label_hmm_states(model, scaler) -> list:
    """Auto-label the 4 HMM states by inspecting their mean net_gex emission.

    Returns a list of 4 label strings indexed by state number.
    """
    import numpy as np
    # Inverse-transform the means to get interpretable values
    means_scaled = model.means_          # shape (n_states, n_features)
    means_raw = scaler.inverse_transform(means_scaled)
    # net_gex is feature index 0, kcs is index 1
    net_gex_means = means_raw[:, 0]      # in billions
    kcs_means     = means_raw[:, 1]

    # Sort states by net_gex mean descending
    order = np.argsort(net_gex_means)[::-1]  # highest to lowest
    labels = [""] * HMM_N_STATES
    tier_names = [
        "Positive Stable",    # highest net_gex
        "Positive Weakening", # second
        "Negative Trending",  # third
        "Negative Volatile",  # lowest net_gex
    ]
    for tier, state_idx in enumerate(order):
        labels[state_idx] = tier_names[tier]
    return labels


def _train_hmm(force: bool = False) -> dict:
    """Train a GaussianHMM on all historical RTH GEX snapshots and persist to DB.

    Skips training if model is <7 days old unless force=True.
    Returns a summary dict with status and metrics.
    """
    import pickle, json
    import numpy as np
    from datetime import datetime, timezone, timedelta

    # Check if recent model exists
    if not force:
        with _db() as con:
            row = con.execute("SELECT trained_at, n_samples FROM hmm_model WHERE id=1").fetchone()
        if row:
            trained_at = datetime.fromisoformat(row[0])
            age_days = (datetime.now(timezone.utc) - trained_at).days
            if age_days < 7:
                return {"status": "skipped", "reason": f"model is {age_days}d old", "n_samples": row[1]}

    X_scaled, scaler, df = _build_hmm_matrix()
    if X_scaled is None:
        return {"status": "error", "reason": "insufficient data (<20 snapshots)"}

    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        return {"status": "error", "reason": "hmmlearn not installed — run: pip install hmmlearn"}

    model = GaussianHMM(
        n_components=HMM_N_STATES,
        covariance_type="full",
        n_iter=200,
        random_state=42,
        verbose=False,
    )
    model.fit(X_scaled)

    state_labels = _label_hmm_states(model, scaler)
    trained_at = datetime.now(timezone.utc).isoformat()

    blob = pickle.dumps({"model": model, "scaler": scaler})
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO hmm_model (id, trained_at, n_samples, n_states, features, state_labels, model_blob)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        """, (trained_at, len(X_scaled), HMM_N_STATES, json.dumps(HMM_FEATURES),
              json.dumps(state_labels), blob))

    # Regenerate stored HMM labels for all historical snapshots using the new model.
    hmm_backfill = _backfill_hmm_labels_for_snapshot()

    return {
        "status": "trained",
        "n_samples": len(X_scaled),
        "n_states": HMM_N_STATES,
        "state_labels": state_labels,
        "trained_at": trained_at,
        "trans_matrix": model.transmat_.tolist(),
        "hmm_backfill": hmm_backfill,
    }


def _compute_pca() -> dict:
    """Compute PCA over GEX data from gex_strike_window table.

    Returns explained variance, cumulative variance, per-component feature
    loadings, and the list of features used. Used to visualise the independent
    dimensions that drive the HMM feature selection.
    """
    import numpy as np
    import json
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_gex_ratio,
        calculate_net_gex,
        calculate_kcs,
        calculate_dominance,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
        calculate_total_gex,
        calculate_flip_level,
        calculate_raw_aggregates,
    )

    # Full feature set covering all raw aggregates, derived metrics, distance features
    # AND the trade signal feedback loop features used by the ML models.
    FEATURES = [
        # GEX
        "net_gex", "total_call_gex", "total_put_gex",
        # Regime / sentiment
        "sentiment", "gex_ratio",
        # Key strike derived
        "kcs", "dominance",
        "key_call_gex", "key_put_gex",
        "key_call_oi", "key_put_oi",
        "key_call_vol", "key_put_vol",
        # Secondary key
        "key2_abs", "key2_call_vol", "key2_put_vol",
        # Total OI / Vol
        "total_call_oi", "total_put_oi",
        "total_call_vol", "total_put_vol",
        # OI and Vol ratios (call/put imbalance)
        "oi_ratio", "vol_ratio",
        # Raw aggregates
        "pcmag", "cotm", "potm",
        # Distance features
        "dist_to_key", "dist_to_flip",
        # Trade Signal Feedback Loop Features
        "call_wall_success_rate_7d", "call_wall_success_rate_30d",
        "put_wall_success_rate_7d", "put_wall_success_rate_30d",
        "butterfly_success_rate_7d", "butterfly_success_rate_30d",
        "condor_success_rate_7d", "condor_success_rate_30d",
        "pillar_success_rate_7d", "pillar_success_rate_30d",
        "notrade_success_rate_7d", "notrade_success_rate_30d",
        "wall_strength_score", "signal_reliability_score",
        "recent_signal_performance_5", "recent_signal_performance_20",
        "high_volatility_regime", "trending_market", "choppy_market", "macro_event_risk",
    ]

    FEATURE_GROUPS = {
        "net_gex": "GEX", "total_call_gex": "GEX", "total_put_gex": "GEX",
        "sentiment": "Regime", "gex_ratio": "Regime",
        "kcs": "Key Strike", "dominance": "Key Strike",
        "key_call_gex": "Key Strike", "key_put_gex": "Key Strike",
        "key_call_oi": "Key Strike", "key_put_oi": "Key Strike",
        "key_call_vol": "Key Strike", "key_put_vol": "Key Strike",
        "key2_abs": "Key2", "key2_call_vol": "Key2", "key2_put_vol": "Key2",
        "total_call_oi": "OI/Vol", "total_put_oi": "OI/Vol",
        "total_call_vol": "OI/Vol", "total_put_vol": "OI/Vol",
        "oi_ratio": "OI/Vol", "vol_ratio": "OI/Vol",
        "pcmag": "Raw", "cotm": "Raw", "potm": "Raw",
        "dist_to_key": "Distance", "dist_to_flip": "Distance",
        "call_wall_success_rate_7d": "Feedback", "call_wall_success_rate_30d": "Feedback",
        "put_wall_success_rate_7d": "Feedback", "put_wall_success_rate_30d": "Feedback",
        "butterfly_success_rate_7d": "Feedback", "butterfly_success_rate_30d": "Feedback",
        "condor_success_rate_7d": "Feedback", "condor_success_rate_30d": "Feedback",
        "pillar_success_rate_7d": "Feedback", "pillar_success_rate_30d": "Feedback",
        "notrade_success_rate_7d": "Feedback", "notrade_success_rate_30d": "Feedback",
        "wall_strength_score": "Feedback", "signal_reliability_score": "Feedback",
        "recent_signal_performance_5": "Feedback", "recent_signal_performance_20": "Feedback",
        "high_volatility_regime": "Feedback", "trending_market": "Feedback",
        "choppy_market": "Feedback", "macro_event_risk": "Feedback",
    }

    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, symbol, source, price, data "
            "FROM gex_strike_window "
            "WHERE symbol='SPX' AND source='gex' AND ntime>=935 "
            "ORDER BY ndate, ntime"
        ).fetchall()
        
        # Load feedback features for all relevant snapshots
        feedback_rows = con.execute(
            "SELECT ndate, ntime, "
            "call_wall_success_rate_7d, call_wall_success_rate_30d, "
            "put_wall_success_rate_7d, put_wall_success_rate_30d, "
            "butterfly_success_rate_7d, butterfly_success_rate_30d, "
            "condor_success_rate_7d, condor_success_rate_30d, "
            "pillar_success_rate_7d, pillar_success_rate_30d, "
            "notrade_success_rate_7d, notrade_success_rate_30d, "
            "wall_strength_score, signal_reliability_score, "
            "recent_signal_performance_5, recent_signal_performance_20, "
            "high_volatility_regime, trending_market, choppy_market, macro_event_risk "
            "FROM trade_signal_features"
        ).fetchall()

    # Build feedback lookup
    feedback_lookup = {}
    for fb in feedback_rows:
        feedback_lookup[(fb[0], fb[1])] = fb[2:]

    feedback_cols = [
        "call_wall_success_rate_7d", "call_wall_success_rate_30d",
        "put_wall_success_rate_7d", "put_wall_success_rate_30d",
        "butterfly_success_rate_7d", "butterfly_success_rate_30d",
        "condor_success_rate_7d", "condor_success_rate_30d",
        "pillar_success_rate_7d", "pillar_success_rate_30d",
        "notrade_success_rate_7d", "notrade_success_rate_30d",
        "wall_strength_score", "signal_reliability_score",
        "recent_signal_performance_5", "recent_signal_performance_20",
        "high_volatility_regime", "trending_market", "choppy_market", "macro_event_risk",
    ]

    records = []
    for row in rows:
        ndate, ntime, symbol, source, uprice, data_json = row
        
        if not uprice or not data_json:
            continue
        
        try:
            strikes = json.loads(data_json)
        except:
            continue
        
        if not strikes:
            continue
        
        # Calculate all PCA features using gex_calculations module
        sentiment = calculate_sentiment(strikes)
        gex_ratio = calculate_gex_ratio(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, uprice)
        dominance = calculate_dominance(strikes, uprice)
        key_stats = calculate_key_strike_stats(strikes, uprice)
        total_oi_vol = calculate_total_oi_and_vol(strikes)
        total_gex_vals = calculate_total_gex(strikes)
        flip = calculate_flip_level(strikes)
        raw = calculate_raw_aggregates(strikes)

        # Distance features
        key_strike = key_stats["key_strike"] or uprice
        dist_to_key = abs(uprice - key_strike)
        dist_to_flip = abs(uprice - flip) if flip else 0

        # OI and Vol ratios (call/put imbalance — avoid div/0)
        tcoi = total_oi_vol["total_call_oi"] or 0
        tpoi = total_oi_vol["total_put_oi"] or 0
        tcvol = total_oi_vol["total_call_vol"] or 0
        tpvol = total_oi_vol["total_put_vol"] or 0
        oi_ratio = round(tcoi / tpoi, 4) if tpoi else 0
        vol_ratio = round(tcvol / tpvol, 4) if tpvol else 0

        # Base GEX-derived features
        record = {
            "net_gex": net_gex,
            "total_call_gex": total_gex_vals["total_call_gex"],
            "total_put_gex": total_gex_vals["total_put_gex"],
            "sentiment": sentiment,
            "gex_ratio": gex_ratio,
            "kcs": kcs,
            "dominance": dominance,
            "key_call_gex": key_stats["key_call_gex"],
            "key_put_gex": key_stats["key_put_gex"],
            "key_call_oi": key_stats["key_call_oi"],
            "key_put_oi": key_stats["key_put_oi"],
            "key_call_vol": key_stats["key_call_vol"],
            "key_put_vol": key_stats["key_put_vol"],
            "key2_abs": key_stats["key2_abs"],
            "key2_call_vol": key_stats["key2_call_vol"],
            "key2_put_vol": key_stats["key2_put_vol"],
            "total_call_oi": tcoi,
            "total_put_oi": tpoi,
            "total_call_vol": tcvol,
            "total_put_vol": tpvol,
            "oi_ratio": oi_ratio,
            "vol_ratio": vol_ratio,
            "pcmag": raw["pcmag"],
            "cotm": raw["cotm"],
            "potm": raw["potm"],
            "dist_to_key": dist_to_key,
            "dist_to_flip": dist_to_flip,
        }
        
        # Add feedback loop features if available
        fb_values = feedback_lookup.get((ndate, ntime))
        if fb_values:
            for col, val in zip(feedback_cols, fb_values):
                record[col] = val if val is not None else 0.0
        else:
            # Default values for missing feedback features
            for col in feedback_cols:
                if "_regime" in col or "_market" in col or col == "macro_event_risk":
                    record[col] = 0
                else:
                    record[col] = 0.5
        
        records.append(record)

    if len(records) < 5:
        return {"status": "error", "reason": "insufficient data (<5 snapshots)"}

    df = pd.DataFrame(records)[FEATURES].fillna(0)
    X_scaled = StandardScaler().fit_transform(df.values)

    n_components = min(len(FEATURES), len(records) - 1)
    pca = PCA(n_components=n_components)
    pca.fit(X_scaled)

    evr = pca.explained_variance_ratio_.tolist()
    cumulative = np.cumsum(pca.explained_variance_ratio_).tolist()
    components = pca.components_.tolist()

    # Build per-component top feature loadings
    component_details = []
    for i, comp in enumerate(components):
        loadings = sorted(zip(FEATURES, comp), key=lambda x: abs(x[1]), reverse=True)
        component_details.append({
            "pc": i + 1,
            "variance": evr[i],
            "cumulative": cumulative[i],
            "top_features": [{"feature": f, "loading": round(l, 3)} for f, l in loadings[:6]],
            "all_loadings": [{"feature": f, "loading": round(l, 4)} for f, l in zip(FEATURES, pca.components_[i])],
        })

    # Ranked feature importance (weighted loading across all significant PCs)
    n90 = next((i + 1 for i, c in enumerate(cumulative) if c >= 0.90), len(FEATURES))
    feature_importance = {f: 0.0 for f in FEATURES}
    for i in range(n90):
        for j, f in enumerate(FEATURES):
            feature_importance[f] += abs(pca.components_[i, j]) * evr[i]
    max_score = max(feature_importance.values()) or 1
    ranked_features = sorted([
        {
            "feature": f,
            "score": round(score, 4),
            "score_pct": round(score / max_score * 100, 1),
            "group": FEATURE_GROUPS.get(f, "Other"),
            "verdict": "HIGH" if score >= max_score * 0.5 else ("MODERATE" if score >= max_score * 0.25 else "LOW"),
        }
        for f, score in feature_importance.items()
    ], key=lambda x: -x["score"])

    # Correlation matrix (upper triangle, |r| > 0.7 only)
    # Replace NaN with 0 (constant/zero-variance features produce NaN correlation)
    corr = df.corr().round(3).fillna(0)
    high_corr = []
    for i in range(len(FEATURES)):
        for j in range(i + 1, len(FEATURES)):
            r = corr.iloc[i, j]
            if abs(r) > 0.7:
                high_corr.append({
                    "a": FEATURES[i], "b": FEATURES[j],
                    "r": round(r, 3),
                    "verdict": "DROP one" if abs(r) > 0.95 else ("REDUNDANT" if abs(r) > 0.85 else "HIGH"),
                })
    high_corr.sort(key=lambda x: -abs(x["r"]))

    # Full correlation matrix for heatmap
    corr_matrix = {
        "features": FEATURES,
        "values": corr.values.tolist(),
    }

    return {
        "status": "ok",
        "n_samples": len(records),
        "n_features": len(FEATURES),
        "features": FEATURES,
        "feature_groups": FEATURE_GROUPS,
        "hmm_features": HMM_FEATURES,
        "explained_variance_ratio": evr,
        "cumulative_variance": cumulative,
        "n90": n90,
        "components": component_details,
        "ranked_features": ranked_features,
        "high_correlations": high_corr,
        "correlation_matrix": corr_matrix,
    }


@app.route("/api/ml/latest-signal")
def api_ml_latest_signal():
    """Return the most recent ML prediction row for a given date (default: today).

    Used by the live page to restore the ML signal badge on page load / refresh.
    Query param: ?date=YYYY-MM-DD
    """
    from datetime import datetime
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        ndate = int(date_str.replace("-", ""))
    except ValueError:
        return jsonify({"error": "invalid date"}), 400

    with _db() as con:
        row = con.execute("""
            SELECT ndate, ntime, vol_regime_pred, vol_regime_proba,
                   direction_pred, direction_proba, trade_pred, trade_code, confidence
            FROM ml_predictions
            WHERE ndate=?
            ORDER BY ntime DESC
            LIMIT 1
        """, (ndate,)).fetchone()

    if not row:
        return jsonify({"signal": None})

    ndate, ntime, vol, vol_p, dirn, dir_p, trade, trade_code, conf = row

    # Rebuild viable_rate same way as _predict_snapshot
    viable_rate = None
    _tc_col = {"IC": "trade_viable_ic", "SPS": "trade_viable_sps", "SCS": "trade_viable_scs",
               "LCS": "trade_viable_lcs", "LPS": "trade_viable_lps"}.get(trade_code)
    if _tc_col:
        with _db() as con:
            r = con.execute(
                f"SELECT ROUND(AVG({_tc_col})*100,1) FROM ml_labels WHERE {_tc_col} IS NOT NULL"
            ).fetchone()
            viable_rate = r[0] if r else None

    dots = {"HIGH": "\u25cf\u25cf\u25cf", "MEDIUM": "\u25cf\u25cf\u25cb", "LOW": "\u25cf\u25cb\u25cb"}.get(conf, "\u25cf\u25cb\u25cb")
    signal_text = f"[{vol}] [{dirn}] \u2192 {trade} {dots}"

    return jsonify({
        "signal": {
            "ntime": ntime,
            "vol_regime": vol,
            "vol_regime_proba": vol_p,
            "direction": dirn,
            "direction_proba": dir_p,
            "trade": trade,
            "trade_code": trade_code,
            "confidence": conf,
            "viable_rate": viable_rate,
            "signal_text": signal_text,
        }
    })


@app.route("/api/ml/predictions")
def api_ml_predictions():
    """Return prediction history with outcomes. Query: limit=N (default 100)"""
    limit = min(int(request.args.get("limit", 200)), 500)
    with _db() as con:
        rows = con.execute("""
            SELECT ndate, ntime, predicted_at,
                   vol_regime_pred, vol_regime_proba, direction_pred, direction_proba,
                   trade_pred, trade_code, confidence,
                   vol_regime_actual, direction_1hr_actual, direction_2hr_actual,
                   direction_eod_actual, trade_viable_actual,
                   vol_correct, direction_1hr_correct, direction_2hr_correct,
                   outcome_filled_at
            FROM ml_predictions
            ORDER BY ndate DESC, ntime DESC
            LIMIT ?
        """, (limit,)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM ml_predictions").fetchone()[0]
        filled = con.execute("SELECT COUNT(*) FROM ml_predictions WHERE outcome_filled_at IS NOT NULL").fetchone()[0]
        # Accuracy stats
        stats = con.execute("""
            SELECT
                ROUND(AVG(vol_correct)*100,1) as vol_acc,
                ROUND(AVG(direction_1hr_correct)*100,1) as dir1_acc,
                ROUND(AVG(direction_2hr_correct)*100,1) as dir2_acc,
                ROUND(AVG(trade_viable_actual)*100,1) as trade_acc
            FROM ml_predictions WHERE outcome_filled_at IS NOT NULL
        """).fetchone()
    cols = ["ndate","ntime","predicted_at",
            "vol_regime_pred","vol_regime_proba","direction_pred","direction_proba",
            "trade_pred","trade_code","confidence",
            "vol_regime_actual","direction_1hr_actual","direction_2hr_actual",
            "direction_eod_actual","trade_viable_actual",
            "vol_correct","direction_1hr_correct","direction_2hr_correct",
            "outcome_filled_at"]
    return jsonify({
        "total": total, "filled": filled,
        "accuracy": {"vol_regime": stats[0], "direction_1hr": stats[1],
                     "direction_2hr": stats[2], "trade_viable": stats[3]},
        "predictions": [dict(zip(cols, r)) for r in rows],
    })


@app.route("/api/ml/backtest-accuracy")
def api_ml_backtest_accuracy():
    """Run the trained models over all labelled historical snapshots and return accuracy stats.

    Expensive first call (~5-10s); results are not cached — call once on tab load.
    """
    import numpy as np

    clf_v, scaler_v, _, _ = _load_ml_model("vol_regime")
    clf_d, scaler_d, _, _ = _load_ml_model("direction")
    if clf_v is None or clf_d is None:
        return jsonify({"error": "models not trained yet"}), 404

    with _db() as con:
        rows = con.execute("""
            SELECT g.ndate, g.ntime, g.price, g.data,
                   l.range_regime, l.direction_2hr,
                   l.trade_viable_ic, l.trade_viable_sps, l.trade_viable_scs,
                   l.trade_viable_lcs, l.trade_viable_lps,
                   l.pct_2hr, l.range_2hr
            FROM gex_strike_window g
            JOIN ml_labels l ON l.ndate=g.ndate AND l.ntime=g.ntime
            WHERE g.symbol='SPX' AND g.source='gex' AND g.ntime>=935
              AND l.range_regime IS NOT NULL AND l.direction_2hr IS NOT NULL
            ORDER BY g.ndate, g.ntime
        """).fetchall()

    if not rows:
        return jsonify({"error": "no labelled data"}), 404

    records = []
    X_list, y_vol, y_dir = [], [], []
    meta = []

    for row in rows:
        ndate, ntime, uprice, data_json, range_regime, dir_2hr, \
            tv_ic, tv_sps, tv_scs, tv_lcs, tv_lps, pct_2hr, range_2hr = row
        try:
            strikes = json.loads(data_json) if data_json else []
        except Exception:
            continue
        feats = _extract_gex_features(strikes, uprice, ndate=ndate)
        if feats is None:
            continue
        X_list.append([feats[f] for f in ML_FEATURES])
        y_vol.append("WIDE" if range_regime == "WIDE" else "TIGHT")
        y_dir.append(dir_2hr)
        meta.append({
            "ndate": ndate, "ntime": ntime,
            "tv_ic": tv_ic, "tv_sps": tv_sps, "tv_scs": tv_scs,
            "tv_lcs": tv_lcs, "tv_lps": tv_lps,
            "pct_2hr": pct_2hr, "range_2hr": range_2hr,
        })

    X = np.nan_to_num(np.array(X_list, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    X_v = scaler_v.transform(X)
    X_d = scaler_d.transform(X)

    preds_vol = clf_v.predict(X_v).tolist()
    preds_dir = clf_d.predict(X_d).tolist()
    proba_vol = clf_v.predict_proba(X_v).max(axis=1).tolist()
    proba_dir = clf_d.predict_proba(X_d).max(axis=1).tolist()

    _TV_MAP = {"IC": "tv_ic", "IB": "tv_ic", "SPS": "tv_sps",
               "SCS": "tv_scs", "LCS": "tv_lcs", "LPS": "tv_lps"}

    # Build per-row result and aggregate stats
    vol_correct, dir_correct, trade_viable_list = [], [], []
    by_date = {}
    detail_rows = []

    for i, m in enumerate(meta):
        pv = preds_vol[i]; pd_ = preds_dir[i]
        trade, trade_code = _TRADE_MATRIX.get((pv, pd_), ("No signal", "---"))
        min_conf = min(proba_vol[i], proba_dir[i])
        confidence = "HIGH" if min_conf >= 0.65 else ("MEDIUM" if min_conf >= 0.45 else "LOW")

        vc = 1 if pv == y_vol[i] else 0
        dc = 1 if pd_ == y_dir[i] else 0
        tv_col = _TV_MAP.get(trade_code)
        tv = m.get(tv_col) if tv_col else None

        vol_correct.append(vc)
        dir_correct.append(dc)
        if tv is not None:
            trade_viable_list.append(tv)

        nd = str(m["ndate"])
        date_iso = f"{nd[:4]}-{nd[4:6]}-{nd[6:]}"
        by_date.setdefault(date_iso, {"vc": [], "dc": [], "tv": []})
        by_date[date_iso]["vc"].append(vc)
        by_date[date_iso]["dc"].append(dc)
        if tv is not None:
            by_date[date_iso]["tv"].append(tv)

        detail_rows.append({
            "date": date_iso,
            "time": m["ntime"],
            "vol_pred": pv, "vol_actual": y_vol[i], "vol_correct": vc,
            "dir_pred": pd_, "dir_actual": y_dir[i], "dir_correct": dc,
            "trade": trade, "trade_code": trade_code,
            "trade_viable": tv, "confidence": confidence,
            "pct_2hr": round(m["pct_2hr"], 3) if m["pct_2hr"] else None,
        })

    # Daily accuracy series for chart
    daily = sorted([{
        "date": d,
        "vol_acc": round(sum(v["vc"]) / len(v["vc"]) * 100, 1),
        "dir_acc": round(sum(v["dc"]) / len(v["dc"]) * 100, 1),
        "trade_viable_pct": round(sum(v["tv"]) / len(v["tv"]) * 100, 1) if v["tv"] else None,
        "n": len(v["vc"]),
    } for d, v in by_date.items()], key=lambda x: x["date"])

    # Confusion matrices
    vol_classes = sorted(set(y_vol))
    dir_classes = sorted(set(y_dir))

    def confusion(y_true, y_pred, classes):
        m = {c: {c2: 0 for c2 in classes} for c in classes}
        for t, p in zip(y_true, y_pred):
            if t in m and p in m[t]:
                m[t][p] += 1
        return {"classes": classes, "matrix": [[m[r][c] for c in classes] for r in classes]}

    return jsonify({
        "n_samples": len(meta),
        "overall": {
            "vol_accuracy": round(sum(vol_correct) / len(vol_correct) * 100, 1),
            "dir_accuracy": round(sum(dir_correct) / len(dir_correct) * 100, 1),
            "trade_viable_pct": round(sum(trade_viable_list) / len(trade_viable_list) * 100, 1) if trade_viable_list else None,
        },
        "vol_confusion": confusion(y_vol, preds_vol, vol_classes),
        "dir_confusion": confusion(y_dir, preds_dir, dir_classes),
        "daily_series": daily,
        "detail": detail_rows[-200:],  # last 200 rows for table
    })


@app.route("/api/ml/anomaly")
def api_ml_anomaly():
    """PCA-based anomaly detection over all historical GEX snapshots.

    Fits PCA on the full historical feature matrix, then computes the
    reconstruction error (MSE) for every snapshot. High reconstruction error
    = the day's GEX structure is unusual vs the historical distribution.

    Returns:
      - scores: [{date, time, error, z_score, label}] for every snapshot
      - thresholds: z-score cutoffs for UNUSUAL / EXTREME
      - today: latest snapshot score if available
    """
    import numpy as np
    import json as _json
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from controllers.gex_calculations import (
        calculate_sentiment, calculate_gex_ratio, calculate_net_gex,
        calculate_kcs, calculate_dominance, calculate_key_strike_stats,
        calculate_total_oi_and_vol, calculate_total_gex,
        calculate_flip_level, calculate_raw_aggregates,
    )

    FEATURES = [
        "net_gex", "total_call_gex", "total_put_gex",
        "sentiment", "gex_ratio", "kcs", "dominance",
        "key_call_gex", "key_put_gex", "key_call_oi", "key_put_oi",
        "key_call_vol", "key_put_vol", "key2_abs", "key2_call_vol", "key2_put_vol",
        "total_call_oi", "total_put_oi", "total_call_vol", "total_put_vol",
        "oi_ratio", "vol_ratio", "pcmag", "cotm", "potm",
        "dist_to_key", "dist_to_flip",
    ]

    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, price, data FROM gex_strike_window "
            "WHERE symbol='SPX' AND source='gex' AND ntime>=935 "
            "ORDER BY ndate, ntime"
        ).fetchall()

    if len(rows) < 10:
        return jsonify({"error": "insufficient data (<10 snapshots)"}), 404

    meta, X_list = [], []
    for ndate, ntime, uprice, data_json in rows:
        if not uprice or not data_json:
            continue
        try:
            strikes = _json.loads(data_json)
        except Exception:
            continue
        if not strikes:
            continue

        sentiment   = calculate_sentiment(strikes)
        gex_ratio   = calculate_gex_ratio(strikes)
        net_gex     = calculate_net_gex(strikes)
        kcs         = calculate_kcs(strikes, uprice)
        dominance   = calculate_dominance(strikes, uprice)
        key_stats   = calculate_key_strike_stats(strikes, uprice)
        total_oi_vol= calculate_total_oi_and_vol(strikes)
        total_gex_v = calculate_total_gex(strikes)
        flip        = calculate_flip_level(strikes)
        raw         = calculate_raw_aggregates(strikes)
        key_strike  = key_stats["key_strike"] or uprice
        tcoi = total_oi_vol["total_call_oi"] or 0
        tpoi = total_oi_vol["total_put_oi"] or 0
        tcvol= total_oi_vol["total_call_vol"] or 0
        tpvol= total_oi_vol["total_put_vol"] or 0

        vec = [
            net_gex, total_gex_v["total_call_gex"], total_gex_v["total_put_gex"],
            sentiment, gex_ratio, kcs, dominance,
            key_stats["key_call_gex"], key_stats["key_put_gex"],
            key_stats["key_call_oi"],  key_stats["key_put_oi"],
            key_stats["key_call_vol"], key_stats["key_put_vol"],
            key_stats["key2_abs"], key_stats["key2_call_vol"], key_stats["key2_put_vol"],
            tcoi, tpoi, tcvol, tpvol,
            (tcoi/tpoi if tpoi else 0), (tcvol/tpvol if tpvol else 0),
            raw["pcmag"], raw["cotm"], raw["potm"],
            abs(uprice - key_strike), (abs(uprice - flip) if flip else 0),
        ]
        X_list.append(vec)
        nd = str(ndate)
        meta.append({"date": f"{nd[:4]}-{nd[4:6]}-{nd[6:]}", "time": ntime})

    X = np.nan_to_num(np.array(X_list, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit PCA retaining 95% variance
    pca = PCA(n_components=0.95, svd_solver="full")
    pca.fit(X_scaled)
    n_comp = pca.n_components_

    # Reconstruction error = MSE between original and PCA-reconstructed
    X_proj  = pca.transform(X_scaled)
    X_recon = pca.inverse_transform(X_proj)
    errors  = np.mean((X_scaled - X_recon) ** 2, axis=1)

    mu, sigma = float(errors.mean()), float(errors.std())
    z_scores = ((errors - mu) / sigma).tolist()
    errors   = errors.tolist()

    THRESH_UNUSUAL = 2.0
    THRESH_EXTREME = 3.0

    def label(z):
        if z >= THRESH_EXTREME: return "EXTREME"
        if z >= THRESH_UNUSUAL: return "UNUSUAL"
        return "NORMAL"

    scores = []
    for i, m in enumerate(meta):
        scores.append({
            "date":    m["date"],
            "time":    m["time"],
            "error":   round(errors[i], 5),
            "z_score": round(z_scores[i], 2),
            "label":   label(z_scores[i]),
        })

    # Aggregate to daily: use max z_score per day
    by_date = {}
    for s in scores:
        d = s["date"]
        if d not in by_date or s["z_score"] > by_date[d]["z_score"]:
            by_date[d] = s

    daily = sorted(by_date.values(), key=lambda x: x["date"])

    # Most recent snapshot = "today"
    today = scores[-1] if scores else None

    # Top 10 most anomalous snapshots
    top_anomalies = sorted(scores, key=lambda x: x["z_score"], reverse=True)[:10]

    return jsonify({
        "n_snapshots":    len(scores),
        "n_components":   int(n_comp),
        "variance_kept":  round(float(pca.explained_variance_ratio_.sum()), 3),
        "thresholds":     {"unusual": THRESH_UNUSUAL, "extreme": THRESH_EXTREME},
        "scores":         scores,
        "daily":          daily,
        "today":          today,
        "top_anomalies":  top_anomalies,
    })


@app.route("/api/ml/trade-performance")
def api_ml_trade_performance():
    """Return historical trade performance metrics.

    Query params:
        days: number of recent days to return (default 30)

    Returns:
        List of performance records with metrics by date
    """
    days = int(request.args.get("days", 30))

    with _db() as con:
        rows = con.execute("""
            SELECT
                ndate, model_version, training_date, force_retrain,
                total_predictions, high_conf_predictions, medium_conf_predictions, low_conf_predictions,
                trade_correct, trade_incorrect, trade_neutral,
                ic_correct, ic_total, sps_correct, sps_total, scs_correct, scs_total,
                lcs_correct, lcs_total, lps_correct, lps_total,
                high_conf_accuracy, medium_conf_accuracy,
                total_outcome_points, avg_outcome_points, max_drawdown,
                vol_regime_correct, vol_regime_total, vol_regime_accuracy,
                direction_2hr_correct, direction_2hr_total, direction_2hr_accuracy,
                computed_at
            FROM ml_trade_performance
            ORDER BY ndate DESC
            LIMIT ?
        """, (days,)).fetchall()

    cols = ["ndate", "model_version", "training_date", "force_retrain",
            "total_predictions", "high_conf_predictions", "medium_conf_predictions", "low_conf_predictions",
            "trade_correct", "trade_incorrect", "trade_neutral",
            "ic_correct", "ic_total", "sps_correct", "sps_total", "scs_correct", "scs_total",
            "lcs_correct", "lcs_total", "lps_correct", "lps_total",
            "high_conf_accuracy", "medium_conf_accuracy",
            "total_outcome_points", "avg_outcome_points", "max_drawdown",
            "vol_regime_correct", "vol_regime_total", "vol_regime_accuracy",
            "direction_2hr_correct", "direction_2hr_total", "direction_2hr_accuracy",
            "computed_at"]

    performance = [dict(zip(cols, r)) for r in rows]

    return jsonify({
        "success": True,
        "data": performance,
        "count": len(performance)
    })


@app.route("/api/trade-signals/performance")
def api_trade_signals_performance():
    """Return trade signals performance metrics.

    Returns:
        Overall stats, performance by structure, financial performance, win rate by action
    """
    with _db() as con:
        # Overall stats
        overall = con.execute("SELECT COUNT(*) FROM trade_signals").fetchone()[0]
        
        # Outcome distribution
        outcomes = con.execute("""
            SELECT outcome, COUNT(*) 
            FROM trade_signals 
            GROUP BY outcome
        """).fetchall()
        
        # Performance by structure
        structure_perf = con.execute("""
            SELECT structure, outcome, COUNT(*) 
            FROM trade_signals 
            WHERE outcome IS NOT NULL 
            GROUP BY structure, outcome
            ORDER BY structure, outcome
        """).fetchall()
        
        # Financial performance
        financial = con.execute("""
            SELECT action, SUM(outcome_points), AVG(outcome_points), COUNT(*) 
            FROM trade_signals 
            WHERE outcome_points IS NOT NULL 
            GROUP BY action
        """).fetchall()
        
        # Win rate by action
        win_rates = con.execute("""
            SELECT action, 
                   SUM(CASE WHEN outcome IN ('WIN', 'CORRECT', 'PARTIAL') THEN 1 ELSE 0 END) as wins,
                   COUNT(*) as total
            FROM trade_signals 
            WHERE outcome IS NOT NULL 
            GROUP BY action
        """).fetchall()
    
    return jsonify({
        "total_signals": overall,
        "outcomes": [{"outcome": o, "count": c} for o, c in outcomes],
        "structure_performance": [{"structure": s, "outcome": o, "count": c} for s, o, c in structure_perf],
        "financial": [{"action": a, "total_points": tp, "avg_points": ap, "trades": t} for a, tp, ap, t in financial],
        "win_rates": [{"action": a, "wins": w, "total": t, "win_rate": round(w/t*100, 1) if t > 0 else 0} for a, w, t in win_rates]
    })

@app.route("/api/ml/trade-performance-summary")
def api_ml_trade_performance_summary():
    """Return summary of trade performance metrics.

    Returns:
        Latest performance record + aggregated stats over all time
    """
    with _db() as con:
        # Get latest performance record
        latest = con.execute("""
            SELECT * FROM ml_trade_performance
            ORDER BY ndate DESC LIMIT 1
        """).fetchone()

        # Get aggregated stats
        agg = con.execute("""
            SELECT
                COUNT(*) as total_days,
                SUM(total_predictions) as total_predictions,
                SUM(trade_correct) as total_correct,
                SUM(trade_incorrect) as total_incorrect,
                AVG(trade_correct * 1.0 / NULLIF(trade_correct + trade_incorrect, 0)) as avg_accuracy,
                SUM(total_outcome_points) as total_points,
                AVG(avg_outcome_points) as avg_daily_points
            FROM ml_trade_performance
        """).fetchone()

    cols = ["id", "ndate", "model_version", "training_date", "force_retrain",
            "total_predictions", "high_conf_predictions", "medium_conf_predictions", "low_conf_predictions",
            "trade_correct", "trade_incorrect", "trade_neutral",
            "ic_correct", "ic_total", "sps_correct", "sps_total", "scs_correct", "scs_total",
            "lcs_correct", "lcs_total", "lps_correct", "lps_total",
            "high_conf_accuracy", "medium_conf_accuracy",
            "total_outcome_points", "avg_outcome_points", "max_drawdown",
            "vol_regime_correct", "vol_regime_total", "vol_regime_accuracy",
            "direction_2hr_correct", "direction_2hr_total", "direction_2hr_accuracy",
            "computed_at"]

    latest_dict = dict(zip(cols, latest)) if latest else None

    agg_dict = {
        "total_days": agg[0],
        "total_predictions": agg[1],
        "total_correct": agg[2],
        "total_incorrect": agg[3],
        "avg_accuracy": round(agg[4], 4) if agg[4] else None,
        "total_points": round(agg[5], 2) if agg[5] else None,
        "avg_daily_points": round(agg[6], 2) if agg[6] else None
    }

    return jsonify({
        "success": True,
        "latest": latest_dict,
        "aggregated": agg_dict
    })


@app.route("/api/ml/model-versions")
def api_ml_model_versions():
    """Return list of model versions with their performance metrics.

    Returns:
        List of unique model versions with their performance summary
    """
    with _db() as con:
        rows = con.execute("""
            SELECT
                model_version,
                training_date,
                COUNT(*) as days_used,
                AVG(trade_correct * 1.0 / NULLIF(trade_correct + trade_incorrect, 0)) as avg_accuracy,
                SUM(total_outcome_points) as total_points,
                MIN(ndate) as first_used,
                MAX(ndate) as last_used
            FROM ml_trade_performance
            GROUP BY model_version, training_date
            ORDER BY first_used DESC
        """).fetchall()

    cols = ["model_version", "training_date", "days_used", "avg_accuracy", "total_points", "first_used", "last_used"]
    versions = [dict(zip(cols, r)) for r in rows]

    return jsonify({
        "success": True,
        "versions": versions,
        "count": len(versions)
    })


@app.route("/api/ml/session-range")
def api_ml_session_range():
    """Session Range Forecast: given today's vol regime + direction, return historical
    distribution of 2hr and EOD ranges, plus key/flip strike levels for strike selection.

    Query params:
        date: YYYY-MM-DD (default today)
        time: HHMM snapshot time (default earliest today)

    Returns per vol_regime bucket:
        - range_2hr distribution (p10/p25/p50/p75/p90)
        - range_eod distribution
        - trade_viable rates by trade type
        - scatter of historical instances (date, pct_2hr, range_2hr)
        - today's snapshot key_strike, flip_level, uprice, ml_signal
    """
    import numpy as np
    import json as _json
    from datetime import date as _date

    date_str = request.args.get("date", _date.today().isoformat())
    try:
        ndate = int(date_str.replace("-", ""))
    except Exception:
        return jsonify({"error": "invalid date"}), 400

    # Get today's latest RTH snapshot
    with _db() as con:
        snap = con.execute(
            "SELECT ntime, price, data FROM gex_strike_window "
            "WHERE ndate=? AND symbol='SPX' AND source='gex' AND ntime>=935 "
            "ORDER BY ntime DESC LIMIT 1",
            (ndate,)
        ).fetchone()

    if not snap:
        return jsonify({"error": f"No RTH snapshot found for {date_str}"}), 404

    ntime, uprice, data_json = snap
    try:
        strikes = _json.loads(data_json) if data_json else []
    except Exception:
        strikes = []

    # Get key strike and flip level for today
    from controllers.gex_calculations import (
        calculate_key_strike_stats, calculate_flip_level
    )
    key_stats  = calculate_key_strike_stats(strikes, uprice) if strikes else {}
    flip_level = calculate_flip_level(strikes) if strikes else None
    key_strike = key_stats.get("key_strike")
    key2_strike= key_stats.get("key2_strike")

    # Get today's ML prediction
    ml_pred = None
    with _db() as con:
        # Inspect actual columns to handle schema variations
        cols = [r[1] for r in con.execute("PRAGMA table_info(ml_predictions)").fetchall()]
        if cols and "ndate" in cols:
            try:
                p = con.execute(
                    "SELECT * FROM ml_predictions WHERE ndate=? ORDER BY ntime DESC LIMIT 1",
                    (ndate,)
                ).fetchone()
                if p:
                    row = dict(zip(cols, p))
                    ml_pred = {
                        "vol_regime": row.get("vol_regime_pred"),
                        "direction":  row.get("direction_pred"),
                        "trade":      row.get("trade_pred"),
                        "trade_code": row.get("trade_code"),
                        "confidence": row.get("confidence"),
                        "vol_proba":  row.get("vol_regime_proba"),
                        "dir_proba":  row.get("direction_proba"),
                    }
            except Exception:
                pass

    # Run live prediction if no stored prediction yet
    if not ml_pred and strikes and uprice:
        try:
            ml_pred = _predict_snapshot(strikes, uprice, ntime)
        except Exception:
            pass

    # Pull all historical ml_labels with range data
    with _db() as con:
        rows = con.execute("""
            SELECT l.ndate, l.ntime, l.range_regime, l.direction_2hr,
                   l.range_2hr, l.pct_2hr, l.range_to_eod,
                   l.trade_viable_ic, l.trade_viable_sps, l.trade_viable_scs,
                   l.trade_viable_lcs, l.trade_viable_lps
            FROM ml_labels l
            WHERE l.range_2hr IS NOT NULL AND l.range_to_eod IS NOT NULL
              AND l.ndate != ?
            ORDER BY l.ndate DESC
        """, (ndate,)).fetchall()

    if not rows:
        return jsonify({"error": "insufficient historical label data"}), 404

    # Collapse NORMAL→TIGHT to match model
    def _regime(r): return "WIDE" if r == "WIDE" else "TIGHT"

    # Aggregate by regime bucket
    buckets = {"TIGHT": [], "WIDE": []}
    for row in rows:
        nd, nt, rr, d2, r2, p2, reod, tv_ic, tv_sps, tv_scs, tv_lcs, tv_lps = row
        nd_str = str(nd)
        buckets[_regime(rr)].append({
            "date": f"{nd_str[:4]}-{nd_str[4:6]}-{nd_str[6:]}",
            "direction": d2,
            "range_2hr": r2,
            "pct_2hr": p2,
            "range_eod": reod,
            "tv_ic": tv_ic, "tv_sps": tv_sps, "tv_scs": tv_scs,
            "tv_lcs": tv_lcs, "tv_lps": tv_lps,
        })

    def percentiles(vals, qs=(10, 25, 50, 75, 90)):
        if not vals:
            return {f"p{q}": None for q in qs}
        arr = np.array(vals, dtype=float)
        return {f"p{q}": round(float(np.percentile(arr, q)), 1) for q in qs}

    def viable_rate(items, col):
        vals = [x[col] for x in items if x[col] is not None]
        return round(sum(vals) / len(vals) * 100, 1) if vals else None

    def build_bucket(items):
        if not items:
            return None
        r2  = [x["range_2hr"] for x in items if x["range_2hr"] is not None]
        reod= [x["range_eod"] for x in items if x["range_eod"] is not None]
        p2  = [x["pct_2hr"]   for x in items if x["pct_2hr"]   is not None]
        # Direction breakdown
        dir_counts = {}
        for x in items:
            dk = x["direction"] or "UNKNOWN"
            dir_counts[dk] = dir_counts.get(dk, 0) + 1
        # Scatter sample (last 120 for chart) — skip rows with null pct/range
        scatter = [{"date": x["date"],
                    "pct_2hr": round(x["pct_2hr"], 3),
                    "range_2hr": round(x["range_2hr"], 1),
                    "direction": x["direction"]}
                   for x in items[-120:]
                   if x["pct_2hr"] is not None and x["range_2hr"] is not None]
        return {
            "n": len(items),
            "range_2hr":  percentiles(r2),
            "range_eod":  percentiles(reod),
            "pct_2hr":    percentiles(p2),
            "direction_counts": dir_counts,
            "trade_viable": {
                "IC":  viable_rate(items, "tv_ic"),
                "SPS": viable_rate(items, "tv_sps"),
                "SCS": viable_rate(items, "tv_scs"),
                "LCS": viable_rate(items, "tv_lcs"),
                "LPS": viable_rate(items, "tv_lps"),
            },
            "scatter": scatter,
        }

    # Also split by direction within today's predicted regime
    pred_regime = None
    pred_dir = None
    if ml_pred:
        pred_regime = "WIDE" if ml_pred.get("vol_regime") == "WIDE" else "TIGHT"
        pred_dir = ml_pred.get("direction")

    filtered_items = []
    if pred_regime and pred_dir:
        filtered_items = [x for x in buckets[pred_regime] if x["direction"] == pred_dir]

    return jsonify({
        "date":        date_str,
        "ntime":       ntime,
        "uprice":      uprice,
        "key_strike":  key_strike,
        "key2_strike": key2_strike,
        "flip_level":  flip_level,
        "ml_signal":   ml_pred,
        "buckets":     {k: build_bucket(v) for k, v in buckets.items()},
        "filtered":    build_bucket(filtered_items) if filtered_items else None,
        "filtered_label": f"{pred_regime} + {pred_dir}" if pred_regime and pred_dir else None,
    })


@app.route("/api/ml/retrain")
def api_ml_retrain():
    """Manually trigger ML model retraining."""
    result = _train_ml_models()
    return jsonify(result)


@app.route("/api/ml/predict")
def api_ml_predict():
    """Run ML prediction for a stored snapshot. Query: date=YYYY-MM-DD&time=HHMM"""
    date_str = request.args.get("date", "")
    time_str = request.args.get("time", "")
    if not date_str or not time_str:
        return jsonify({"error": "date and time required"}), 400
    try:
        ndate = int(date_str.replace("-", ""))
        ntime = int(time_str.replace(":", ""))
    except ValueError:
        return jsonify({"error": "invalid date/time format"}), 400
    with _db() as con:
        row = con.execute(
            "SELECT price, data FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol='SPX'",
            (ndate, ntime)
        ).fetchone()
    if not row:
        return jsonify({"error": "snapshot not found"}), 404
    uprice, data_json = row
    try:
        strikes = json.loads(data_json) if data_json else []
    except Exception:
        return jsonify({"error": "invalid strike data"}), 500
    result = _predict_snapshot(strikes, uprice)
    return jsonify(result)


@app.route("/api/ml/models-status")
def api_ml_models_status():
    """Return status of trained ML models."""
    with _db() as con:
        rows = con.execute(
            "SELECT model_name, trained_at, n_samples, classes, accuracy FROM ml_models"
        ).fetchall()
    models = [{"name": r[0], "trained_at": r[1], "samples": r[2],
               "classes": json.loads(r[3]), "accuracy": r[4]} for r in rows]
    return jsonify({"models": models})


@app.route("/api/ml/update-ohlc")
def api_ml_update_ohlc():
    """Fetch latest SPX 5-min bars from yfinance and update ml_labels."""
    ohlc_result = _update_spx_ohlc_from_yfinance()
    label_result = _ensure_ml_labels_current()
    return jsonify({"ohlc": ohlc_result, "labels": label_result})


@app.route("/api/ml/rebuild-labels")
def api_ml_rebuild_labels():
    """Full rebuild of ml_labels from scratch:
    1. Fetch latest OHLC from yfinance
    2. Delete ALL existing ml_labels rows
    3. Re-run _ensure_ml_labels_current() to repopulate from all gex_strike_window data

    Use this after syncing missing historical GEX snapshots.
    """
    ohlc_result = _update_spx_ohlc_from_yfinance()
    with _db() as con:
        deleted = con.execute("DELETE FROM ml_labels").rowcount
    label_result = _ensure_ml_labels_current()
    return jsonify({
        "ohlc": ohlc_result,
        "deleted_labels": deleted,
        "labels": label_result,
        "message": f"Deleted {deleted} old labels, rebuilt {label_result.get('inserted', 0)} rows from {label_result.get('dates', 0)} dates",
    })


@app.route("/api/ml/labels-summary")
def api_ml_labels_summary():
    """Return summary statistics for ml_labels table."""
    with _db() as con:
        total = con.execute("SELECT COUNT(*) FROM ml_labels").fetchone()[0]
        with_eod = con.execute("SELECT COUNT(*) FROM ml_labels WHERE spx_eod IS NOT NULL").fetchone()[0]
        dates = con.execute("SELECT COUNT(DISTINCT ndate) FROM ml_labels").fetchone()[0]
        last = con.execute("SELECT MAX(ndate) FROM ml_labels").fetchone()[0]
        dirs = con.execute(
            "SELECT direction_eod, COUNT(*) FROM ml_labels WHERE direction_eod IS NOT NULL GROUP BY direction_eod"
        ).fetchall()
        regimes = con.execute(
            "SELECT range_regime, COUNT(*) FROM ml_labels WHERE range_regime IS NOT NULL GROUP BY range_regime"
        ).fetchall()
        flips = con.execute(
            "SELECT flip_breached, COUNT(*) FROM ml_labels WHERE flip_breached IS NOT NULL GROUP BY flip_breached"
        ).fetchall()
    return jsonify({
        "total": total, "with_eod": with_eod, "dates": dates, "last_date": last,
        "direction_eod": dict(dirs),
        "range_regime": dict(regimes),
        "flip_breached": {str(k): v for k, v in flips},
    })


@app.route("/ml")
def page_ml():
    """Machine Learning analysis page."""
    return render_template("ml.html")


@app.route("/api/pca")
def api_pca():
    """Return PCA analysis of the flat summary feature set."""
    return jsonify(_compute_pca())


def _load_hmm() -> tuple:
    """Load the HMM model and scaler from DB. Returns (model, scaler, labels) or (None, None, None)."""
    import pickle
    with _db() as con:
        row = con.execute("SELECT model_blob, state_labels FROM hmm_model WHERE id=1").fetchone()
    if not row:
        return None, None, None
    import json
    payload = pickle.loads(row[0])
    labels = json.loads(row[1])
    return payload["model"], payload["scaler"], labels


def _snap_to_hmm_row(snap: dict) -> list:
    """Convert a summarised snapshot dict to a 5-feature HMM input row."""
    uprice = snap.get("uprice") or 0
    key = snap.get("key_strike") or uprice
    return [
        (snap.get("net_gex") or 0) / 1e9,
        snap.get("kcs") or 0,
        snap.get("sentiment_pct") or 50,
        abs(uprice - key),
        (snap.get("total_put_vol") or 0) / 1e3,
    ]


def predict_hmm_sequence(snaps: list) -> list:
    """Predict HMM states for a list of snapshot dicts as a sequence.

    This is the correct HMM usage — Viterbi decoding over the full sequence
    gives more reliable state assignments than single-point prediction.
    Returns a list of {state, label} dicts, one per input snap.
    """
    import numpy as np
    if not snaps:
        return []
    model, scaler, labels = _load_hmm()
    if model is None:
        return [{"state": None, "label": None} for _ in snaps]

    X = np.array([_snap_to_hmm_row(s) for s in snaps])
    X_scaled = scaler.transform(X)
    states = model.predict(X_scaled)
    return [
        {"state": int(s), "label": labels[s] if s < len(labels) else f"State {s}"}
        for s in states
    ]


def predict_hmm_state(snap: dict) -> dict:
    """Predict HMM regime state for a single snapshot.

    NOTE: single-point HMM prediction is less reliable than sequence prediction.
    Use predict_hmm_sequence when multiple snapshots are available.
    Returns {state, label} or {} if model not available.
    """
    result = predict_hmm_sequence([snap])
    return result[0] if result and result[0].get("state") is not None else {}


@app.route("/api/hmm/train", methods=["POST"])
def api_hmm_train():
    """Retrain the HMM model on all available historical RTH snapshots."""
    result = _train_hmm(force=True)
    return jsonify(result)


@app.route("/api/rf/train", methods=["POST"])
def api_rf_train():
    """Retrain the Random Forest model on all available labelled trade signals."""
    import subprocess
    import sys
    from pathlib import Path
    
    # Run the training script
    script_path = Path(__file__).parent / "train_trade_classifier.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": "Training timed out after 5 minutes",
            "returncode": -1
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }), 500


@app.route("/api/admin/run-daily", methods=["POST"])
def api_admin_run_daily():
    """Run optionalpha_daily.py script."""
    import subprocess
    import sys
    from pathlib import Path
    
    script_path = Path(__file__).parent / "optionalpha_daily.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--symbol", "SPX"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": "Script timed out after 5 minutes",
            "returncode": -1
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }), 500


@app.route("/api/admin/run-summary", methods=["POST"])
def api_admin_run_summary():
    """Run optionalpha_daily-summary.py script."""
    import subprocess
    import sys
    from pathlib import Path
    
    script_path = Path(__file__).parent / "optionalpha_daily-summary.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": "Script timed out after 5 minutes",
            "returncode": -1
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }), 500


@app.route("/api/admin/generate-report", methods=["POST"])
def api_admin_generate_report():
    """Generate GEX report using OpenAI API."""
    import subprocess
    import sys
    from pathlib import Path
    import os
    
    # Read the prompt
    prompt_path = Path(__file__).parent / "GEX_REPORT_PROMPT.md"
    if not prompt_path.exists():
        return jsonify({
            "success": False,
            "error": "GEX_REPORT_PROMPT.md not found"
        }), 404
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    # For now, return the prompt as the report (user will need to manually run through LLM)
    # This is a placeholder - full implementation would require OpenAI API integration
    report_text = "GEX Report Generation\n\n" + "="*50 + "\n\n" + \
                 "Note: Full LLM integration requires OpenAI API key configuration.\n\n" + \
                 "Current prompt instructions:\n\n" + prompt + \
                 "\n\nTo implement full automation:\n" + \
                 "1. Add OPENAI_API_KEY to environment variables\n" + \
                 "2. Implement OpenAI API call in this endpoint\n" + \
                 "3. Execute the prompt steps programmatically\n" + \
                 "\n\nCurrent status: Placeholder implementation"
    return jsonify({
        "success": True,
        "report": report_text
    }), 200


@app.route("/api/admin/verify-data", methods=["POST"])
def api_admin_verify_data():
    """Verify data integrity across snapshot table."""
    try:
        results = _verify_data()
        return jsonify({
            "success": True,
            "results": results
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/admin/regenerate-signals", methods=["POST"])
def api_admin_regenerate_signals():
    """Regenerate trade signals from corrected data."""
    import subprocess
    import sys
    from pathlib import Path
    
    script_path = Path(__file__).parent / "backfill_trade_signals.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        return jsonify({
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }), 200
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Script timed out after 10 minutes"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/admin/daily-workflow", methods=["POST"])
def api_admin_daily_workflow():
    """Run daily workflow steps.

    Steps:
    1. Purge test records (dry_run=False to actually delete)
    2. Verify data
    3. Update SPX OHLC
    4. Rebuild ML labels
    5. Retrain HMM
    6. Retrain ML models
    7. Generate today's trade signals
    8. Backfill prediction outcomes
    9. Compute trade performance metrics

    Note: Sync Historical is now a separate operation (use 'Load Missing Historical' button)

    Query params:
        steps: comma-separated list of steps to run, or "all" (default)
              Options: purge,verify,ohlc,labels,hmm,ml,signals,outcomes,performance
        force_retrain: 1 to force ML retrain regardless of threshold (default 0)
    """
    import time as _time_mod
    from datetime import datetime as _dt
    body = request.get_json(force=True) or {}
    steps_param = body.get("steps", "all")
    force_retrain = body.get("force_retrain", False)

    all_steps = ["purge", "verify", "ohlc", "labels", "hmm", "ml", "signals", "outcomes", "performance"]
    if steps_param == "all":
        steps = all_steps
    else:
        steps = [s.strip() for s in steps_param.split(",")]
    
    results = {}
    
    if "sync" in steps:
        try:
            results["sync"] = sync_historical_gex(mode="all", max_days=30)
            _time_mod.sleep(2)
        except Exception as e:
            results["sync"] = {"error": str(e)}
    
    if "purge" in steps:
        try:
            results["purge"] = {"skipped": True, "reason": "No simple helper function available"}
        except Exception as e:
            results["purge"] = {"error": str(e)}
    
    if "verify" in steps:
        try:
            results["verify"] = _verify_data()
        except Exception as e:
            results["verify"] = {"error": str(e)}
    
    if "ohlc" in steps:
        try:
            results["ohlc"] = _update_spx_ohlc_from_yfinance()
        except Exception as e:
            results["ohlc"] = {"error": str(e)}
    
    if "labels" in steps:
        try:
            results["labels"] = _ensure_ml_labels_current()
        except Exception as e:
            results["labels"] = {"error": str(e)}
    
    if "hmm" in steps:
        try:
            results["hmm"] = _train_hmm()
        except Exception as e:
            results["hmm"] = {"error": str(e)}
    
    if "ml" in steps:
        if force_retrain:
            try:
                # Fetch previous model metrics before training
                with _db() as con:
                    prev_model = con.execute(
                        "SELECT model_name, trained_at, n_samples, accuracy, features, classes FROM ml_models WHERE model_name='vol_regime'"
                    ).fetchone()
                    prev_acc = prev_model[3] if prev_model else None
                    prev_samples = prev_model[2] if prev_model else None
                    
                    # Save previous model to history before overwriting
                    if prev_model:
                        con.execute(
                            """INSERT INTO ml_model_history 
                               (model_name, trained_at, n_samples, accuracy, features, classes)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (prev_model[0], prev_model[1], prev_model[2], prev_model[3], prev_model[4], prev_model[5])
                        )
                
                result = _train_ml_models()
                
                # Add comparison to result
                if prev_acc is not None:
                    new_acc = result.get("models", {}).get("vol_regime", {}).get("accuracy")
                    result["vol_regime"] = {
                        "previous_accuracy": prev_acc,
                        "new_accuracy": new_acc,
                        "change": round(new_acc - prev_acc, 4) if new_acc else None,
                        "previous_samples": prev_samples,
                        "new_samples": result.get("models", {}).get("vol_regime", {}).get("samples")
                    }
                
                results["ml"] = result
            except Exception as e:
                results["ml"] = {"error": str(e)}
        else:
            # Check if retrain is needed
            try:
                with _db() as con:
                    row = con.execute(
                        "SELECT trained_at, n_samples FROM ml_models WHERE model_name='vol_regime'"
                    ).fetchone()
                    current_samples = con.execute(
                        "SELECT COUNT(*) FROM ml_labels WHERE range_regime IS NOT NULL AND direction_eod IS NOT NULL"
                    ).fetchone()[0]
                
                if row is None or (current_samples - row[1] >= 70):
                    results["ml"] = _train_ml_models()
                else:
                    results["ml"] = {"skipped": True, "reason": f"Dataset not grown enough ({current_samples} vs {row[1]})"}
            except Exception as e:
                results["ml"] = {"error": str(e)}
    
    if "signals" in steps:
        try:
            results["signals"] = {"skipped": True, "reason": "Requires HTTP context - run via UI instead"}
        except Exception as e:
            results["signals"] = {"error": str(e)}
    
    if "outcomes" in steps:
        try:
            results["outcomes"] = _backfill_prediction_outcomes()
        except Exception as e:
            results["outcomes"] = {"error": str(e)}
    
    return jsonify({
        "success": all("error" not in r for r in results.values()),
        "steps_run": steps,
        "results": results
    })


@app.route("/api/metric/history")
def api_metric_history():
    """Return historical EOD values for a metric and current value context."""
    metric_name = request.args.get("metric")
    if not metric_name:
        return jsonify({"error": "metric parameter required"}), 400

    # Get historical values
    with _db() as con:
        rows = con.execute(
            "SELECT ndate, value FROM metric_history WHERE metric_name=? ORDER BY ndate",
            (metric_name,)
        ).fetchall()

    if not rows:
        return jsonify({"error": "no historical data for metric", "metric": metric_name}), 404

    values = [r[1] for r in rows]
    dates = [r[0] for r in rows]

    # Get current value (latest live capture or latest historical)
    current_value = None
    current_date = None
    with _db() as con:
        # Try live captures first (today)
        live_row = con.execute(
            "SELECT ndate, uprice, net_gex, kcs, sentiment, gex_ratio, total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, total_call_oi, total_put_oi, key_call_oi, key_put_oi, total_call_vol, total_put_vol, key_call_vol, key_put_vol, key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip FROM snapshot WHERE ndate=(SELECT MAX(ndate) FROM snapshot) ORDER BY ntime DESC LIMIT 1"
        ).fetchone()
        if live_row:
            current_date = live_row[0]
            # Map metric_name to column index
            metric_map = {
                "spx_last": 1, "sentiment_pct": 4, "gex_ratio": 5, "net_gex": 6,
                "kcs": 7, "total_call_gex": 8, "total_put_gex": 9, "key_strike": 10,
                "key_call_gex": 11, "key_put_gex": 12, "total_call_oi": 13,
                "total_put_oi": 14, "key_call_oi": 15, "key_put_oi": 16,
                "total_call_vol": 17, "total_put_vol": 18, "key_call_vol": 19,
                "key_put_vol": 20, "key2_strike": 21, "key2_abs": 22,
                "key2_call_vol": 23, "key2_put_vol": 24, "flip": 25,
            }
            idx = metric_map.get(metric_name)
            if idx is not None and idx < len(live_row):
                current_value = live_row[idx]
        else:
            # Fall back to latest historical
            hist_row = con.execute(
                "SELECT ndate, value FROM metric_history WHERE metric_name=? ORDER BY ndate DESC LIMIT 1",
                (metric_name,)
            ).fetchone()
            if hist_row:
                current_date = hist_row[0]
                current_value = hist_row[1]

    # Calculate percentile
    percentile = None
    if current_value is not None:
        sorted_vals = sorted(values)
        rank = sum(1 for v in sorted_vals if v <= current_value)
        percentile = round(rank / len(sorted_vals) * 100, 1)

    # Get time-slot percentile for current value
    time_slot_pct = None
    if current_value is not None and current_date:
        # Find the time slot with most data for comparison
        best_ntime = None
        best_size = 0
        with _db() as con:
            for t in TIMES:
                size = con.execute(
                    "SELECT COUNT(DISTINCT ndate) FROM percentile_history WHERE ntime=?",
                    (t,)
                ).fetchone()[0]
                if size > best_size:
                    best_size = size
                    best_ntime = t
            if best_ntime:
                # Get percentile against time-slot distribution
                pct_raw = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=? AND value<=?",
                    (best_ntime, metric_name, current_value)
                ).fetchone()[0]
                total = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=?",
                    (best_ntime, metric_name)
                ).fetchone()[0]
                time_slot_pct = round(pct_raw / total * 100, 1) if total > 0 else None

    return jsonify({
        "metric": metric_name,
        "values": values,
        "dates": dates,
        "current_value": current_value,
        "current_date": current_date,
        "percentile": percentile,  # EOD percentile (vs all EOD values)
        "time_slot_percentile": time_slot_pct,  # Time-slot percentile (vs same time of day)
        "min": min(values),
        "max": max(values),
        "mean": round(sum(values) / len(values), 2),
        "count": len(values),
    })




def _ensure_snapshot_table() -> None:
    """Create unified snapshot table if it does not exist.

    This table replaces both snapshot and snapshot.
    Source field: 'gex' for live data, 'histgex' for historical data.
    """
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS snapshot (
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                symbol          TEXT NOT NULL,
                uprice          REAL,
                raw_json        TEXT,
                capture_ts      TEXT,
                source          TEXT NOT NULL,
                sentiment       REAL,
                gex_ratio       REAL,
                net_gex         REAL,
                kcs             REAL,
                dominance       REAL,
                total_call_gex  REAL,
                total_put_gex   REAL,
                key_strike      REAL,
                key_call_gex    REAL,
                key_put_gex     REAL,
                total_call_oi   INTEGER,
                total_put_oi    INTEGER,
                key_call_oi     INTEGER,
                key_put_oi      INTEGER,
                total_call_vol  INTEGER,
                total_put_vol   INTEGER,
                key_call_vol    INTEGER,
                key_put_vol     INTEGER,
                key2_strike     REAL,
                key2_abs        REAL,
                key2_call_vol   INTEGER,
                key2_put_vol    INTEGER,
                flip            REAL,
                is_premarket    INTEGER NOT NULL DEFAULT 0,
                hmm_state       INTEGER,
                hmm_label       TEXT,
                PRIMARY KEY (ndate, ntime, symbol)
            )
        """)
        # Create indexes for common queries
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshot_symbol ON snapshot (symbol)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshot_ndate ON snapshot (ndate)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshot_source ON snapshot (source)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshot_date_time ON snapshot (ndate DESC, ntime DESC)")


def _ensure_snapshot_table() -> None:
    """Create the snapshot table if it does not exist, and add is_premarket column if missing."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS snapshot (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_ts      TEXT NOT NULL,
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                spx_last        REAL,
                sentiment       REAL,
                gex_ratio       REAL,
                net_gex         REAL,
                kcs             REAL,
                dominance       REAL,
                total_call_gex  REAL,
                total_put_gex   REAL,
                key_strike      REAL,
                key_call_gex    REAL,
                key_put_gex     REAL,
                total_call_oi   INTEGER,
                total_put_oi    INTEGER,
                key_call_oi     INTEGER,
                key_put_oi      INTEGER,
                total_call_vol  INTEGER,
                total_put_vol   INTEGER,
                key_call_vol    INTEGER,
                key_put_vol     INTEGER,
                key2_strike     REAL,
                key2_abs        REAL,
                key2_call_vol   INTEGER,
                key2_put_vol   INTEGER,
                flip            REAL,
                is_premarket    INTEGER NOT NULL DEFAULT 0,
                raw_json        TEXT,
                UNIQUE(ndate, ntime)
            )
        """)
        # Migrate existing tables that may lack is_premarket or raw_json
        cols = [r[1] for r in con.execute("PRAGMA table_info(snapshot)").fetchall()]
        if "is_premarket" not in cols:
            con.execute("ALTER TABLE snapshot ADD COLUMN is_premarket INTEGER NOT NULL DEFAULT 0")
        if "raw_json" not in cols:
            con.execute("ALTER TABLE snapshot ADD COLUMN raw_json TEXT")
        
        # Migration: add UNIQUE constraint on (ndate, ntime) if not present
        # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we need to recreate
        indexes = [r[1] for r in con.execute("PRAGMA index_list(snapshot)").fetchall()]
        has_unique = any("snapshot_ndate_ntime" in idx for idx in indexes)
        if not has_unique:
            # Remove duplicates first (use rowid)
            con.execute("""
                DELETE FROM snapshot 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM snapshot 
                    GROUP BY ndate, ntime, symbol
                )
            """)
            # Create unique index
            con.execute("CREATE UNIQUE INDEX snapshot_ndate_ntime ON snapshot(ndate, ntime, symbol)")


def _ensure_unified_snapshots_table() -> None:
    """Create unified snapshots table if it does not exist.

    This table replaces both snapshot and snapshot.
    Historical = date < today (SQL filter, no flag needed).
    """
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                ndate           INTEGER NOT NULL,
                ntime           INTEGER NOT NULL,
                symbol          TEXT NOT NULL,
                uprice          REAL,
                data            TEXT NOT NULL DEFAULT '[]',
                capture_ts      TEXT,
                source          TEXT NOT NULL DEFAULT 'live',
                sentiment       REAL,
                gex_ratio       REAL,
                net_gex         REAL,
                kcs             REAL,
                dominance       REAL,
                total_call_gex  REAL,
                total_put_gex   REAL,
                key_strike      REAL,
                key_call_gex    REAL,
                key_put_gex     REAL,
                total_call_oi   INTEGER,
                total_put_oi    INTEGER,
                key_call_oi     INTEGER,
                key_put_oi      INTEGER,
                total_call_vol  INTEGER,
                total_put_vol  INTEGER,
                key_call_vol    INTEGER,
                key_put_vol     INTEGER,
                key2_strike     REAL,
                key2_abs        REAL,
                key2_call_vol   INTEGER,
                key2_put_vol   INTEGER,
                flip            REAL,
                is_premarket    INTEGER NOT NULL DEFAULT 0,
                hmm_state       INTEGER,
                hmm_label       TEXT,
                PRIMARY KEY (ndate, ntime, symbol)
            )
        """)
        # Create indexes for common queries
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshots_symbol ON snapshots (symbol)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshots_ndate ON snapshots (ndate)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_snapshots_date_time ON snapshots (ndate DESC, ntime DESC)")


def _migrate_to_unified_snapshots() -> dict:
    """Migrate data from snapshot and snapshot to unified snapshots table.

    Returns {"live_migrated": N, "hist_migrated": N, "skipped": N}
    """
    import json
    live_migrated = 0
    hist_migrated = 0
    skipped = 0

    with _db() as con:
        # Check if unified table already has data
        existing = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        if existing > 0:
            return {"status": "already_migrated", "existing": existing}

        # Migrate snapshot
        live_rows = con.execute(
            """SELECT ndate, ntime, uprice, sentiment, gex_ratio, net_gex, kcs, dominance,
               total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
               total_call_oi, total_put_oi, key_call_oi, key_put_oi,
               total_call_vol, total_put_vol, key_call_vol, key_put_vol,
               key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
               is_premarket, hmm_state, hmm_label, capture_ts
               FROM snapshot"""
        ).fetchall()

        for r in live_rows:
            (ndate, ntime, spx_last, sentiment, gex_ratio, net_gex, kcs, dominance,
             total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
             total_call_oi, total_put_oi, key_call_oi, key_put_oi,
             total_call_vol, total_put_vol, key_call_vol, key_put_vol,
             key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
             is_premarket, hmm_state, hmm_label, capture_ts) = r
            try:
                con.execute(
                    """INSERT OR REPLACE INTO snapshots
                    (ndate, ntime, symbol, uprice, data, capture_ts, source,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                     is_premarket, hmm_state, hmm_label)
                    VALUES (?, ?, 'SPX', ?, '[]', ?, 'live',
                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ndate, ntime, spx_last or 0, capture_ts,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                     is_premarket or 0, hmm_state, hmm_label)
                )
                live_migrated += 1
            except Exception as e:
                skipped += 1

        # Migrate snapshot
        hist_rows = con.execute(
            """SELECT ndate, ntime, symbol, uprice, raw_json, source,
               sentiment, gex_ratio, net_gex, kcs, dominance,
               total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
               total_call_oi, total_put_oi, key_call_oi, key_put_oi,
               total_call_vol, total_put_vol, key_call_vol, key_put_vol,
               key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
               is_premarket, hmm_state, hmm_label
               FROM snapshot WHERE symbol='SPX'"""
        ).fetchall()

        for r in hist_rows:
            (ndate, ntime, symbol, uprice, data, source,
             sentiment, gex_ratio, net_gex, kcs, dominance,
             total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
             total_call_oi, total_put_oi, key_call_oi, key_put_oi,
             total_call_vol, total_put_vol, key_call_vol, key_put_vol,
             key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
             is_premarket, hmm_state, hmm_label) = r
            try:
                con.execute(
                    r"""INSERT OR REPLACE INTO snapshots
                    (ndate, ntime, symbol, uprice, data, source,
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                     is_premarket, hmm_state, hmm_label)
                    VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ndate, ntime, symbol, uprice, data, source or 'histgex',
                     sentiment, gex_ratio, net_gex, kcs, dominance,
                     total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                     total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                     total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                     key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                     is_premarket or 0, hmm_state, hmm_label)
                )
                hist_migrated += 1
            except Exception as e:
                skipped += 1

    return {"live_migrated": live_migrated, "hist_migrated": hist_migrated, "skipped": skipped}


SPX_FILES = [
    BASE_DIR / "spx-5min.csv",
    Path(r"g:\My Drive\Colab Notebooks\optionalpha_orb\spx-5min-20250201.csv"),
]
TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]

# Time regimes for Distribution page filtering
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
    {"id": "1531_1555", "label": "15:31-15:55", "start": 1531, "end": 1555},
]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_spx() -> pd.DataFrame:
    """Legacy CSV loader - kept for reference only. SPX price data now sourced from DB."""
    return pd.DataFrame()


RTH_OPEN = 935   # Regular Trading Hours start (ET)
RTH_CLOSE = 1600  # Regular Trading Hours end (ET)


def get_spx_ohlc_from_db(date_iso: str) -> dict | None:
    """Derive SPX OHLC for a date from the uprice values stored in snapshot.

    Only uses RTH prices (ntime >= 935) so pre-market captures don't corrupt
    the Open value. Also checks snapshot for today.
    Returns None if no RTH data found.
    """
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        rows = con.execute(
            "SELECT ntime, uprice FROM snapshot "
            "WHERE ndate=? AND uprice IS NOT NULL AND ntime>=? ORDER BY ntime",
            (ndate, RTH_OPEN),
        ).fetchall()
        live_rows = con.execute(
            "SELECT ntime, uprice FROM snapshot "
            "WHERE ndate=? AND uprice IS NOT NULL AND ntime>=? ORDER BY ntime",
            (ndate, RTH_OPEN),
        ).fetchall()

    # Merge and sort by ntime so open/close are chronologically correct
    combined = sorted(
        [(r[0], r[1]) for r in rows if r[1]] +
        [(r[0], r[1]) for r in live_rows if r[1]],
        key=lambda x: x[0],
    )
    if not combined:
        return None

    prices = [p for _, p in combined]

    # Use manually entered open price if available — overrides first snapshot price
    with _db() as con:
        op_row = con.execute(
            "SELECT open_price FROM spx_open_prices WHERE ndate=?", (ndate,)
        ).fetchone()
    open_price = op_row[0] if op_row else prices[0]

    return {
        "open":  open_price,
        "high":  max(prices + [open_price]),
        "low":   min(prices + [open_price]),
        "close": prices[-1],
    }


def get_spx_bars_from_db(date_iso: str, up_to_ntime: int) -> list:
    """Return per-snapshot RTH price bars from snapshot uprice for the chart,
    for all ntimes in [935, up_to_ntime].
    """
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
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


def available_dates() -> list:
    """Return sorted list of ISO date strings that have GEX data in the DB."""
    with _db() as con:
        rows = con.execute(
            "SELECT DISTINCT ndate FROM snapshot ORDER BY ndate"
        ).fetchall()
    dates = []
    for r in rows:
        s = str(r[0])   # YYYYMMDD int -> string
        dates.append(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
    return dates


def load_snapshot(date_iso: str, ntime: int, symbol: str = "SPX") -> dict | None:
    """Load a single snapshot from the unified snapshot table."""
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        row = con.execute(
            "SELECT uprice, raw_json, sentiment, gex_ratio, net_gex, kcs, dominance, "
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
        # The DB stores the full JSON dict with 'data' key; extract the inner data list
        data_list = parsed.get("data") if isinstance(parsed, dict) else parsed
        return {
            "uprice": row[0],
            "data": data_list,
            "sentiment": row[2],
            "gex_ratio": row[3],
            "net_gex": row[4],
            "kcs": row[5],
            "dominance": row[6],
            "total_call_gex": row[7],
            "total_put_gex": row[8],
            "key_strike": row[9],
            "key_call_gex": row[10],
            "key_put_gex": row[11],
            "total_call_oi": row[12],
            "total_put_oi": row[13],
            "key_call_oi": row[14],
            "key_put_oi": row[15],
            "total_call_vol": row[16],
            "total_put_vol": row[17],
            "key_call_vol": row[18],
            "key_put_vol": row[19],
            "key2_strike": row[20],
            "key2_abs": row[21],
            "key2_call_vol": row[22],
            "key2_put_vol": row[23],
            "flip": row[24],
            "hmm_state": row[25],
            "hmm_label": row[26],
        }
    return None


def load_gex_snapshot(date_iso: str, ntime: int, symbol: str = "SPX") -> dict | None:
    """Load a single GEX snapshot from SQLite (historical only)."""
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        row = con.execute(
            "SELECT uprice, raw_json, sentiment, gex_ratio, net_gex, kcs, dominance, "
            "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
            "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
            "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
            "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, hmm_state, hmm_label "
            "FROM snapshot "
            "WHERE ndate=? AND ntime=? AND symbol=?",
            (ndate, ntime, symbol),
        ).fetchone()
    if row:
        parsed = json.loads(row[1])
        # The DB stores the full JSON dict with 'data' key; extract the inner data list
        data_list = parsed.get("data") if isinstance(parsed, dict) else parsed
        return {
            "uprice": row[0],
            "data": data_list,
            "sentiment": row[2],
            "gex_ratio": row[3],
            "net_gex": row[4],
            "kcs": row[5],
            "dominance": row[6],
            "total_call_gex": row[7],
            "total_put_gex": row[8],
            "key_strike": row[9],
            "key_call_gex": row[10],
            "key_put_gex": row[11],
            "total_call_oi": row[12],
            "total_put_oi": row[13],
            "key_call_oi": row[14],
            "key_put_oi": row[15],
            "total_call_vol": row[16],
            "total_put_vol": row[17],
            "key_call_vol": row[18],
            "key_put_vol": row[19],
            "key2_strike": row[20],
            "key2_abs": row[21],
            "key2_call_vol": row[22],
            "key2_put_vol": row[23],
            "flip": row[24],
            "hmm_state": row[25],
            "hmm_label": row[26],
        }
    return None


def load_live_snapshot(date_iso: str, ntime: int) -> dict | None:
    """Load a single live snapshot from snapshot table."""
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        row = con.execute(
            "SELECT uprice, raw_json, sentiment, gex_ratio, net_gex, kcs, dominance, "
            "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
            "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
            "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
            "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, hmm_state, hmm_label "
            "FROM snapshot "
            "WHERE ndate=? AND ntime=?",
            (ndate, ntime),
        ).fetchone()
    if row:
        parsed = json.loads(row[1]) if row[1] else {"data": []}
        # The DB stores the full JSON dict with 'data' key; extract the inner data list
        data_list = parsed.get("data") if isinstance(parsed, dict) else parsed
        return {
            "uprice": row[0],
            "data": data_list,
            "sentiment": row[2],
            "gex_ratio": row[3],
            "net_gex": row[4],
            "kcs": row[5],
            "dominance": row[6],
            "total_call_gex": row[7],
            "total_put_gex": row[8],
            "key_strike": row[9],
            "key_call_gex": row[10],
            "key_put_gex": row[11],
            "total_call_oi": row[12],
            "total_put_oi": row[13],
            "key_call_oi": row[14],
            "key_put_oi": row[15],
            "total_call_vol": row[16],
            "total_put_vol": row[17],
            "key_call_vol": row[18],
            "key_put_vol": row[19],
            "key2_strike": row[20],
            "key2_abs": row[21],
            "key2_call_vol": row[22],
            "key2_put_vol": row[23],
            "flip": row[24],
            "hmm_state": row[25],
            "hmm_label": row[26],
        }
    return None


def summarise_snapshot(data: dict) -> dict:
    """Summarise snapshot data. If flat columns are present, use them directly."""
    # If flat columns are already computed, return them
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
            "key_vol_net": key_call_vol - key_put_vol,
            "key2_strike": data.get("key2_strike", 0),
            "key2_abs": data.get("key2_abs", 0),
            "key2_call_vol": data.get("key2_call_vol", 0),
            "key2_put_vol": data.get("key2_put_vol", 0),
            "flip": data.get("flip", 0),
            "hmm_state": data.get("hmm_state", 0),
            "hmm_label": data.get("hmm_label", None)
        }
    
    # Fallback: calculate from raw data
    rows   = data.get("data") or []
    uprice = data.get("uprice", 0)
    if not rows:
        return {"uprice": uprice, "net_gex": 0, "call_gex": 0, "put_gex": 0, "sentiment_pct": 50, "gex_ratio": 0}

    valid = [r for r in rows if r.get("strike") is not None]

    # 40-strike window: 20 strikes below + 20 strikes above underlying price
    below = [r for r in valid if r["strike"] < uprice]
    above = [r for r in valid if r["strike"] >= uprice]
    window_rows = below[-20:] + above[:20]
    if not window_rows:
        return {"uprice": uprice, "net_gex": 0, "call_gex": 0, "put_gex": 0, "sentiment_pct": 50, "gex_ratio": 0}

    net    = sum(r.get("net", 0) or 0 for r in window_rows)
    cg     = sum(r.get("cg",  0) or 0 for r in window_rows)
    pg     = sum(r.get("pg",  0) or 0 for r in window_rows)
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in window_rows)

    sorted_abs = sorted(window_rows, key=lambda r: abs(r.get("abs", 0) or 0), reverse=True)
    wall   = sorted_abs[0]["strike"] if sorted_abs else None
    wall2  = sorted_abs[1]["strike"] if len(sorted_abs) > 1 else None

    # Flip level: cumulative net crosses zero within the 40-strike window
    by_strike  = sorted(window_rows, key=lambda r: r["strike"])
    cumulative = 0.0
    flip       = None
    prev_strike, prev_cum = None, 0.0
    for r in by_strike:
        cumulative += r.get("net", 0) or 0
        if prev_strike is not None and prev_cum * cumulative < 0:
            denom = abs(cumulative) + abs(prev_cum)
            flip  = round(prev_strike + (r["strike"] - prev_strike) * abs(prev_cum) / denom, 1) if denom else r["strike"]
            break
        prev_strike, prev_cum = r["strike"], cumulative

    total_call_oi  = sum(r.get("coi",  0) or 0 for r in window_rows)
    total_put_oi   = sum(r.get("poi",  0) or 0 for r in window_rows)
    total_call_vol = sum(r.get("cvol", 0) or 0 for r in window_rows)
    total_put_vol  = sum(r.get("pvol", 0) or 0 for r in window_rows)

    pos_bars = sum(1 for r in window_rows if (r.get("net", 0) or 0) > 0)
    sentiment_pct = round(pos_bars / len(window_rows) * 100) if window_rows else 50
    # Use corrected GEX ratio calculation
    from controllers.gex_calculations import calculate_gex_ratio
    gex_ratio = calculate_gex_ratio(window_rows)

    snap = {
        "uprice": uprice, "net_gex": net, "call_gex": cg, "put_gex": pg,
        "total_abs": total_abs, "wall": wall, "wall2": wall2, "flip": flip,
        "total_call_oi": total_call_oi, "total_put_oi": total_put_oi,
        "total_call_vol": total_call_vol, "total_put_vol": total_put_vol,
        "sentiment_pct": sentiment_pct, "gex_ratio": gex_ratio,
    }
    snap.update(_compute_key_strike_stats(window_rows, uprice))
    return snap


def _compute_key_strike_stats(rows: list, uprice: float) -> dict:
    """Compute key-strike dominance and KCS from the 40-strike window rows.

    KCS (Key Strike Confluence Score) = weighted share of GEX (50%) + OI (30%)
    + Vol (20%) at the proximity-weighted key strike, scaled by a proximity
    factor exp(−distance/25).  Typical range: 3–25.
    """
    if not rows:
        return {}
    total_abs = sum(abs(r.get("abs", 0) or 0) for r in rows)
    total_oi  = sum((r.get("coi", 0) or 0) + (r.get("poi", 0) or 0) for r in rows)
    total_vol = sum((r.get("cvol", 0) or 0) + (r.get("pvol", 0) or 0) for r in rows)

    # Key strike = highest proximity-weighted absolute GEX in the window
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

    # Key2: second-highest proximity-weighted absolute GEX
    other_rows = [r for r in rows if r["strike"] != key_strike]
    key2_row   = max(other_rows, key=lambda r: abs(r.get("abs", 0) or 0)
                                               * math.exp(-abs(r["strike"] - uprice) / 25.0)) if other_rows else None
    key2_strike = key2_row["strike"] if key2_row else None
    key2_abs    = abs(key2_row.get("abs", 0) or 0) if key2_row else None
    key2_cvol   = key2_row.get("cvol", 0) or 0 if key2_row else None
    key2_pvol   = key2_row.get("pvol", 0) or 0 if key2_row else None

    return {
        "key_strike":         key_strike,
        "key_dominance_pct":  key_dominance_pct,
        "key_call_gex":       key_cg,
        "key_put_gex":        key_pg,
        "key_call_oi":        key_coi,
        "key_put_oi":         key_poi,
        "key_call_vol":       key_cvol,
        "key_put_vol":        key_pvol,
        "kcs":                kcs,
        "key2_strike":        key2_strike,
        "key2_abs":           key2_abs,
        "key2_call_vol":      key2_cvol,
        "key2_put_vol":       key2_pvol,
    }


def _compute_flat_summary(data: dict) -> dict:
    """Compute all flat summary fields for a GEX snapshot (40-strike window).

    This matches the calculation used for snapshot so that historical and
    live rows share identical numeric values.
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

    # Use corrected GEX ratio calculation
    from controllers.gex_calculations import calculate_gex_ratio
    gex_ratio = calculate_gex_ratio(rows)

    net_g = sum(net_gex)

    key_stats = _compute_key_strike_stats(window_rows, uprice)

    # Flip level: cumulative net crosses zero within the 40-strike window
    from controllers.gex_calculations import calculate_flip_level
    flip = calculate_flip_level(window_rows)

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


def teaching_points(snap: dict, prev_snap: dict | None, spx_rows: list) -> list:
    points = []
    uprice = snap.get("uprice", 0)
    net    = snap.get("net_gex", 0)
    wall   = snap.get("wall")
    flip   = snap.get("flip")

    # 1. Regime
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

    # 2. GEX wall proximity
    if wall:
        dist = wall - uprice
        if abs(dist) <= 5:
            points.append({
                "type": "warning",
                "icon": "🏔",
                "title": f"AT the GEX Wall ({wall})",
                "text": (f"SPX is pinned at the {wall} GEX wall (±{abs(dist):.0f}pt). "
                         "The largest open interest cluster creates a dealer hedging anchor. "
                         "Price often stalls here. A decisive break through on high volume "
                         "in a negative GEX environment can accelerate sharply.")
            })
        elif abs(dist) <= 20:
            direction = "below" if dist > 0 else "above"
            points.append({
                "type": "info",
                "icon": "🎯",
                "title": f"Approaching GEX Wall at {wall}",
                "text": (f"SPX is {abs(dist):.0f}pts {direction} the {wall} GEX wall. "
                         f"Expect resistance/compression as price gets closer. "
                         f"Dealer hedging flows intensify within 10pts of this level.")
            })
        elif abs(dist) <= 50:
            direction = "below" if dist > 0 else "above"
            points.append({
                "type": "info",
                "icon": "🧲",
                "title": f"GEX Wall at {wall} — gravitational pull active",
                "text": (f"SPX is {abs(dist):.0f}pts {direction} the {wall} GEX wall. "
                         f"Historical data: ~57-63% of 30-min bars move toward the wall from this zone. "
                         f"Compression increases as price approaches. Watch for stall at the wall.")
            })
        else:
            direction = "below" if dist > 0 else "above"
            points.append({
                "type": "secondary",
                "icon": "↔",
                "title": f"Far from GEX Wall ({wall}) — larger moves expected",
                "text": (f"SPX is {abs(dist):.0f}pts {direction} the {wall} wall. "
                         f"With no nearby gamma concentration, dealer hedging is less active. "
                         f"Historical data: avg 30-min move when >50pts from wall = ~40pts vs 8pts when within 10pts.")
            })

    # 3. Flip level
    if flip:
        dist_flip = flip - uprice
        if abs(dist_flip) <= 5:
            points.append({
                "type": "warning",
                "icon": "⚖",
                "title": f"At GEX Flip Level ({flip})",
                "text": (f"SPX is AT the GEX flip level ({flip}). "
                         "This is the zero-crossing where dealer hedging flips from "
                         "stabilising to amplifying. Historical data shows 72% probability "
                         "of an upward move when price touches this level. "
                         "A strong signal to watch for direction.")
            })
        elif dist_flip > 0:
            points.append({
                "type": "secondary",
                "icon": "⬇",
                "title": f"Below Flip Level — bearish dealer flow",
                "text": (f"SPX ({uprice:.0f}) is {dist_flip:.0f}pts below the flip level ({flip:.0f}). "
                         f"Dealers are net sellers on rallies below this line. "
                         f"A move back to {flip:.0f} would flip dealer hedging from selling to buying.")
            })
        else:
            points.append({
                "type": "primary",
                "icon": "⬆",
                "title": f"Above Flip Level — bullish dealer flow",
                "text": (f"SPX ({uprice:.0f}) is {abs(dist_flip):.0f}pts above the flip level ({flip:.0f}). "
                         f"Dealers are net buyers on dips above this line — provides support. "
                         f"A drop back to {flip:.0f} would be a key test: hold = bullish, break = bearish regime change.")
            })

    # 4. Compare move vs previous snapshot
    if prev_snap and prev_snap.get("uprice"):
        prev_price = prev_snap["uprice"]
        move = uprice - prev_price
        prev_net = prev_snap.get("net_gex", 0)
        if abs(move) > 5:
            regime_word = "negative" if prev_net < 0 else "positive"
            consistent  = (move > 0 and prev_net < 0) or (move < 0 and prev_net < 0)
            label = "consistent with" if consistent else "surprising given"
            points.append({
                "type": "dark",
                "icon": "📊",
                "title": f"Last 30-min move: {move:+.1f}pts",
                "text": (f"Price moved {move:+.1f}pts over the last 30 minutes. "
                         f"This is {label} the {regime_word} GEX regime that was in force. "
                         + ("In negative GEX, large moves are expected and dealers amplify them."
                            if prev_net < 0 else
                            "In positive GEX, large moves are unusual — check for a catalyst or GEX flip."))
            })

    return points


def teaching_points_for_snapshot(snap: dict) -> list:
    """Generate teaching points for a single snapshot without historical context."""
    return teaching_points(snap, None, [])


# ---------------------------------------------------------------------------
# EOD Analysis — Thesis Generator & Comparison Engine
# ---------------------------------------------------------------------------

def fmtTime(t: int) -> str:
    """Format time integer (e.g., 1000) to string (e.g., '10:00')."""
    s = str(t).zfill(4)
    return f"{s[:2]}:{s[2:]}"


def fmtBig(v: float) -> str:
    """Format large number with B/M suffix."""
    if abs(v) >= 1e9:
        return f"{v/1e9:.2f}B"
    elif abs(v) >= 1e6:
        return f"{v/1e6:.2f}M"
    elif abs(v) >= 1e3:
        return f"{v/1e3:.2f}K"
    else:
        return f"{v:.2f}"


def parse_summary_value(v):
    """Parse a value from the daily summary CSV, stripping 'B'/'M' suffixes."""
    if v is None:
        return 0
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return 0
    try:
        if s.endswith("B"):
            return float(s[:-1]) * 1e9
        if s.endswith("M"):
            return float(s[:-1]) * 1e6
        return float(s)
    except ValueError:
        return 0


def load_daily_summary() -> pd.DataFrame:
    """Load the concise daily summary CSV used by the analysis report."""
    path = BASE_DIR / "results" / "daily_gex_summary-concise.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [c.strip().strip('"') for c in df.columns]
    df["date_iso"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


DAILY_SUMMARY_DF = None


def get_daily_summary() -> pd.DataFrame:
    """Lazy-load the daily summary DataFrame."""
    global DAILY_SUMMARY_DF
    if DAILY_SUMMARY_DF is None:
        DAILY_SUMMARY_DF = load_daily_summary()
    return DAILY_SUMMARY_DF


def generate_thesis(date_iso: str) -> dict:
    """Generate a thesis from the 10:00 GEX snapshot (or 9:30 if 10:00 unavailable).
    
    Historical analysis intentionally uses only histgex snapshots and SPX data —
    it does NOT rely on daily summary CSV or analysis-concise files, which may be
    missing or only partially generated for older dates.
    """
    # Try 10:00 first, fall back to 9:30
    for t in [1000, 930]:
        raw = load_gex_snapshot(date_iso, t)
        if raw:
            snap = summarise_snapshot(raw)
            break
    else:
        return {"error": "No GEX data available for thesis generation"}

    # Extract wall OI and GEX from the snapshot rows for consistent setup classification
    wall = snap.get("wall")
    key_call_oi, key_put_oi = 0, 0
    key_call_gex, key_put_gex = 0, 0
    if wall is not None and raw:
        for row in raw.get("data", []):
            if row.get("strike") == wall:
                key_call_oi = row.get("coi", 0) or 0
                key_put_oi = row.get("poi", 0) or 0
                key_call_gex = row.get("cg", 0) or 0
                key_put_gex = row.get("pg", 0) or 0
                break

    return build_thesis(
        uprice=snap.get("uprice", 0),
        net_gex=snap.get("net_gex", 0),
        wall=wall,
        flip=snap.get("flip"),
        key_call_oi=key_call_oi,
        key_put_oi=key_put_oi,
        key_call_vol=0,
        key_put_vol=0,
        key_call_gex=key_call_gex,
        key_put_gex=key_put_gex,
        date_iso=date_iso,
        detect_divergence=True,
        divergence_source="snapshot",
    )


def generate_thesis_from_daily_summary(date_iso: str) -> dict:
    """Generate a thesis from the daily summary CSV (used for live/current-day analysis)."""
    df = get_daily_summary()
    row = df[df["date_iso"] == date_iso].iloc[-1] if not df.empty and not df[df["date_iso"] == date_iso].empty else None
    if row is None:
        return {"error": "No daily summary row available for live analysis"}

    return build_thesis(
        uprice=parse_summary_value(row.get("last")),
        net_gex=parse_summary_value(row.get("net_gex")),
        wall=parse_summary_value(row.get("key_strike")) or None,
        flip=None,
        key_call_oi=parse_summary_value(row.get("key_call_oi")),
        key_put_oi=parse_summary_value(row.get("key_put_oi")),
        key_call_vol=parse_summary_value(row.get("key_call_vol")),
        key_put_vol=parse_summary_value(row.get("key_put_vol")),
        key_call_gex=parse_summary_value(row.get("key_call_gex")),
        key_put_gex=parse_summary_value(row.get("key_put_gex")),
        date_iso=date_iso,
        detect_divergence=True,
        divergence_source="daily_summary",
    )


def build_thesis(
    uprice: float,
    net_gex: float,
    wall: float | None,
    flip: float | None = None,
    key_call_oi: float = 0,
    key_put_oi: float = 0,
    key_call_vol: float = 0,
    key_put_vol: float = 0,
    key_call_gex: float = 0,
    key_put_gex: float = 0,
    date_iso: str | None = None,
    detect_divergence: bool = False,
    divergence_source: str = "snapshot",
) -> dict:
    """Build a thesis dict from any GEX snapshot (histgex or daily summary)."""
    thesis_parts = []

    # Regime
    regime = "NEGATIVE" if net_gex < 0 else "POSITIVE"
    thesis_parts.append(f"{regime} GEX regime (net {net_gex/1e9:.1f}B)")

    # Setup classification (same logic as optionalpha_daily-summary.py)
    total_abs_at_key = abs(key_call_gex) + abs(key_put_gex)
    call_put_balance = (abs(key_call_gex) - abs(key_put_gex)) / total_abs_at_key if total_abs_at_key else 0

    if wall:
        dist = wall - uprice
        if abs(dist) <= 10:
            thesis_parts.append(f"PIN at {wall} (±{abs(dist):.0f}pt)")
        elif abs(dist) <= 30:
            thesis_parts.append(f"MAGNET at {wall} ({abs(dist):.0f}pts away)")
        else:
            thesis_parts.append(f"Distant wall at {wall} ({abs(dist):.0f}pts away)")

        # Classify setup using GEX balance + OI, matching optionalpha_daily-summary.py
        if abs(key_call_gex) + abs(key_put_gex) == 0:
            # No GEX breakdown available (histgex snapshot without cg/pg per row) — fall back to OI
            if key_call_oi > key_put_oi * 1.3:
                thesis_parts.append(f"CALL WALL at {wall}")
            elif key_put_oi > key_call_oi * 1.3:
                thesis_parts.append(f"PUT PILLAR at {wall}")
            else:
                thesis_parts.append(f"Key OI cluster at {wall}")
        else:
            key_net_oi = key_call_oi - key_put_oi
            if abs(call_put_balance) <= 0.25:
                thesis_parts.append(f"Balanced PIN at {wall}")
            elif call_put_balance < -0.35 and key_net_oi < -100:
                thesis_parts.append(f"PUT PILLAR at {wall}")
            elif call_put_balance > 0.35 and key_net_oi > 100:
                thesis_parts.append(f"CALL WALL at {wall}")
            else:
                thesis_parts.append(f"Key OI cluster at {wall}")

    # Volume divergence warning
    divergence_warning = None
    if wall and detect_divergence:
        if divergence_source == "daily_summary":
            cvol, pvol, coi, poi = key_call_vol, key_put_vol, key_call_oi, key_put_oi
            if coi > poi and pvol > cvol * 1.5:
                divergence_warning = f"BEARISH divergence at {wall}: heavy put volume ({int(pvol)}) vs call volume ({int(cvol)}) despite call wall"
            elif poi > coi and cvol > pvol * 1.5:
                divergence_warning = f"BULLISH divergence at {wall}: heavy call volume ({int(cvol)}) vs put volume ({int(pvol)}) despite put wall"
            elif poi > coi and pvol > cvol * 3:
                divergence_warning = f"BEARISH divergence at {wall}: aggressive put volume ({int(pvol)}) vs call volume ({int(cvol)}) at put wall"
            elif coi > poi and cvol > pvol * 3:
                divergence_warning = f"BULLISH divergence at {wall}: aggressive call volume ({int(cvol)}) vs put volume ({int(pvol)}) at call wall"
        else:
            # Snapshot source: scan all intraday histgex snapshots for the wall
            for t in TIMES:
                raw_t = load_gex_snapshot(date_iso, t) if date_iso else None
                if raw_t:
                    data = raw_t.get("data", [])
                    for row in data:
                        if row.get("strike") == wall:
                            cvol = row.get("cvol", 0) or 0
                            pvol = row.get("pvol", 0) or 0
                            coi = row.get("coi", 0) or 0
                            poi = row.get("poi", 0) or 0

                            if coi > poi and pvol > cvol * 1.5:
                                divergence_warning = f"BEARISH divergence at {wall} ({fmtTime(t)}): heavy put volume ({pvol}) vs call volume ({cvol}) despite call wall"
                                break
                            elif poi > coi and cvol > pvol * 1.5:
                                divergence_warning = f"BULLISH divergence at {wall} ({fmtTime(t)}): heavy call volume ({cvol}) vs put volume ({pvol}) despite put wall"
                                break
                            elif poi > coi and pvol > cvol * 3:
                                divergence_warning = f"BEARISH divergence at {wall} ({fmtTime(t)}): aggressive put volume ({pvol}) vs call volume ({cvol}) at put wall"
                                break
                            elif coi > poi and cvol > pvol * 3:
                                divergence_warning = f"BULLISH divergence at {wall} ({fmtTime(t)}): aggressive call volume ({cvol}) vs put volume ({pvol}) at call wall"
                                break
                if divergence_warning:
                    break

    if divergence_warning:
        thesis_parts.append(divergence_warning)

    # Expiration week (Friday)
    from datetime import datetime
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        if dt.weekday() == 4:
            thesis_parts.append("Expiration week caution")
    except:
        pass

    return {
        "thesis": " | ".join(thesis_parts),
        "regime": regime,
        "wall": wall,
        "uprice": uprice,
        "net_gex": net_gex,
        "flip": flip,
        "divergence": divergence_warning,
    }


def compare_thesis_with_actuals(date_iso: str, thesis: dict, spx_df: pd.DataFrame = None) -> dict:
    """Compare thesis with OHLC sourced from snapshot DB."""
    ohlc = get_spx_ohlc_from_db(date_iso)
    if not ohlc:
        return {"error": "No SPX data for this date"}
    return _build_verdict(thesis, ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"])


def compare_thesis_with_daily_summary_actuals(date_iso: str, thesis: dict) -> dict:
    """Compare live/current-day thesis with OHLC from the daily summary CSV.
    
    Falls back to SPX CSV if the daily summary has no OHLC yet.
    """
    df = get_daily_summary()
    summary_row = df[df["date_iso"] == date_iso].iloc[-1] if not df.empty and not df[df["date_iso"] == date_iso].empty else None

    if summary_row is not None:
        open_price = parse_summary_value(summary_row.get("ohlc_open"))
        high_price = parse_summary_value(summary_row.get("ohlc_high"))
        low_price = parse_summary_value(summary_row.get("ohlc_low"))
        close_price = parse_summary_value(summary_row.get("ohlc_close"))
        if open_price and high_price and low_price and close_price:
            return _build_verdict(thesis, open_price, high_price, low_price, close_price)

    # Fallback to DB-sourced OHLC
    return compare_thesis_with_actuals(date_iso, thesis)


def _build_verdict(thesis: dict, open_price: float, high_price: float, low_price: float, close_price: float) -> dict:
    """Build a verdict dict from thesis and OHLC."""
    verdict_parts = []

    # Check if pin held
    wall = thesis.get("wall")
    if wall:
        if low_price < wall - 10:  # Broke below with room
            verdict_parts.append(f"Pin at {wall} FAILED — price broke below to {low_price:.0f}")
        elif high_price > wall + 10:  # Broke above with room
            verdict_parts.append(f"Pin at {wall} FAILED — price broke above to {high_price:.0f}")
        else:
            verdict_parts.append(f"Pin at {wall} HELD — price stayed within ±10pts")

    # Check if call wall was tested
    if high_price > open_price + 20:
        verdict_parts.append(f"Rally tested {high_price:.0f} (vs open {open_price:.0f})")

    # Check regime consistency
    regime = thesis.get("regime")
    close_vs_open = close_price - open_price
    if regime == "NEGATIVE" and abs(close_vs_open) > 30:
        verdict_parts.append(f"Large move ({close_vs_open:+.0f}pts) consistent with negative GEX amplification")
    elif regime == "POSITIVE" and abs(close_vs_open) > 30:
        verdict_parts.append(f"Large move ({close_vs_open:+.0f}pts) UNUSUAL in positive GEX regime")

    return {
        "ohlc": {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
        },
        "verdict": " | ".join(verdict_parts) if verdict_parts else "No significant deviations",
    }


def generate_eod_analysis(date_iso: str) -> dict:
    """Generate full historical EOD analysis using only histgex snapshots and SPX CSV."""
    thesis = generate_thesis(date_iso)
    if "error" in thesis:
        return thesis

    comparison = compare_thesis_with_actuals(date_iso, thesis)
    if "error" in comparison:
        return comparison

    return {
        "date": date_iso,
        "thesis": thesis,
        "actuals": comparison["ohlc"],
        "verdict": comparison["verdict"],
    }


def _analyse_intraday_captures(date_iso: str) -> dict:
    """Apply the four Jun-22 lessons to today's snapshot rows.

    Lessons from Gex/Lessons Learnt/20260622.txt:
      1. Key-strike call:put vol ratio — if puts overtake calls early, pin will fail
      2. Net GEX regime flip — if window net_gex goes deeply negative and stays, MMs amplify
      3. Key strike abs GEX trend — growing = self-reinforcing pin; collapsing = anchor dissolving
      4. OI character vs intraday vol — structural put-heavy + put flow confirms directional move
    """
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        rows = con.execute(
            "SELECT ntime, uprice, net_gex, key_strike, key_call_gex, key_put_gex, "
            "key_call_vol, key_put_vol, key_call_oi, key_put_oi, "
            "key2_strike, key2_abs, flip, dominance "
            "FROM snapshot WHERE ndate=? ORDER BY ntime",
            (ndate,),
        ).fetchall()

    if not rows:
        return {"available": False, "signals": [], "summary": "No intraday captures yet today."}

    cols = ["ntime", "spx_last", "net_gex", "key_strike", "key_call_gex", "key_put_gex",
            "key_call_vol", "key_put_vol", "key_call_oi", "key_put_oi",
            "key2_strike", "key2_abs", "flip", "dominance"]
    captures = [dict(zip(cols, r)) for r in rows]
    first = captures[0]
    latest = captures[-1]
    signals = []

    # --- LESSON 1: Key-strike call:put volume ratio ---
    vol_ratios = []
    for c in captures:
        cv = c["key_call_vol"] or 0
        pv = c["key_put_vol"] or 0
        ratio = cv / pv if pv else None
        vol_ratios.append(ratio)

    first_ratio = vol_ratios[0]
    latest_ratio = vol_ratios[-1]
    put_dominant_count = sum(1 for r in vol_ratios if r is not None and r < 1.0)

    if latest_ratio is not None:
        if latest_ratio < 0.5:
            signals.append({
                "lesson": 1,
                "severity": "danger",
                "title": "Put Volume Dominance — Pin Dissolution Risk (Lesson 1)",
                "text": (f"Key strike put volume is running at {1/latest_ratio:.1f}× call volume "
                         f"(ratio {latest_ratio:.2f}). "
                         f"On Jun 22, puts ran 2:1 over calls by 10:30 — the 7500 pin dissolved. "
                         f"Put-heavy flow forces market makers to sell futures, pushing price AWAY from the key strike. "
                         f"{'Trend: deteriorating across ' + str(put_dominant_count) + ' of ' + str(len(captures)) + ' captures.' if put_dominant_count > 1 else ''}")
            })
        elif latest_ratio < 0.8:
            signals.append({
                "lesson": 1,
                "severity": "warning",
                "title": "Put Volume Gaining — Watch Key Strike (Lesson 1)",
                "text": (f"Call:put vol ratio at key strike is {latest_ratio:.2f} — puts are gaining on calls. "
                         f"On Jun 18, calls ran 3–5:1 over puts when the pin held. "
                         f"A ratio below 0.8 is early-warning territory. Monitor for further deterioration.")
            })
        elif latest_ratio >= 2.0:
            signals.append({
                "lesson": 1,
                "severity": "success",
                "title": "Call Volume Dominant — Pin Reinforcement (Lesson 1)",
                "text": (f"Calls running {latest_ratio:.1f}× puts at key strike. "
                         f"On Jun 18, this 3–5:1 call dominance made 7500 a self-reinforcing magnet. "
                         f"Market makers buying calls → delta-hedge by selling above key strike → gravitational pull.")
            })
        else:
            signals.append({
                "lesson": 1,
                "severity": "info",
                "title": f"Call:Put Vol Ratio Neutral ({latest_ratio:.2f}) (Lesson 1)",
                "text": "Volume is roughly balanced at the key strike. No strong reinforcement or dissolution signal yet."
            })

    # --- LESSON 2: Net GEX regime and trend ---
    net_values = [c["net_gex"] for c in captures if c["net_gex"] is not None]
    if net_values:
        latest_net = net_values[-1]
        neg_count = sum(1 for v in net_values if v < 0)
        deepening = len(net_values) >= 2 and net_values[-1] < net_values[-2] < 0

        if latest_net < -5e9 and neg_count >= 2:
            signals.append({
                "lesson": 2,
                "severity": "danger",
                "title": "Deeply Negative Gamma — Regime Locked In (Lesson 2)",
                "text": (f"Net GEX is {latest_net/1e9:.1f}B and has been negative for {neg_count} of "
                         f"{len(net_values)} captures. On Jun 22, net GEX locked at −6 to −9B from 10:30 "
                         f"onward — market makers AMPLIFIED every move away from 7500. "
                         f"{'Deepening further this capture.' if deepening else ''} "
                         f"Do not sell premium into directional moves. No pin thesis is valid.")
            })
        elif latest_net < 0:
            signals.append({
                "lesson": 2,
                "severity": "warning",
                "title": f"Negative Gamma Active ({latest_net/1e9:.1f}B) — Amplification Risk (Lesson 2)",
                "text": (f"Net GEX flipped negative. On Jun 22 the flip happened at 10:30 and never recovered. "
                         f"{'Negative across ' + str(neg_count) + ' captures — trend is persistent.' if neg_count > 1 else 'First negative capture — watch next read.'} "
                         f"Market makers now amplify rather than dampen moves.")
            })
        else:
            signals.append({
                "lesson": 2,
                "severity": "success",
                "title": f"Positive Gamma Stabilising ({latest_net/1e9:.1f}B) (Lesson 2)",
                "text": (f"Net GEX is positive across all {len(net_values)} captures today. "
                         f"On Jun 18, positive gamma kept the 7500 pin intact — MMs bought dips and sold rallies, "
                         f"dampening moves back toward the key strike.")
            })

    # --- LESSON 3: Key strike abs GEX trend ---
    abs_values = []
    for c in captures:
        cg = abs(c["key_call_gex"] or 0)
        pg = abs(c["key_put_gex"] or 0)
        abs_values.append(cg + pg)

    if len(abs_values) >= 2:
        abs_first = abs_values[0]
        abs_latest = abs_values[-1]
        pct_change = (abs_latest - abs_first) / abs_first * 100 if abs_first else 0

        if pct_change >= 20:
            signals.append({
                "lesson": 3,
                "severity": "success",
                "title": f"Key Strike GEX Growing +{pct_change:.0f}% — Self-Reinforcing Pin (Lesson 3)",
                "text": (f"Key strike abs GEX has grown from {abs_first/1e9:.2f}B to {abs_latest/1e9:.2f}B "
                         f"(+{pct_change:.0f}%). On Jun 18, 7500's GEX grew 3× intraday as volume accumulated — "
                         f"the more transacted, the stronger the gravitational pull.")
            })
        elif pct_change <= -30:
            signals.append({
                "lesson": 3,
                "severity": "danger",
                "title": f"Key Strike GEX Collapsing {pct_change:.0f}% — Anchor Dissolving (Lesson 3)",
                "text": (f"Key strike abs GEX has fallen from {abs_first/1e9:.2f}B to {abs_latest/1e9:.2f}B "
                         f"({pct_change:.0f}%). On Jun 22, 7500's GEX shrank 80% from 5B to 1B by close — "
                         f"traders closing/rolling positions removed the gravitational anchor entirely. "
                         f"The pin dissolved because volume was leaving, not accumulating.")
            })
        else:
            signals.append({
                "lesson": 3,
                "severity": "info",
                "title": f"Key Strike GEX Stable ({pct_change:+.0f}%) (Lesson 3)",
                "text": f"Key strike abs GEX has moved {pct_change:+.0f}% from first to latest capture. No strong growth or collapse signal yet."
            })

    # --- LESSON 4: OI character vs intraday flow (structural vs live) ---
    oi_net = (latest.get("key_call_oi") or 0) - (latest.get("key_put_oi") or 0)
    vol_net = (latest.get("key_call_vol") or 0) - (latest.get("key_put_vol") or 0)
    if oi_net != 0 and vol_net != 0:
        oi_char = "call-heavy" if oi_net > 0 else "put-heavy"
        flow_char = "call-dominant" if vol_net > 0 else "put-dominant"
        if (oi_net > 0) != (vol_net > 0):
            signals.append({
                "lesson": 4,
                "severity": "warning",
                "title": f"OI vs Flow Divergence — {oi_char.title()} OI but {flow_char.title()} Volume (Lesson 4)",
                "text": (f"Key strike OI is {oi_char} (net OI {oi_net:+,}) but intraday volume is {flow_char} "
                         f"(net vol {vol_net:+,}). On Jun 22, the structurally balanced OI at 7500 was overwhelmed "
                         f"by put flow — the live flow, not the OI, determined direction. "
                         f"{'Put flow into call-heavy OI is BEARISH divergence — watch for pin failure.' if oi_net > 0 else 'Call flow into put-heavy OI is BULLISH divergence — potential bounce signal.'}")
            })
        else:
            signals.append({
                "lesson": 4,
                "severity": "success",
                "title": f"OI and Flow Aligned — {oi_char.title()} (Lesson 4)",
                "text": (f"Key strike OI ({oi_char}, net OI {oi_net:+,}) and intraday flow ({flow_char}, net vol {vol_net:+,}) "
                         f"are pointing the same direction. On Jun 18, call-heavy OI and massive call flow both reinforced "
                         f"the 7500 level. Alignment confirms the structural thesis.")
            })

    # Build plain-text summary for the overall trend
    key_strikes = [c["key_strike"] for c in captures if c["key_strike"]]
    ks_migrated = len(set(key_strikes)) > 1
    spx_prices = [c["spx_last"] for c in captures if c["spx_last"]]
    price_move = round(spx_prices[-1] - spx_prices[0], 2) if len(spx_prices) >= 2 else 0

    summary_parts = [
        f"{len(captures)} capture{'s' if len(captures)>1 else ''} today",
        f"SPX {spx_prices[0]:.2f} → {spx_prices[-1]:.2f} ({price_move:+.2f})" if len(spx_prices) >= 2 else f"SPX {spx_prices[0]:.2f}",
    ]
    if ks_migrated:
        summary_parts.append(f"Key strike migrated: {' → '.join(str(int(k)) for k in key_strikes)}")
    else:
        summary_parts.append(f"Key strike stable at {int(key_strikes[-1]) if key_strikes else '?'}")

    danger_count = sum(1 for s in signals if s["severity"] == "danger")
    warning_count = sum(1 for s in signals if s["severity"] == "warning")
    if danger_count:
        summary_parts.append(f"⚠️ {danger_count} DANGER signal{'s' if danger_count>1 else ''}")
    elif warning_count:
        summary_parts.append(f"⚡ {warning_count} warning signal{'s' if warning_count>1 else ''}")
    else:
        summary_parts.append("✅ No breakdown signals detected")

    return {
        "available": True,
        "capture_count": len(captures),
        "signals": signals,
        "summary": " | ".join(summary_parts),
        "key_strike_migrated": ks_migrated,
    }


def generate_live_analysis(date_iso: str) -> dict:
    """Generate live/current-day analysis from the daily summary CSV,
    overriding stale CSV values with the latest snapshot row from DB.
    """
    thesis = generate_thesis_from_daily_summary(date_iso)
    if "error" in thesis:
        return thesis

    # Override thesis values with the latest snapshot row so the
    # thesis net_gex, the table, and the UI widget all show the same number.
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        latest_cap = con.execute(
            "SELECT uprice, net_gex, key_strike, flip, "
            "key_call_gex, key_put_gex, key_call_oi, key_put_oi, "
            "key_call_vol, key_put_vol "
            "FROM snapshot WHERE ndate=? ORDER BY id DESC LIMIT 1",
            (ndate,),
        ).fetchone()
    if latest_cap:
        cap_cols = ["spx_last", "net_gex", "key_strike", "flip",
                    "key_call_gex", "key_put_gex", "key_call_oi", "key_put_oi",
                    "key_call_vol", "key_put_vol"]
        cap = dict(zip(cap_cols, latest_cap))
        # Rebuild thesis text with live values
        thesis = build_thesis(
            uprice=cap["spx_last"] or thesis.get("uprice", 0),
            net_gex=cap["net_gex"] or thesis.get("net_gex", 0),
            wall=cap["key_strike"] or thesis.get("wall"),
            flip=cap["flip"] or thesis.get("flip"),
            key_call_oi=cap["key_call_oi"] or 0,
            key_put_oi=cap["key_put_oi"] or 0,
            key_call_vol=cap["key_call_vol"] or 0,
            key_put_vol=cap["key_put_vol"] or 0,
            key_call_gex=cap["key_call_gex"] or 0,
            key_put_gex=cap["key_put_gex"] or 0,
            date_iso=date_iso,
            detect_divergence=True,
            divergence_source="daily_summary",
        )

    intraday = _analyse_intraday_captures(date_iso)

    comparison = compare_thesis_with_daily_summary_actuals(date_iso, thesis)
    if "error" in comparison:
        # No SPX OHLC yet (intraday / CSV not updated) — build a live price range
        # from the intraday captures so we still return a useful response
        actuals = None
        verdict = "No SPX OHLC data yet for today."
        caps = intraday.get("signals") and intraday.get("available")
        if caps:
            ndate = int(date_iso.replace("-", ""))
            with _db() as con:
                price_rows = con.execute(
                    "SELECT uprice FROM snapshot WHERE ndate=? AND uprice IS NOT NULL ORDER BY ntime",
                    (ndate,),
                ).fetchall()
            prices = [r[0] for r in price_rows]
            if prices:
                actuals = {
                    "open":  prices[0],
                    "high":  max(prices),
                    "low":   min(prices),
                    "close": prices[-1],
                }
                verdict = (f"Live range so far: Open {prices[0]:.2f} | "
                           f"High {max(prices):.2f} | Low {min(prices):.2f} | "
                           f"Last {prices[-1]:.2f} — session in progress.")
    else:
        actuals = comparison["ohlc"]
        verdict = comparison["verdict"]

    return {
        "date": date_iso,
        "thesis": thesis,
        "actuals": actuals,
        "verdict": verdict,
        "intraday": intraday,
    }


def classify_setup_from_summary(row: dict) -> str:
    """Classify today's GEX setup using the same logic as optionalpha_daily-summary.py."""
    def parse_b(v):
        if v is None or v == "":
            return 0.0
        s = str(v).strip().upper().rstrip("B")
        try:
            return float(s)
        except ValueError:
            return 0.0

    def safe_f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    kabs = parse_b(row.get("key_absolute"))
    kcall_g = parse_b(row.get("key_call_gex"))
    kput_g = parse_b(row.get("key_put_gex"))
    ngex = parse_b(row.get("net_gex"))
    knet_oi = safe_f(row.get("key_net_oi"))

    if kabs < 1.5:
        return "LOW_CONV"

    total = abs(kcall_g or 0) + abs(kput_g or 0)
    bal = (abs(kcall_g or 0) - abs(kput_g or 0)) / total if total else 0

    if abs(bal) <= 0.25:
        return "PIN"
    if bal < -0.35 and (knet_oi or 0) < -100:
        return "PUT_PILLAR"
    if bal > 0.35 and (knet_oi or 0) > 100:
        return "CALL_WALL"
    if ngex < -5:
        return "NEG_GAMMA"
    return "NO_SETUP"


SETUP_LABELS = {
    "PIN":          "GEX Pin / Magnet",
    "PUT_PILLAR":   "Put Pillar / Support",
    "CALL_WALL":    "Call Wall / Resistance",
    "NEG_GAMMA":    "Negative Gamma Acceleration",
    "LOW_CONV":     "Low Conviction / No Clear Setup",
    "NO_SETUP":     "No Clear Setup",
}


def generate_concise_report(date_iso: str) -> Path | None:
    """Generate a concise GEX analysis markdown file from the daily summary CSV.

    This replicates the output structure of GEX_REPORT_PROMPT.md using the same
    daily summary data and classification logic.
    """
    df = get_daily_summary()
    rows = df[df["date_iso"] == date_iso]
    if rows.empty:
        return None
    row = rows.iloc[-1].to_dict()

    setup = classify_setup_from_summary(row)
    setup_label = SETUP_LABELS.get(setup, setup)

    analysis_dir = BASE_DIR / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    now = datetime.now()
    filename = f"analysis-concise-{date_iso.replace('-', '')}-{now.strftime('%H%M')}.md"
    path = analysis_dir / filename

    def parse_b(v):
        s = str(v).strip().upper().rstrip("B")
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    def fmtb(v):
        return f"{parse_b(v):.2f}B"

    last = parse_b(row.get("last"))
    key_strike = parse_b(row.get("key_strike"))
    key2_strike = parse_b(row.get("key2_strike"))
    key_absolute = parse_b(row.get("key_absolute"))
    key2_absolute = parse_b(row.get("key2_absolute"))
    key_net = parse_b(row.get("key_net"))
    key_dominance = float(row.get("key_dominance_pct") or 0)
    key_call_oi = float(row.get("key_call_oi") or 0)
    key_put_oi = float(row.get("key_put_oi") or 0)
    key_net_oi = float(row.get("key_net_oi") or 0)
    key_call_vol = float(row.get("key_call_vol") or 0)
    key_put_vol = float(row.get("key_put_vol") or 0)
    key_vol_net = float(row.get("key_vol_net") or 0)
    ohlc_open = parse_b(row.get("ohlc_open"))
    ohlc_high = parse_b(row.get("ohlc_high"))
    ohlc_low = parse_b(row.get("ohlc_low"))
    ohlc_close = parse_b(row.get("ohlc_close"))

    dist = key_strike - last if key_strike and last else 0

    lines = [
        f"# SPX GEX Concise Report — {date_iso}",
        f"**Capture time:** {row.get('date', '')}",
        f"**SPX last:** {last:.2f}",
        f"**Report generated:** {now.strftime('%Y-%m-%d %H:%M')} local",
        "",
        "---",
        "",
        "## Section A — Today's Values in Isolation",
        "",
        f"**Setup:** {setup} — {setup_label}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| last | {last:.2f} |",
        f"| sentiment | {row.get('sentiment', '')}% |",
        f"| gex_ratio | {row.get('gex_ratio', '')} |",
        f"| net_gex | {fmtb(row.get('net_gex'))} |",
        f"| key_strike | {key_strike:.0f} ({dist:+.0f} pts from price) |",
        f"| key_absolute | {fmtb(row.get('key_absolute'))} |",
        f"| key_net | {fmtb(row.get('key_net'))} |",
        f"| key_dominance_pct | {key_dominance:.1f}% |",
        f"| key_call_oi | {int(key_call_oi)} |",
        f"| key_put_oi | {int(key_put_oi)} |",
        f"| key_net_oi | {int(key_net_oi)} |",
        f"| key_call_vol | {int(key_call_vol)} |",
        f"| key_put_vol | {int(key_put_vol)} |",
        f"| key_vol_net | {int(key_vol_net)} |",
        f"| key2_strike | {key2_strike:.0f} |",
        f"| key2_absolute | {fmtb(row.get('key2_absolute'))} |",
        "",
        "---",
        "",
        "## Section C — GEX Teaching Point Mapping",
        "",
        f"**{setup_label}** — key strike {key_strike:.0f} with {fmtb(row.get('key_absolute'))} absolute GEX.",
        "",
        "## Section D — Trade Logic",
        "",
        "See Section C for setup classification. Short premium with defined risk only.",
        "",
        "## Section E — Invalidation Conditions",
        "",
        f"- Break of {key2_strike:.0f} (key2) with momentum would weaken the {setup_label} thesis.",
        "- A flip in net GEX from positive to negative (or vice versa) on a mid-session refresh invalidates the current regime.",
        "",
        "## Section F — Caution Notes",
        "",
        "- Verify economic calendar before trading.",
        "- Tomorrow's GEX profile has not been checked.",
        "",
    ]

    if ohlc_open and ohlc_high and ohlc_low and ohlc_close:
        lines.extend([
            "## Actual OHLC",
            "",
            f"Open: {ohlc_open:.2f} | High: {ohlc_high:.2f} | Low: {ohlc_low:.2f} | Close: {ohlc_close:.2f}",
            "",
        ])

    lines.extend([
        "---",
        "",
        f"*Report generated by GEX Intraday Viewer live pipeline.*",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# GEX Day Classification
# ---------------------------------------------------------------------------

def classify_gex_day(date_iso: str, spx_df: pd.DataFrame) -> dict:
    """Classify the GEX day type using all available snapshots and price data."""
    snapshots = []
    for t in TIMES:
        raw = load_gex_snapshot(date_iso, t)
        if raw:
            s = summarise_snapshot(raw)
            s["time"] = t
            snapshots.append(s)
    if not snapshots:
        return {"type": "no-data", "label": "No Data", "description": "No GEX snapshots available."}

    # Gather key metrics across the day
    nets = [s.get("net_gex", 0) for s in snapshots]
    walls = [s.get("wall") for s in snapshots if s.get("wall")]
    flips = [s.get("flip") for s in snapshots if s.get("flip")]
    uprices = [s.get("uprice", 0) for s in snapshots if s.get("uprice")]

    avg_net = sum(nets) / len(nets) if nets else 0
    pct_negative = sum(1 for n in nets if n < 0) / len(nets) if nets else 0

    # Price range for the day
    day_df = spx_df[spx_df["date_iso"] == date_iso] if not spx_df.empty else pd.DataFrame()
    if not day_df.empty:
        day_high = day_df["High"].max()
        day_low  = day_df["Low"].min()
        day_range = day_high - day_low
        day_open  = day_df.iloc[0]["Open"]
        day_close = day_df.iloc[-1]["Close"]
    elif uprices:
        day_high  = max(uprices)
        day_low   = min(uprices)
        day_range = day_high - day_low
        day_open  = uprices[0]
        day_close = uprices[-1]
    else:
        return {"type": "no-data", "label": "No Data", "description": "Insufficient price data."}

    # Primary wall for the day (most common)
    primary_wall = max(set(walls), key=walls.count) if walls else None

    # Distance from wall metrics
    if primary_wall and uprices:
        avg_dist_from_wall = sum(abs(p - primary_wall) for p in uprices) / len(uprices)
        max_dist_from_wall = max(abs(p - primary_wall) for p in uprices)
    else:
        avg_dist_from_wall = 999
        max_dist_from_wall = 999

    # Did price cross the flip level?
    flip_crossed = False
    if flips and uprices and len(uprices) >= 2:
        primary_flip = flips[len(flips) // 2]  # mid-day flip
        above_count = sum(1 for p in uprices if p > primary_flip)
        below_count = sum(1 for p in uprices if p < primary_flip)
        flip_crossed = above_count > 0 and below_count > 0

    # --- Classification rules (ordered by specificity) ---

    # 1. PIN DAY: positive GEX, price stays within 15pts of wall most of the day
    if pct_negative < 0.3 and primary_wall and avg_dist_from_wall <= 15 and day_range < 30:
        return {
            "type": "pin",
            "label": "Pin Day",
            "color": "#0d6efd",
            "description": (
                f"Price pinned near {primary_wall} GEX wall all day (avg {avg_dist_from_wall:.0f}pt away). "
                f"Positive GEX kept dealers selling rallies and buying dips, capping range to {day_range:.0f}pts. "
                f"This is a textbook GEX pinning effect — ideal for selling premium (iron condors/butterflies)."
            )
        }

    # 2. COMPRESSION DAY: very high positive GEX, ultra-tight range
    if pct_negative < 0.2 and avg_net > 3e9 and day_range < 20:
        return {
            "type": "compression",
            "label": "Compression Day",
            "color": "#198754",
            "description": (
                f"Extremely high positive GEX ({avg_net/1e9:.1f}B avg) compressed the day's range to just "
                f"{day_range:.0f}pts. Dealers aggressively mean-reverted every move. "
                f"These days often precede a large move when GEX eventually unwinds (usually at expiration)."
            )
        }

    # 3. MAGNET DAY: price drifts steadily toward the wall
    if primary_wall and uprices:
        first_dist = abs(uprices[0] - primary_wall)
        last_dist  = abs(uprices[-1] - primary_wall)
        if first_dist > 25 and last_dist < 10 and pct_negative < 0.5:
            return {
                "type": "magnet",
                "label": "Magnet Day",
                "color": "#6f42c1",
                "description": (
                    f"Price started {first_dist:.0f}pts from the {primary_wall} wall and drifted to within "
                    f"{last_dist:.0f}pts by end of day. The wall acted as a gravitational magnet — "
                    f"dealer hedging pulled price toward the largest OI cluster. "
                    f"Classic mean-reversion trade setup: fade moves away from the wall."
                )
            }

    # 4. FLIP DAY: price crosses the flip level, regime changes
    if flip_crossed and flips:
        primary_flip = flips[len(flips) // 2]
        return {
            "type": "flip",
            "label": "Flip Day",
            "color": "#fd7e14",
            "description": (
                f"Price crossed the GEX flip level ({primary_flip:.0f}) during the session. "
                f"This flipped dealer hedging from stabilising to amplifying (or vice versa). "
                f"The cross often marks an inflection point — watch for acceleration after the flip. "
                f"Day range: {day_range:.0f}pts."
            )
        }

    # 5. BREAKOUT DAY: negative GEX + price breaks through wall with follow-through
    if pct_negative > 0.5 and primary_wall and max_dist_from_wall > 30 and day_range > 35:
        direction = "higher" if day_close > day_open else "lower"
        return {
            "type": "breakout",
            "label": "Breakout Day",
            "color": "#dc3545",
            "description": (
                f"Negative GEX ({pct_negative*100:.0f}% of session) allowed price to break "
                f"through the {primary_wall} wall and extend {direction}. Day range: {day_range:.0f}pts. "
                f"Dealers amplified the move by hedging in the same direction. "
                f"These days reward breakout/momentum strategies and punish fading."
            )
        }

    # 6. TRENDING DAY: sustained directional move under negative GEX
    if pct_negative > 0.6 and day_range > 30:
        direction = "bullish" if day_close > day_open else "bearish"
        move_size = abs(day_close - day_open)
        return {
            "type": "trending",
            "label": "Trending Day",
            "color": "#dc3545",
            "description": (
                f"Sustained {direction} trend under negative GEX ({pct_negative*100:.0f}% of session). "
                f"Dealers amplified momentum throughout — {move_size:.0f}pt body, {day_range:.0f}pt range. "
                f"Once direction established in negative GEX, dips/rallies are shallow. "
                f"Best strategy: ride the trend, trail stops, avoid counter-trend entries."
            )
        }

    # 7. WALL REJECTION DAY: price approaches wall, gets rejected
    if primary_wall and uprices:
        touched_wall = any(abs(p - primary_wall) <= 5 for p in uprices)
        ended_away   = abs(uprices[-1] - primary_wall) > 15
        if touched_wall and ended_away and pct_negative < 0.5:
            return {
                "type": "wall-reject",
                "label": "Wall Rejection Day",
                "color": "#20c997",
                "description": (
                    f"Price approached the {primary_wall} GEX wall but was rejected and ended "
                    f"{abs(uprices[-1] - primary_wall):.0f}pts away. The concentrated dealer hedging at the wall "
                    f"created supply/demand that absorbed the move. "
                    f"Rejection from a GEX wall is a high-probability reversal signal."
                )
            }

    # Default: no strong classification
    return {
        "type": "mixed",
        "label": "Mixed / No Clear Type",
        "color": "#6c757d",
        "description": (
            f"No single dominant GEX regime today. Net GEX averaged {avg_net/1e9:.1f}B "
            f"({pct_negative*100:.0f}% negative). Day range: {day_range:.0f}pts. "
            f"Mixed days require more discretion — watch for intraday regime shifts."
        )
    }


# ---------------------------------------------------------------------------
# Percentile ranking — compare any snapshot against historical distributions
# ---------------------------------------------------------------------------

_STATS_CACHE: dict = {}    # {ntime: {metric: sorted_list}}
_HISTORY_CACHE = {}  # {ntime: {metric: [values in date order], "dates": [...]}}
_STATS_CACHE_METRICS = ["net_gex", "call_gex", "put_gex", "call_oi", "put_oi", "call_vol", "put_vol", "kcs", "dominance", "sentiment", "gex_ratio"]


def _snapshot_computed_stats(date_iso: str, ntime: int) -> dict | None:
    """Load a histgex snapshot and compute the same 40-strike window stats as the API.
    
    First tries to read from flat columns in snapshot (backfilled values).
    Falls back to JSON computation if flat columns are NULL.
    """
    import sqlite3
    ndate = int(date_iso.replace("-", ""))
    
    # Try to read from flat columns first
    with _db() as con:
        row = con.execute(
            "SELECT net_gex, total_call_gex, total_put_gex, total_call_oi, total_put_oi, "
            "total_call_vol, total_put_vol, kcs, dominance, sentiment, gex_ratio "
            "FROM snapshot WHERE ndate=? AND ntime=? AND symbol='SPX'",
            (ndate, ntime)
        ).fetchone()
    
    if row and row[0] is not None:  # net_gex is not NULL, use flat columns
        return {
            "net_gex": row[0],
            "call_gex": row[1],
            "put_gex": row[2],
            "call_oi": row[3],
            "put_oi": row[4],
            "call_vol": row[5],
            "put_vol": row[6],
            "kcs": row[7],
            "dominance": row[8],
            "sentiment": row[9],
            "gex_ratio": row[10],
        }
    
    # Fall back to JSON computation
    raw = load_gex_snapshot(date_iso, ntime)
    if not raw:
        return None
    uprice = raw.get("uprice", 0)
    all_rows = sorted(
        [r for r in (raw.get("data") or []) if r.get("strike") is not None],
        key=lambda r: r["strike"],
    )
    below = [r for r in all_rows if r["strike"] < uprice]
    above = [r for r in all_rows if r["strike"] >= uprice]
    rows = below[-20:] + above[:20]
    if not rows:
        return None
    call_gex = [r.get("calls", r.get("cg", 0)) or 0 for r in rows]
    put_gex  = [r.get("puts", r.get("pg", 0)) or 0 for r in rows]
    net_gex  = [r.get("net", 0) or 0 for r in rows]
    ks = _compute_key_strike_stats(rows, uprice)

    pos_bars = sum(1 for n in net_gex if n > 0)
    sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50

    # Use corrected GEX ratio calculation
    from controllers.gex_calculations import calculate_gex_ratio
    gex_ratio = calculate_gex_ratio(rows)

    return {
        "net_gex":  sum(net_gex),
        "call_gex": sum(call_gex),
        "put_gex":  sum(put_gex),
        "call_oi":  sum(r.get("coi", 0) or 0 for r in rows),
        "put_oi":   sum(r.get("poi", 0) or 0 for r in rows),
        "call_vol": sum(r.get("cvol", 0) or 0 for r in rows),
        "put_vol":  sum(r.get("pvol", 0) or 0 for r in rows),
        "kcs":      ks.get("kcs", 0.0),
        "dominance": ks.get("key_dominance_pct", 0.0),
        "sentiment": sentiment_pct,
        "gex_ratio": gex_ratio,
    }


def get_stats_cache(ntime: int) -> dict:
    """Return (and lazily build) the sorted distribution for each metric at this time slot."""
    global _STATS_CACHE
    if ntime in _STATS_CACHE:
        return _STATS_CACHE[ntime]
    buckets: dict = {k: [] for k in _STATS_CACHE_METRICS}
    for date_iso in available_dates():
        stats = _snapshot_computed_stats(date_iso, ntime)
        if stats:
            for k in _STATS_CACHE_METRICS:
                buckets[k].append(stats[k])
    _STATS_CACHE[ntime] = {k: sorted(v) for k, v in buckets.items()}
    return _STATS_CACHE[ntime]


def pct_rank(value: float, sorted_list: list) -> int:
    """Percentile rank of value: % of historical readings strictly below this value (0-100)."""
    if not sorted_list:
        return 50
    return round(bisect.bisect_left(sorted_list, value) / len(sorted_list) * 100)


def get_history_cache(ntime: int) -> dict:
    """Return (and lazily build) ordered history lists for scatter charts."""
    global _HISTORY_CACHE
    if ntime in _HISTORY_CACHE:
        return _HISTORY_CACHE[ntime]
    buckets: dict = {"dates": []}
    for k in _STATS_CACHE_METRICS:
        buckets[k] = []
    for date_iso in available_dates():
        stats = _snapshot_computed_stats(date_iso, ntime)
        if stats:
            buckets["dates"].append(date_iso)
            for k in _STATS_CACHE_METRICS:
                buckets[k].append(stats[k])
    _HISTORY_CACHE[ntime] = buckets
    return buckets


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

SPX_DF = pd.DataFrame()  # SPX price data sourced from snapshot DB, not CSV


@app.route("/")
def index():
    return redirect("/gex")

@app.route("/gex")
def gex():
    from time import time
    return render_template("gex.html", cache_bust=int(time()))

@app.route("/gex-admin")
def gex_admin():
    from time import time
    return render_template("gex_admin.html", cache_bust=int(time()))

@app.route("/bots")
def bots():
    from time import time
    return render_template("bots.html", cache_bust=int(time()))

@app.route("/api/bots")
def api_bots():
    """Fetch active bots list from OptionAlpha via bots.load RPC."""
    import time as _time_mod
    from optionalpha_client import call_optionalpha_api, SESSION_FILE

    tid = int(_time_mod.time() * 1000)
    payload = [
        {
            "t": "rpc",
            "tid": f"{tid}-10008",
            "api": "bots.load",
            "args": [
                {
                    "where": {"accountId": "*"},
                    "start": 0,
                }
            ],
        }
    ]
    print(f"[BOTS API] Calling bots.load, tid={tid}")
    try:
        data = call_optionalpha_api(payload)
        print(f"[BOTS API] Response length: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, dict) and data.get("error"):
            return jsonify({"error": data.get("error"), "details": data}), 503
        # Extract bot list from response
        bots = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("api") == "bots.load":
                    bot_data = item.get("data")
                    if isinstance(bot_data, list):
                        bots = bot_data
                    break
        print(f"[BOTS API] Loaded {len(bots)} bots")
        return jsonify({
            "status": "ok",
            "count": len(bots),
            "bots": bots,
            "raw": data,
        })
    except FileNotFoundError as e:
        print(f"[BOTS API] Session file missing: {e}")
        return jsonify({"error": "Session file not found. Run optionalpha_probe.py to refresh session.json."}), 503
    except Exception as e:
        print(f"[BOTS API] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot-scanners")
def api_bot_scanners():
    """Fetch scanners/triggers and notes for a single bot from OptionAlpha."""
    import time as _time_mod
    from optionalpha_client import call_optionalpha_api, SESSION_FILE

    bot_id = request.args.get("id")
    if not bot_id:
        return jsonify({"error": "Missing bot id"}), 400

    tid = int(_time_mod.time() * 1000)
    payload = [
        {
            "t": "rpc",
            "tid": f"{tid}-10002",
            "api": "triggers.list",
            "args": [{"iid": bot_id}],
        },
        {
            "t": "rpc",
            "tid": f"{tid}-10003",
            "api": "bot.getNotes",
            "args": [bot_id],
        },
    ]
    print(f"[BOT SCANNERS API] Calling triggers.list and bot.getNotes for {bot_id}, tid={tid}")
    try:
        data = call_optionalpha_api(payload)
        print(f"[BOT SCANNERS API] Response length: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, dict) and data.get("error"):
            return jsonify({"error": data.get("error"), "details": data}), 503

        triggers = []
        autos = []
        notes = None
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                api_name = item.get("api")
                item_data = item.get("data")
                if api_name == "triggers.list" and isinstance(item_data, dict):
                    triggers = item_data.get("triggers") or []
                    autos = item_data.get("autos") or []
                elif api_name == "bot.getNotes":
                    notes = item_data
        print(f"[BOT SCANNERS API] Loaded {len(triggers)} triggers for {bot_id}")
        return jsonify({
            "status": "ok",
            "bot_id": bot_id,
            "triggers": triggers,
            "autos": autos,
            "notes": notes,
            "raw": data,
        })
    except FileNotFoundError as e:
        print(f"[BOT SCANNERS API] Session file missing: {e}")
        return jsonify({"error": "Session file not found. Run optionalpha_probe.py to refresh session.json."}), 503
    except Exception as e:
        print(f"[BOT SCANNERS API] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/routine-details")
def api_routine_details():
    """Fetch detailed routine/scanner configuration from OptionAlpha."""
    import time as _time_mod
    from optionalpha_client import call_optionalpha_api, SESSION_FILE

    routine_id = request.args.get("id")
    if not routine_id:
        return jsonify({"error": "Missing routine id"}), 400

    tid = int(_time_mod.time() * 1000)
    payload = [
        {
            "t": "rpc",
            "tid": f"{tid}-10005",
            "api": "routines.details",
            "args": [routine_id],
        }
    ]
    print(f"[ROUTINE DETAILS API] Calling routines.details for {routine_id}, tid={tid}")
    try:
        data = call_optionalpha_api(payload)
        print(f"[ROUTINE DETAILS API] Response length: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, dict) and data.get("error"):
            return jsonify({"error": data.get("error"), "details": data}), 503

        routine = None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("api") == "routines.details":
                    routine = item.get("data")
                    break
        print(f"[ROUTINE DETAILS API] Loaded routine {routine_id}")
        return jsonify({
            "status": "ok",
            "routine_id": routine_id,
            "routine": routine,
            "raw": data,
        })
    except FileNotFoundError as e:
        print(f"[ROUTINE DETAILS API] Session file missing: {e}")
        return jsonify({"error": "Session file not found. Run optionalpha_probe.py to refresh session.json."}), 503
    except Exception as e:
        print(f"[ROUTINE DETAILS API] Error: {e}")
        return jsonify({"error": str(e)}), 500

def _ensure_magnet_days_table() -> None:
    """Create magnet_days table if it does not exist."""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS magnet_days (
                ndate              INTEGER PRIMARY KEY,
                modal_ks           INTEGER,
                modal_ks_pct       REAL,
                median_ratio       REAL,
                ratio_dev          REAL,
                ratio_rank         INTEGER,
                median_dominance   REAL,
                snap_count         INTEGER,
                avg_net_gex        REAL,
                updated_at         TEXT
            )
        """)
        # Migrations for older schemas
        for col_def in [
            "ALTER TABLE magnet_days ADD COLUMN median_dominance REAL",
            "ALTER TABLE magnet_days ADD COLUMN ks_sequence TEXT",
            "ALTER TABLE magnet_days ADD COLUMN anchor_ks INTEGER",
            "ALTER TABLE magnet_days ADD COLUMN anchor_ntime INTEGER",
            "ALTER TABLE magnet_days ADD COLUMN anchor_dominance REAL",
            "ALTER TABLE magnet_days ADD COLUMN anchor_balance REAL",
            "ALTER TABLE magnet_days ADD COLUMN median_balance REAL",
            "ALTER TABLE magnet_days ADD COLUMN avg_total_abs REAL",
            "ALTER TABLE magnet_days ADD COLUMN magnet_score REAL",
            "ALTER TABLE magnet_days ADD COLUMN qualified INTEGER DEFAULT 0",
            "ALTER TABLE magnet_days ADD COLUMN snap_1200_ks INTEGER",
            "ALTER TABLE magnet_days ADD COLUMN snap_1200_dominance REAL",
            "ALTER TABLE magnet_days ADD COLUMN snap_1200_balance REAL",
            "ALTER TABLE magnet_days ADD COLUMN snap_1200_call_gex REAL",
            "ALTER TABLE magnet_days ADD COLUMN snap_1200_put_gex REAL",
            "ALTER TABLE magnet_days ADD COLUMN qualified_1200 INTEGER DEFAULT 0",
        ]:
            try:
                con.execute(col_def)
            except Exception:
                pass


def _compute_magnet_days() -> dict:
    """Recompute magnet_days table for all historical dates.

    Qualification rules (both must pass):
      1. Find the first snapshot in 09:35-12:00 where the dominant strike's
         own call/put balance >= 67% (i.e. neither side > 1.5x the other).
         That snapshot's strike becomes the 'anchor_ks'.
      2. That exact anchor_ks must remain the #1 dominant strike
         (highest proximity-weighted abs GEX) at every subsequent snapshot
         through 15:55.

    Ranking (qualified days only, higher = better):
      magnet_score = anchor_dominance * W_DOM
                   + anchor_balance   * W_BAL
                   + avg_total_abs_pctile * W_GEX
      Default weights: 1/1/1 (equal). Frontend offers radio buttons.
    """
    import json as _j
    import math as _math
    import statistics as _stat
    from collections import Counter
    from datetime import datetime as _dt

    PROX_BW    = 50.0
    MIN_BAL    = 67.0   # min(|cg|,|pg|)/max * 100 >= this to qualify
    ANCHOR_MAX_NTIME = 1200  # anchor must be found by this snapshot

    def _v(row, key):
        return row.get(key, 0) or 0

    def snap_metrics(strikes, uprice):
        """Return (top_strike_dict, dominance_pct, ks_balance_pct, total_abs) for one snapshot."""
        if not strikes:
            return None, 0, 0, 0
        total_abs = sum(abs(_v(s, "abs")) for s in strikes)
        top = max(strikes, key=lambda s: abs(_v(s, "abs")) * _math.exp(
            -0.5 * ((abs(_v(s, "strike") - uprice) / PROX_BW) ** 2)))
        top_abs = abs(_v(top, "abs"))
        dom = (top_abs / total_abs * 100.0) if total_abs else 0.0
        cg = abs(_v(top, "cg"))
        pg = abs(_v(top, "pg"))
        bal = (min(cg, pg) / max(cg, pg) * 100.0) if max(cg, pg) > 0 else 0.0
        return top, dom, bal, total_abs

    today_ndate = int(_dt.now().strftime("%Y%m%d"))

    with _db() as con:
        dates = [r[0] for r in con.execute(
            "SELECT DISTINCT ndate FROM gex_strike_window "
            "WHERE ntime >= 935 AND ntime <= 1555 "
            "ORDER BY ndate"
        ).fetchall()]

    rows = []
    for ndate in dates:
        if ndate == today_ndate:
            continue

        with _db() as con:
            snaps = con.execute(
                "SELECT ntime, price, data FROM gex_strike_window "
                "WHERE ndate=? AND ntime >= 935 AND ntime <= 1555 ORDER BY ntime",
                (ndate,)
            ).fetchall()

        if len(snaps) < 2:
            continue

        # --- Parse all snapshots first ---
        parsed = []  # [(ntime, uprice, strikes, top, dom, bal, total_abs)]
        for ntime, price, data in snaps:
            try:
                strikes = _j.loads(data)
            except Exception:
                continue
            if not strikes:
                continue
            uprice = price or 0.0
            top, dom, bal, total_abs = snap_metrics(strikes, uprice)
            if top is None:
                continue
            parsed.append((ntime, uprice, strikes, top, dom, bal, total_abs))

        if len(parsed) < 2:
            continue

        # --- Find anchor: first qualifying snapshot in 935-1200 ---
        anchor_ks = None
        anchor_ntime = None
        anchor_dominance = None
        anchor_balance = None
        for ntime, uprice, strikes, top, dom, bal, total_abs in parsed:
            if ntime > ANCHOR_MAX_NTIME:
                break
            if bal >= MIN_BAL:
                anchor_ks       = int(_v(top, "strike"))
                anchor_ntime    = ntime
                anchor_dominance = round(dom, 2)
                anchor_balance   = round(bal, 2)
                break

        # --- Qualification: anchor_ks must be #1 dominant at every snapshot ---
        qualified = 0
        if anchor_ks is not None:
            qualified = 1
            # Check every snapshot from anchor onwards
            anchor_found = False
            for ntime, uprice, strikes, top, dom, bal, total_abs in parsed:
                if ntime < anchor_ntime:
                    continue
                anchor_found = True
                top_ks = int(_v(top, "strike"))
                if top_ks != anchor_ks:
                    qualified = 0
                    break
            if not anchor_found:
                qualified = 0

        # --- Capture 1200 snapshot metrics ---
        snap_1200_ks = None
        snap_1200_dom = None
        snap_1200_bal = None
        snap_1200_cg = None
        snap_1200_pg = None
        qualified_1200 = 0
        for ntime, uprice, strikes, top, dom, bal, total_abs in parsed:
            if ntime == 1200:
                snap_1200_ks  = int(_v(top, "strike"))
                snap_1200_dom = round(dom, 2)
                snap_1200_bal = round(bal, 2)
                snap_1200_cg  = round(_v(top, "cg"), 2)
                snap_1200_pg  = round(_v(top, "pg"), 2)
                if dom >= 20.0 and bal >= 80.0:
                    qualified_1200 = 1
                break

        # --- Compute day-wide stats (all snapshots) ---
        key_strikes_seen = []
        ks_sequence = []
        ratios = []
        net_gexes = []
        dominances = []
        total_abs_list = []

        for ntime, uprice, strikes, top, dom, bal, total_abs in parsed:
            ks = int(_v(top, "strike"))
            key_strikes_seen.append(ks)
            ks_sequence.append([ntime, ks])
            dominances.append(dom)
            total_abs_list.append(total_abs)
            total_call_gex = sum(_v(s, "cg") for s in strikes)
            total_put_gex  = sum(_v(s, "pg") for s in strikes)
            abs_cg = abs(total_call_gex)
            abs_pg = abs(total_put_gex)
            if abs_cg >= abs_pg:
                ratio = (abs_cg / abs_pg) if abs_pg else 0.0
            else:
                ratio = -(abs_pg / abs_cg) if abs_cg else 0.0
            ratios.append(ratio)
            net_gexes.append(total_call_gex + total_put_gex)

        if not key_strikes_seen:
            continue

        counter = Counter(key_strikes_seen)
        modal_ks      = counter.most_common(1)[0][0]
        modal_ks_pct  = round(key_strikes_seen.count(modal_ks) / len(key_strikes_seen) * 100.0, 1)
        median_ratio  = round(_stat.median(ratios), 3)
        ratio_dev     = round(abs(abs(median_ratio) - 1.0), 4)
        avg_net_gex   = round(sum(net_gexes) / len(net_gexes), 2) if net_gexes else None
        median_dom    = round(_stat.median(dominances), 2) if dominances else None
        avg_total_abs = round(sum(total_abs_list) / len(total_abs_list), 2) if total_abs_list else None

        rows.append({
            "ndate":              ndate,
            "modal_ks":           modal_ks,
            "modal_ks_pct":       modal_ks_pct,
            "median_ratio":       median_ratio,
            "ratio_dev":          ratio_dev,
            "ratio_rank":         0,  # set after
            "median_dominance":   median_dom,
            "snap_count":         len(parsed),
            "avg_net_gex":        avg_net_gex,
            "ks_sequence":        _j.dumps(ks_sequence),
            "anchor_ks":          anchor_ks,
            "anchor_ntime":       anchor_ntime,
            "anchor_dominance":   anchor_dominance,
            "anchor_balance":     anchor_balance,
            "avg_total_abs":      avg_total_abs,
            "magnet_score":       None,  # set after
            "qualified":          qualified,
            "snap_1200_ks":       snap_1200_ks,
            "snap_1200_dominance": snap_1200_dom,
            "snap_1200_balance":  snap_1200_bal,
            "snap_1200_call_gex": snap_1200_cg,
            "snap_1200_put_gex":  snap_1200_pg,
            "qualified_1200":     qualified_1200,
            "updated_at":         _dt.now().isoformat(timespec="seconds"),
        })

    # --- Score and rank qualified rows ---
    # Normalise avg_total_abs to percentile (0-100) across all rows
    abs_vals = [r["avg_total_abs"] for r in rows if r["avg_total_abs"] is not None]
    abs_vals_sorted = sorted(abs_vals)
    n_abs = len(abs_vals_sorted)

    def abs_pctile(v):
        if v is None or n_abs == 0:
            return 0.0
        idx = sum(1 for x in abs_vals_sorted if x <= v)
        return round(idx / n_abs * 100.0, 2)

    for row in rows:
        if row["qualified"]:
            dom  = row["anchor_dominance"] or 0
            bal  = row["anchor_balance"]   or 0
            gex  = abs_pctile(row["avg_total_abs"])
            row["magnet_score"] = round(dom + bal + gex, 4)
        else:
            row["magnet_score"] = None

    # ratio_rank: all rows ranked by ratio_dev ASC (keep for reference)
    rows.sort(key=lambda r: (r["ratio_dev"], -r["snap_count"]))
    for rank, row in enumerate(rows, 1):
        row["ratio_rank"] = rank

    # Insert new rows only (incremental)
    with _db() as con:
        existing = set(r[0] for r in con.execute("SELECT ndate FROM magnet_days").fetchall())

    new_rows = [r for r in rows if r["ndate"] not in existing]

    with _db() as con:
        for row in new_rows:
            con.execute("""
                INSERT OR IGNORE INTO magnet_days
                    (ndate, modal_ks, modal_ks_pct, median_ratio, ratio_dev,
                     ratio_rank, median_dominance, snap_count, avg_net_gex,
                     ks_sequence, anchor_ks, anchor_ntime, anchor_dominance,
                     anchor_balance, avg_total_abs, magnet_score, qualified,
                     snap_1200_ks, snap_1200_dominance, snap_1200_balance,
                     snap_1200_call_gex, snap_1200_put_gex, qualified_1200,
                     updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                row["ndate"], row["modal_ks"], row["modal_ks_pct"],
                row["median_ratio"], row["ratio_dev"], row["ratio_rank"],
                row["median_dominance"], row["snap_count"], row["avg_net_gex"],
                row["ks_sequence"], row["anchor_ks"], row["anchor_ntime"],
                row["anchor_dominance"], row["anchor_balance"],
                row["avg_total_abs"], row["magnet_score"], row["qualified"],
                row["snap_1200_ks"], row["snap_1200_dominance"], row["snap_1200_balance"],
                row["snap_1200_call_gex"], row["snap_1200_put_gex"], row["qualified_1200"],
                row["updated_at"],
            ))

    return {"status": "ok", "computed": len(new_rows), "skipped": len(rows) - len(new_rows)}


@app.route("/api/magnet/compute")
def api_magnet_compute():
    """Incremental compute of magnet_days — adds missing dates only."""
    result = _compute_magnet_days()
    return jsonify(result)


@app.route("/api/magnet/live")
def api_magnet_live():
    """Return live magnet metrics for today — never persisted.

    Reads today's gex_strike_window rows (RTH only: 930-1600), computes the
    same metrics as _compute_magnet_days, then scores vs all historical
    magnet_days rows to derive a provisional combined rank.
    """
    import json as _j
    import math as _math
    import statistics as _stat
    from datetime import datetime as _dt

    PROX_BW = 50.0

    def _v(row, key):
        return row.get(key, 0) or 0

    et_now = get_et_now()
    today_ndate = int(et_now.strftime("%Y%m%d"))
    current_ntime = int(et_now.strftime("%H%M"))
    in_rth = 935 < current_ntime < 1555

    # Fetch today's live RTH snapshots (exclusive bounds, source=gex only)
    with _db() as con:
        snaps = con.execute(
            "SELECT ntime, price, data FROM gex_strike_window "
            "WHERE ndate=? AND source='gex' AND ntime > 935 AND ntime < 1555 "
            "ORDER BY ntime",
            (today_ndate,)
        ).fetchall()

    if not snaps:
        return jsonify({
            "status": "no_data",
            "message": "No live snapshots for today yet.",
            "in_rth": in_rth,
            "ndate": today_ndate,
        })

    # Compute metrics (same logic as _compute_magnet_days)
    key_strikes_seen = []
    ratios = []
    dominances = []
    net_gexes = []

    for ntime, price, data in snaps:
        try:
            strikes = _j.loads(data)
        except Exception:
            continue
        if not strikes:
            continue
        uprice = price or 0.0

        try:
            top = max(strikes, key=lambda s: abs(_v(s, "abs")) * _math.exp(
                -0.5 * ((abs(_v(s, "strike") - uprice) / PROX_BW) ** 2)))
            key_strikes_seen.append(int(_v(top, "strike")))
        except Exception:
            continue

        total_call_gex = sum(_v(s, "cg") for s in strikes)
        total_put_gex  = sum(_v(s, "pg") for s in strikes)
        abs_cg = abs(total_call_gex)
        abs_pg = abs(total_put_gex)
        if abs_cg >= abs_pg:
            ratio = (abs_cg / abs_pg) if abs_pg else 0.0
        else:
            ratio = -(abs_pg / abs_cg) if abs_cg else 0.0
        ratios.append(ratio)
        net_gexes.append(total_call_gex + total_put_gex)

        try:
            total_abs = sum(abs(_v(s, "abs")) for s in strikes)
            top_abs   = abs(_v(top, "abs"))
            if total_abs > 0:
                dominances.append(top_abs / total_abs * 100.0)
        except Exception:
            pass

    if not key_strikes_seen or not ratios:
        return jsonify({
            "status": "insufficient",
            "message": "Snapshots found but could not compute metrics.",
            "snap_count": len(snaps),
            "in_rth": in_rth,
            "ndate": today_ndate,
        })

    from collections import Counter
    counter = Counter(key_strikes_seen)
    modal_ks     = counter.most_common(1)[0][0]
    modal_ks_pct = round(key_strikes_seen.count(modal_ks) / len(key_strikes_seen) * 100.0, 1)
    median_ratio = round(_stat.median(ratios), 3)
    ratio_dev    = round(abs(abs(median_ratio) - 1.0), 4)
    med_dominance = round(_stat.median(dominances), 2) if dominances else None
    snap_count   = len(key_strikes_seen)

    # Provisional ranking vs historical magnet_days
    with _db() as con:
        hist = con.execute(
            "SELECT ndate, ratio_dev, median_dominance, snap_count FROM magnet_days ORDER BY ndate"
        ).fetchall()

    total_hist = len(hist)
    prov_rank = None
    prov_rank_combined = None

    if total_hist > 0:
        # Ratio-only rank: count historical days with better (lower) ratio_dev
        better_ratio = sum(1 for h in hist if h[1] < ratio_dev)
        prov_rank = better_ratio + 1  # provisional ratio rank

        # Combined rank using default weight=2 for dominance
        def combined_score(dom, rdev, weight=2):
            d = dom if dom is not None else 0
            return d * weight - rdev * 100

        today_score = combined_score(med_dominance, ratio_dev)
        hist_scores = [combined_score(h[2], h[1]) for h in hist]
        better_combined = sum(1 for s in hist_scores if s > today_score)
        prov_rank_combined = better_combined + 1

    return jsonify({
        "status": "ok",
        "in_rth": in_rth,
        "ndate": today_ndate,
        "current_ntime": current_ntime,
        "snap_count": snap_count,
        "modal_ks": modal_ks,
        "modal_ks_pct": modal_ks_pct,
        "median_ratio": median_ratio,
        "ratio_dev": ratio_dev,
        "median_dominance": med_dominance,
        "prov_rank_ratio": prov_rank,
        "prov_rank_combined": prov_rank_combined,
        "total_hist": total_hist,
        "key_strikes_seen": key_strikes_seen,
    })


@app.route("/api/magnet/clear")
def api_magnet_clear():
    """Clear all rows from magnet_days table."""
    with _db() as con:
        deleted = con.execute("DELETE FROM magnet_days").rowcount
    return jsonify({"status": "ok", "deleted": deleted})


@app.route("/api/magnet/load-spx-csv", methods=["POST"])
def api_magnet_load_spx_csv():
    """Parse and load SPX 5-min CSV data into spx_ohlc_5min table.

    Expected CSV format (from user's data source):
        Date, Time, Open, High, Low, Close, Up, Down, Volume
        mm/dd/yyyy, HH:MM, ...
    Time is UTC-1 (offset -60 min from ET), so 08:35 = ET 09:35.
    Only RTH bars (ET 09:30-16:00) are stored.
    """
    import csv, io
    from datetime import datetime as _dt, timedelta as _td

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    try:
        content = f.read().decode("utf-8-sig")  # strip BOM if present
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 400

    rows = []
    errors = []
    reader = csv.DictReader(io.StringIO(content))
    for i, row in enumerate(reader, 2):
        try:
            # Parse date mm/dd/yyyy
            date_str = row.get("Date", "").strip()
            time_str = row.get("Time", "").strip()
            dt = _dt.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M")
            # Add 60 minutes to convert from UTC-1 to ET
            dt_et = dt + _td(minutes=60)
            ndate = int(dt_et.strftime("%Y%m%d"))
            ntime = int(dt_et.strftime("%H%M"))
            # Only keep RTH bars
            if ntime < 930 or ntime > 1600:
                continue
            open_  = float(row.get("Open",  "0").strip())
            high   = float(row.get("High",  "0").strip())
            low    = float(row.get("Low",   "0").strip())
            close  = float(row.get("Close", "0").strip())
            rows.append((ndate, ntime, open_, high, low, close))
        except Exception as e:
            errors.append(f"Row {i}: {e}")
            if len(errors) > 10:
                break

    if not rows:
        return jsonify({"error": "No valid RTH rows found", "parse_errors": errors}), 400

    # Delete existing rows for dates in this file so CSV always wins over any existing data
    affected_dates = list(set(r[0] for r in rows))
    with _db() as con:
        placeholders = ",".join("?" * len(affected_dates))
        con.execute(f"DELETE FROM spx_ohlc_5min WHERE ndate IN ({placeholders})", affected_dates)
        con.executemany(
            "INSERT INTO spx_ohlc_5min (ndate, ntime, open, high, low, close) VALUES (?,?,?,?,?,?)",
            rows
        )

    dates_loaded = len(affected_dates)
    return jsonify({
        "status": "ok",
        "rows_loaded": len(rows),
        "dates_loaded": dates_loaded,
        "parse_errors": errors,
    })


@app.route("/api/magnet/clear-spx")
def api_magnet_clear_spx():
    """Clear all rows from spx_ohlc_5min table."""
    with _db() as con:
        deleted = con.execute("DELETE FROM spx_ohlc_5min").rowcount
    return jsonify({"status": "ok", "deleted": deleted})


@app.route("/api/magnet/spx-stats")
def api_magnet_spx_stats():
    """Return summary stats for spx_ohlc_5min table."""
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT ndate), MIN(ndate), MAX(ndate) FROM spx_ohlc_5min"
        ).fetchone()
    return jsonify({
        "total_bars": row[0],
        "distinct_dates": row[1],
        "total_dates": row[1],
        "min_date": row[2],
        "max_date": row[3],
    })


@app.route("/api/magnet/spx-dates")
def api_magnet_spx_dates():
    """Return sorted list of ISO dates that have 5-min SPX data."""
    with _db() as con:
        rows = con.execute(
            "SELECT DISTINCT ndate FROM spx_ohlc_5min ORDER BY ndate DESC"
        ).fetchall()
    dates = []
    for (nd,) in rows:
        s = str(nd)
        dates.append(f"{s[:4]}-{s[4:6]}-{s[6:]}")
    return jsonify({"dates": dates})


@app.route("/api/spx-stale-warning")
def api_spx_stale_warning():
    """Return whether yesterday's SPX 5-min data is missing (stale check)."""
    import datetime as _datetime
    today = _datetime.date.today()
    # Step back to find last trading day (skip weekends)
    day = today - _datetime.timedelta(days=1)
    while day.weekday() >= 5:  # 5=Sat, 6=Sun
        day -= _datetime.timedelta(days=1)
    expected = int(day.strftime("%Y%m%d"))
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM spx_ohlc_5min WHERE ndate=?", (expected,)
        ).fetchone()
    missing = row[0] == 0
    return jsonify({
        "stale": missing,
        "expected_date": str(expected),
        "expected_iso": day.isoformat(),
    })


@app.route("/api/magnet/spx-chart")
def api_magnet_spx_chart():
    """Return SPX price data for a date for the magnet chart popup.

    Returns 5-min OHLC bars if available, otherwise GEX snapshot prices as fallback.
    Query param: date=YYYY-MM-DD
    """
    date_iso = request.args.get("date", "")
    if not date_iso:
        return jsonify({"error": "date required"}), 400
    try:
        ndate = int(date_iso.replace("-", ""))
    except ValueError:
        return jsonify({"error": "invalid date"}), 400

    # Try 5-min SPX OHLC bars first (RTH only)
    with _db() as con:
        bar_rows = con.execute(
            "SELECT ntime, open, high, low, close FROM spx_ohlc_5min "
            "WHERE ndate=? AND ntime >= 930 AND ntime <= 1600 ORDER BY ntime",
            (ndate,)
        ).fetchall()

    spx_bars = [{"ntime": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4]}
                for r in bar_rows]

    # Fallback: GEX snapshot uprice values
    snap_prices = []
    if not spx_bars:
        with _db() as con:
            snap_rows = con.execute(
                "SELECT ntime, uprice FROM gex_strike_window "
                "WHERE ndate=? AND ntime >= 935 AND ntime <= 1555 ORDER BY ntime",
                (ndate,)
            ).fetchall()
        snap_prices = [{"ntime": r[0], "price": r[1]} for r in snap_rows if r[1]]

    return jsonify({
        "ndate": ndate,
        "spx_bars": spx_bars,
        "snap_prices": snap_prices,
        "source": "5min" if spx_bars else "gex_snap",
    })


@app.route("/api/magnet/rows")
def api_magnet_rows():
    """Return qualified magnet_days rows ordered by magnet_score DESC."""
    with _db() as con:
        rows = con.execute("""
            SELECT ndate, modal_ks, modal_ks_pct, median_ratio,
                   ratio_dev, ratio_rank, median_dominance, snap_count, avg_net_gex, updated_at,
                   ks_sequence, anchor_ks, anchor_ntime, anchor_dominance,
                   anchor_balance, avg_total_abs, magnet_score, qualified
            FROM magnet_days
            WHERE qualified = 1
            ORDER BY magnet_score DESC
        """).fetchall()
    cols = ["ndate", "modal_ks", "modal_ks_pct", "median_ratio",
            "ratio_dev", "ratio_rank", "median_dominance", "snap_count", "avg_net_gex", "updated_at",
            "ks_sequence", "anchor_ks", "anchor_ntime", "anchor_dominance",
            "anchor_balance", "avg_total_abs", "magnet_score", "qualified"]
    import json as _j
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        if d.get("ks_sequence"):
            try:
                d["ks_sequence"] = _j.loads(d["ks_sequence"])
            except Exception:
                d["ks_sequence"] = []
        else:
            d["ks_sequence"] = []
        result.append(d)
    return jsonify({"rows": result})


@app.route("/api/magnet/rows-1200")
def api_magnet_rows_1200():
    """Return rows where qualified_1200=1 (dom>=20% and balance>=80% at 12:00), ordered by dominance DESC."""
    with _db() as con:
        rows = con.execute("""
            SELECT ndate, snap_1200_ks, snap_1200_dominance, snap_1200_balance,
                   snap_1200_call_gex, snap_1200_put_gex, snap_count,
                   avg_total_abs, ks_sequence
            FROM magnet_days
            WHERE snap_1200_ks IS NOT NULL
            ORDER BY snap_1200_dominance DESC
        """).fetchall()
    cols = ["ndate", "snap_1200_ks", "snap_1200_dominance", "snap_1200_balance",
            "snap_1200_call_gex", "snap_1200_put_gex", "snap_count",
            "avg_total_abs", "ks_sequence"]
    import json as _j
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        if d.get("ks_sequence"):
            try:
                d["ks_sequence"] = _j.loads(d["ks_sequence"])
            except Exception:
                d["ks_sequence"] = []
        else:
            d["ks_sequence"] = []
        result.append(d)
    return jsonify({"rows": result})


@app.route("/api/magnet/debug/<int:ndate>")
def api_magnet_debug(ndate):
    """Return a full snap-by-snap diagnostic for one date showing exactly why it passed/failed Table 1 and Table 2."""
    import json as _j, math as _math

    PROX_BW = 50.0
    MIN_BAL_T1 = 67.0
    MIN_DOM_T2 = 20.0
    MIN_BAL_T2 = 80.0

    def _v(d, k):
        v = d.get(k, 0)
        return v if v is not None else 0

    with _db() as con:
        raw = con.execute(
            "SELECT ntime, price, data FROM gex_strike_window "
            "WHERE ndate=? AND source='gex' AND ntime>=935 AND ntime<=1555 ORDER BY ntime",
            (ndate,)
        ).fetchall()
        db_row = con.execute(
            "SELECT qualified, qualified_1200, anchor_ks, anchor_ntime, anchor_dominance, "
            "anchor_balance, snap_1200_ks, snap_1200_dominance, snap_1200_balance, magnet_score "
            "FROM magnet_days WHERE ndate=?", (ndate,)
        ).fetchone()

    if not raw:
        return jsonify({"error": f"No snapshots found for {ndate}"}), 404

    # Parse each snap
    snaps = []
    for ntime, uprice, data in raw:
        strikes = _j.loads(data) if data else []
        if not strikes:
            continue
        uprice = uprice or 0.0
        total_abs = sum(abs(_v(s, "abs")) for s in strikes)
        top = max(strikes, key=lambda s: abs(_v(s, "abs")) * _math.exp(
            -0.5 * ((abs(_v(s, "strike") - uprice) / PROX_BW) ** 2)))
        top_abs = abs(_v(top, "abs"))
        dom = round(top_abs / total_abs * 100, 2) if total_abs else 0
        cg = abs(_v(top, "cg"))
        pg = abs(_v(top, "pg"))
        bal = round(min(cg, pg) / max(cg, pg) * 100, 2) if max(cg, pg) > 0 else 0
        snaps.append({
            "ntime": ntime,
            "spx": round(uprice, 1),
            "ks": int(_v(top, "strike")),
            "dom": dom,
            "bal": bal,
            "cg_b": round(cg / 1e9, 3),
            "pg_b": round(pg / 1e9, 3),
        })

    # --- Table 1 trace ---
    t1_anchor = None
    t1_anchor_time = None
    t1_events = []
    t1_pass = False
    for s in snaps:
        if t1_anchor is None:
            if s["ntime"] <= 1200 and s["bal"] >= MIN_BAL_T1:
                t1_anchor = s["ks"]
                t1_anchor_time = s["ntime"]
                t1_events.append({"ntime": s["ntime"], "status": "ANCHOR", "ks": s["ks"],
                                   "dom": s["dom"], "bal": s["bal"], "note": f"First balanced snap (bal={s['bal']:.1f}% ≥ {MIN_BAL_T1}%)"})
            elif s["ntime"] <= 1200:
                t1_events.append({"ntime": s["ntime"], "status": "SKIP", "ks": s["ks"],
                                   "dom": s["dom"], "bal": s["bal"], "note": f"bal={s['bal']:.1f}% < {MIN_BAL_T1}% — not balanced enough"})
            else:
                t1_events.append({"ntime": s["ntime"], "status": "NO_ANCHOR", "ks": s["ks"],
                                   "dom": s["dom"], "bal": s["bal"], "note": "Past 12:00, no anchor found — FAIL"})
                break
        else:
            if s["ks"] == t1_anchor:
                t1_events.append({"ntime": s["ntime"], "status": "OK", "ks": s["ks"],
                                   "dom": s["dom"], "bal": s["bal"], "note": f"Anchor {t1_anchor} still dominant"})
            else:
                t1_events.append({"ntime": s["ntime"], "status": "FAIL", "ks": s["ks"],
                                   "dom": s["dom"], "bal": s["bal"],
                                   "note": f"KS changed {t1_anchor}→{s['ks']} — DISQUALIFIED"})
                break
    else:
        if t1_anchor is not None:
            t1_pass = True

    t1_verdict = "PASS" if t1_pass else "FAIL"
    if t1_anchor is None:
        t1_fail_reason = "No balanced snap (bal ≥ 67%) found before 12:00"
    elif not t1_pass:
        fail_ev = next((e for e in t1_events if e["status"] in ("FAIL", "NO_ANCHOR")), None)
        t1_fail_reason = fail_ev["note"] if fail_ev else "Unknown"
    else:
        t1_fail_reason = None

    # --- Table 2 trace ---
    snap_1200 = next((s for s in snaps if s["ntime"] == 1200), None)
    if snap_1200:
        t2_dom_ok  = snap_1200["dom"] >= MIN_DOM_T2
        t2_bal_ok  = snap_1200["bal"] >= MIN_BAL_T2
        t2_pass    = t2_dom_ok and t2_bal_ok
        t2_reasons = []
        if not t2_dom_ok:
            t2_reasons.append(f"Dom {snap_1200['dom']:.1f}% < {MIN_DOM_T2}%")
        if not t2_bal_ok:
            t2_reasons.append(f"Balance {snap_1200['bal']:.1f}% < {MIN_BAL_T2}%")
        t2_verdict     = "PASS" if t2_pass else "FAIL"
        t2_fail_reason = "; ".join(t2_reasons) if t2_reasons else None
    else:
        snap_1200      = None
        t2_verdict     = "NO_DATA"
        t2_fail_reason = "No 12:00 snapshot exists for this date"

    return jsonify({
        "ndate": ndate,
        "snap_count": len(snaps),
        "table1": {
            "verdict": t1_verdict,
            "anchor_ks": t1_anchor,
            "anchor_time": t1_anchor_time,
            "fail_reason": t1_fail_reason,
            "trace": t1_events,
        },
        "table2": {
            "verdict": t2_verdict,
            "snap_1200": snap_1200,
            "fail_reason": t2_fail_reason,
        },
        "db_stored": dict(zip(
            ["qualified","qualified_1200","anchor_ks","anchor_ntime","anchor_dominance",
             "anchor_balance","snap_1200_ks","snap_1200_dominance","snap_1200_balance","magnet_score"],
            db_row
        )) if db_row else None,
    })


@app.route("/trade-analysis")
def trade_analysis_page():
    from time import time
    from flask import make_response as _make_response
    resp = _make_response(render_template("trade_analysis.html", cache_bust=int(time())))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/trade-analysis/parse", methods=["POST"])
def api_trade_analysis_parse():
    """Accept a CSV upload of trade data and return parsed rows as JSON."""
    import csv, io
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    content = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    FIELDS = ["botName","type","description","symbol","status","quantity","daysInTrade",
              "openPrice","closePrice","premium","pnl","ror","returnPct","risk","ev","alpha",
              "highReturnPct","lowReturnPct","highReturnPctDate","lowReturnPctDate",
              "expiration","openDate","closeDate","tags","underlyingOpen","underlyingClose"]
    trades = []
    for i, row in enumerate(reader):
        t = {}
        for f_name in FIELDS:
            t[f_name] = row.get(f_name, "").strip()
        # Coerce numerics
        for num_f in ["openPrice","closePrice","premium","pnl","ror","returnPct","risk",
                      "underlyingOpen","underlyingClose","quantity","daysInTrade"]:
            try:
                t[num_f] = float(t[num_f]) if t[num_f] not in ("", None) else None
            except ValueError:
                t[num_f] = None
        t["_id"] = i
        trades.append(t)
    return jsonify({"trades": trades, "count": len(trades)})


@app.route("/magnet")
def magnet_page():
    from time import time
    from flask import make_response as _make_response
    resp = _make_response(render_template("magnet.html", cache_bust=int(time())))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/gex-distribution")
def gex_distribution():
    from time import time
    return render_template("gex_distribution.html", cache_bust=int(time()))

@app.route("/daily-analysis")
def daily_analysis():
    from time import time
    return render_template("daily_analysis.html", cache_bust=int(time()))

@app.route("/old")
def index_old():
    from time import time
    return render_template("gex_viewer.html", cache_bust=int(time()))

@app.route("/simple")
def simple():
    from time import time
    return render_template("gex_viewer_simple.html", cache_bust=int(time()))


@app.route("/analysis")
def analysis():
    from time import time
    return render_template("analysis.html", cache_bust=int(time()))

@app.route("/hscatter")
def hscatter():
    from time import time
    return render_template("hscatter.html", cache_bust=int(time()))

@app.route("/spx")
def spx():
    from time import time
    return render_template("spx.html", cache_bust=int(time()))

@app.route("/csv")
def csv_page():
    from time import time
    return render_template("csv.html", cache_bust=int(time()))


@app.route("/api/dates")
def api_dates():
    """Route now delegates to DatesController (Phase 5 migration)."""
    return DatesController.get_dates()


# MVC refactoring routes (Phase 2) - new controller-based implementations
@app.route("/mvc/api/dates")
def mvc_api_dates():
    """MVC version of /api/dates using DatesController."""
    return DatesController.get_dates()


@app.route("/mvc/api/snapshots")
def mvc_api_snapshots():
    """MVC version of /api/snapshots using SnapshotController."""
    return SnapshotController.get_snapshots()


@app.route("/mvc/api/snapshot")
def mvc_api_snapshot():
    """MVC version of /api/snapshot using SnapshotController."""
    return SnapshotController.get_snapshot()


@app.route("/mvc/api/snapshots/summary")
def mvc_api_snapshots_summary():
    """MVC version of /api/snapshots/summary using SnapshotController."""
    return SnapshotController.get_snapshots_summary()


@app.route("/mvc/api/snapshots/all")
def mvc_api_snapshots_all():
    """MVC version of /api/snapshots/all using SnapshotController."""
    return SnapshotController.get_snapshots_all()


# MVC admin routes for data quality tools
@app.route("/mvc/api/admin/invalid-snapshots")
def mvc_api_admin_invalid_snapshots():
    """Get list of snapshots with invalid/null key fields."""
    return AdminController.get_invalid_snapshots()


@app.route("/mvc/api/admin/snapshot-json")
def mvc_api_admin_snapshot_json():
    """Get raw JSON data blob for a specific snapshot."""
    return AdminController.get_json_from_snapshot()


@app.route("/mvc/api/admin/rebuild-snapshot")
def mvc_api_admin_rebuild_snapshot():
    """Rebuild snapshot flat columns from raw JSON data blob."""
    return AdminController.rebuild_snapshot_from_json()


# MVC percentiles route
@app.route("/mvc/api/percentiles")
def mvc_api_percentiles():
    """MVC version of /api/percentiles using PercentilesController."""
    return PercentilesController.get_percentiles()


# MVC trade signals route
@app.route("/mvc/api/trade-signals")
def mvc_api_trade_signals():
    """MVC version of /api/trade-signals using TradeSignalsController."""
    return TradeSignalsController.get_trade_signals()


# MVC narrative route
@app.route("/mvc/api/narrative")
def mvc_api_narrative():
    """MVC version of /api/narrative using NarrativeController."""
    return NarrativeController.get_narrative()


# MVC csv-data route
@app.route("/mvc/api/csv-data")
def mvc_api_csv_data():
    """MVC version of /api/csv-data using CsvController."""
    return CsvController.get_csv_data()


# MVC spx-prices route
@app.route("/mvc/api/spx-prices")
def mvc_api_spx_prices():
    """MVC version of /api/spx-prices using SpxController."""
    return SpxController.get_spx_prices()


CSV_SUMMARY = BASE_DIR / "results" / "daily_gex_summary-concise.csv"


@app.route("/api/csv-data")
def api_csv_data():
    """Return summary metrics for all historical dates at the same time slot."""
    return CsvController.get_csv_data()


@app.route("/api/csv-intraday")
def api_csv_intraday():
    """Return all time slots for a single date."""
    return CsvController.get_csv_intraday()


@app.route("/api/snapshot")
def api_snapshot():
    """Route now delegates to SnapshotController (Phase 5 migration)."""
    return SnapshotController.get_snapshot()


@app.route("/mvc/api/snapshot/historical", methods=["POST"])
def api_upsert_historical_snapshot():
    """Upsert historical snapshot from OptionAlpha market.histgex API."""
    return SnapshotController.upsert_historical_snapshot()


@app.route("/mvc/api/snapshot/live", methods=["POST"])
def api_upsert_live_snapshot():
    """Upsert live snapshot from OptionAlpha market.gex API."""
    return SnapshotController.upsert_live_snapshot()


@app.route("/mvc/api/snapshot/test", methods=["GET"])
def api_find_test_snapshots():
    """Find all test snapshots (source='test') for admin cleanup."""
    return SnapshotController.find_test_snapshots()


@app.route("/mvc/api/gex/strike-window", methods=["GET"])
def api_get_strike_window_entries():
    """Get all gex_strike_window entries for a specific date."""
    return SnapshotController.get_strike_window_entries()


@app.route("/mvc/api/gex/strike-window/csv", methods=["GET"])
def api_get_strike_window_csv():
    """Get gex_strike_window entries for a specific date in CSV format."""
    return SnapshotController.get_strike_window_csv()


@app.route("/mvc/api/gex/upsert", methods=["POST"])
def api_upsert_gex():
    """Upsert GEX strike window data from either historical or live format."""
    return SnapshotController.upsert_gex()


@app.route("/mvc/api/gex/compare", methods=["GET"])
def api_compare_gex():
    """Compare two gex_strike_window records."""
    return SnapshotController.compare_gex()


@app.route("/mvc/api/gex/delete-gex", methods=["DELETE"])
def api_delete_gex():
    """Delete gex_strike_window records by date/time.
    
    Query params:
    - date: YYYY-MM-DD (required)
    - time: HHMM (optional, if not provided deletes all times for the date)
    """
    date_str = request.args.get("date")
    time_str = request.args.get("time")
    
    if not date_str:
        return jsonify({"error": "date parameter is required"}), 400
    
    ndate = int(date_str.replace("-", ""))
    
    with _db() as con:
        if time_str:
            ntime = int(time_str.replace(":", ""))
            con.execute(
                "DELETE FROM gex_strike_window WHERE ndate=? AND ntime=?",
                (ndate, ntime)
            )
            return jsonify({
                "success": True,
                "message": f"Deleted gex_strike_window record for {date_str} at {time_str}"
            })
        else:
            cursor = con.execute(
                "DELETE FROM gex_strike_window WHERE ndate=?",
                (ndate,)
            )
            deleted_count = cursor.rowcount
            return jsonify({
                "success": True,
                "message": f"Deleted {deleted_count} gex_strike_window records for {date_str}"
            })


@app.route("/mvc/api/snapshot", methods=["DELETE"])
def api_delete_snapshot():
    """Delete a snapshot from the database."""
    return SnapshotController.delete_snapshot()


@app.route("/api/admin/purge-test-records")
def api_admin_purge_test_records():
    """Preview or delete garbage records from gex_strike_window:
      - Weekend dates (Saturday=7, Sunday=1 in SQLite strftime %w)
      - Pre-market captures before 0900 (not useful, not RTH)
      - After-hours captures after 1601

    Query params:
        dry_run: 1 (default) to preview, 0 to actually delete
    """
    from datetime import datetime as _dt
    dry_run = request.args.get("dry_run", "1") != "0"

    with _db() as con:
        # Find candidates: weekends OR extreme out-of-hours
        rows = con.execute("""
            SELECT ndate, ntime, symbol, source, price,
                   strftime('%w', substr(ndate,1,4)||'-'||substr(ndate,5,2)||'-'||substr(ndate,7,2)) as dow
            FROM gex_strike_window
            WHERE symbol='SPX' AND source='gex'
              AND (
                CAST(strftime('%w', substr(CAST(ndate AS TEXT),1,4)||'-'||substr(CAST(ndate AS TEXT),5,2)||'-'||substr(CAST(ndate AS TEXT),7,2)) AS INTEGER) IN (0, 6)
                OR ntime < 600
                OR ntime > 1601
              )
            ORDER BY ndate, ntime
        """).fetchall()

        candidates = []
        for r in rows:
            nd, nt, sym, src, price, dow = r
            nd_str = str(nd)
            date_str = f"{nd_str[:4]}-{nd_str[4:6]}-{nd_str[6:]}"
            day_name = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][int(dow)]
            reason = "weekend" if int(dow) in (0, 6) else ("pre-6am" if nt < 600 else "post-1601")
            candidates.append({"date": date_str, "time": nt, "dow": day_name, "reason": reason, "price": price})

        deleted = 0
        if not dry_run and candidates:
            cur = con.execute("""
                DELETE FROM gex_strike_window
                WHERE symbol='SPX' AND source='gex'
                  AND (
                    CAST(strftime('%w', substr(CAST(ndate AS TEXT),1,4)||'-'||substr(CAST(ndate AS TEXT),5,2)||'-'||substr(CAST(ndate AS TEXT),7,2)) AS INTEGER) IN (0, 6)
                    OR ntime < 600
                    OR ntime > 1601
                  )
            """)
            deleted = cur.rowcount

    return jsonify({
        "dry_run": dry_run,
        "candidates": candidates,
        "count": len(candidates),
        "deleted": deleted if not dry_run else 0,
        "message": f"{'Would delete' if dry_run else 'Deleted'} {len(candidates)} test/weekend records. "
                   + ("Pass ?dry_run=0 to actually delete." if dry_run else "Done."),
    })


@app.route("/api/admin/check-data-quality")
def api_admin_check_data_quality():
    """Identify records with zero OI/volume but non-zero GEX (data quality anomaly).

    GEX is typically calculated as OI × delta, so non-zero GEX with zero OI/volume
    indicates corrupt or incomplete data from the source API.

    Query params:
        dry_run: 1 (default) to preview, 0 to actually delete
    """
    import json
    dry_run = request.args.get("dry_run", "1") != "0"

    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, price, data FROM gex_strike_window WHERE symbol=? AND source=?",
            ('SPX', 'gex')
        ).fetchall()

        corrupt = []
        for nd, nt, price, data in rows:
            strikes = json.loads(data) if data else []
            if not strikes:
                continue

            # Check if all strikes have zero OI/vol but non-zero GEX
            has_zero_oi = all(s.get('coi', 0) == 0 and s.get('poi', 0) == 0 for s in strikes)
            has_zero_vol = all(s.get('cvol', 0) == 0 and s.get('pvol', 0) == 0 for s in strikes)
            has_gex = any(s.get('cg', 0) != 0 or s.get('pg', 0) != 0 for s in strikes)

            if has_zero_oi and has_zero_vol and has_gex:
                nd_str = str(nd)
                date_str = f"{nd_str[:4]}-{nd_str[4:6]}-{nd_str[6:]}"
                time_str = f"{nt//100:02d}:{nt%100:02d}"
                corrupt.append({
                    "ndate": nd,
                    "ntime": nt,
                    "date": date_str,
                    "time": time_str,
                    "price": price,
                    "strike_count": len(strikes),
                })

        deleted = 0
        if not dry_run and corrupt:
            # Delete all corrupt records
            for c in corrupt:
                con.execute(
                    "DELETE FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'",
                    (c['ndate'], c['ntime'])
                )
            deleted = len(corrupt)

    return jsonify({
        "dry_run": dry_run,
        "corrupt_records": corrupt,
        "count": len(corrupt),
        "deleted": deleted if not dry_run else 0,
        "message": f"{'Found' if dry_run else 'Deleted'} {len(corrupt)} corrupt records (zero OI/vol but non-zero GEX). "
                   + ("Pass ?dry_run=0 to delete them and re-sync from OptionAlpha." if dry_run else "Deleted. Re-sync these dates from OptionAlpha to get correct data."),
    })


@app.route("/api/snapshots")
def api_snapshots():
    """Route now delegates to SnapshotController (Phase 5 migration)."""
    return SnapshotController.get_snapshots()


@app.route("/api/gex/snapshots")
def api_gex_snapshots():
    """Route for new GEX architecture using gex_strike_window table."""
    from controllers.gex_controller import GexController
    return GexController.get_gex_snapshots()


@app.route("/api/gex/dates")
def api_gex_dates():
    """Get all available dates from gex_strike_window table.
    
    Returns sorted list of ISO date strings (YYYY-MM-DD) that have GEX data.
    """
    try:
        with _db() as con:
            cursor = con.execute('''
                SELECT DISTINCT ndate 
                FROM gex_strike_window 
                WHERE symbol = 'SPX'
                ORDER BY ndate DESC
            ''')
            rows = cursor.fetchall()
        
        # Convert YYYYMMDD int to ISO format (YYYY-MM-DD)
        dates = []
        for row in rows:
            s = str(row[0])  # YYYYMMDD int -> string
            dates.append(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
        
        return jsonify(dates)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gex/percentiles")
def api_gex_percentiles():
    """Get percentile ranks for all metrics for a given date/time snapshot.
    
    Uses pre-computed gex_percentile_history table for fast lookup.
    
    Query params:
    - date: ISO date (YYYY-MM-DD)
    - time: ntime (HHMM format, default 1000)
    
    Returns percentile ranks for net_gex, kcs, dominance, and volume/OI metrics.
    """
    from controllers.gex_controller import GexController
    return GexController.get_gex_percentiles()


@app.route("/api/gex/percentile")
def api_gex_percentile():
    """Calculate percentile for a single metric on-the-fly using recent historical data."""
    from controllers.gex_controller import GexController
    return GexController.calculate_on_the_fly_percentile()


@app.route("/gex/percentile-debug")
def gex_percentile_debug():
    """HTML debug page showing percentile calculation breakdown."""
    from controllers.gex_controller import GexController
    date = request.args.get("date", "")
    time = request.args.get("time", "1000")
    metric = request.args.get("metric", "net_gex")
    days = request.args.get("days", "90")

    if not date:
        return "<h2>Missing ?date= parameter</h2>", 400

    # Temporarily inject debug=true into the request args
    from werkzeug.test import EnvironBuilder
    from werkzeug.wrappers import Request as WerkzeugRequest
    with app.test_request_context(
        f"/api/gex/percentile?date={date}&time={time}&metric={metric}&days={days}&debug=true"
    ):
        from flask import request as inner_request
        result = GexController.calculate_on_the_fly_percentile()

    import json as _json
    data = _json.loads(result.get_data(as_text=True))

    if "error" in data:
        return f"<h2>Error: {data['error']}</h2>", 500

    history = data.get("history", [])
    current_val = data["value"]
    pct = data["percentile"]
    lookup_time = data["lookup_time"]

    rows_html = ""
    for i, h in enumerate(history):
        highlight = ' style="background:#fffbe6;font-weight:bold;"' if h["value"] == current_val else ""
        rows_html += f'<tr{highlight}><td>{i+1}</td><td>{h["date"]}</td><td>{lookup_time}</td><td>{h["value"]:,.2f}</td></tr>'

    html = f"""<!DOCTYPE html><html><head><title>Percentile Debug</title>
    <style>
      body {{ font-family: monospace; padding: 20px; }}
      table {{ border-collapse: collapse; width: 600px; }}
      th {{ background: #343a40; color: #fff; padding: 6px 12px; text-align: left; }}
      td {{ border-bottom: 1px solid #dee2e6; padding: 5px 12px; }}
      .summary {{ background: #e9f5e9; border: 1px solid #aaa; padding: 12px; margin-bottom: 20px; width: 580px; }}
    </style></head><body>
    <h2>Percentile Debug: {metric} @ {date} {time}</h2>
    <div class="summary">
      <b>Current value:</b> {current_val:,.2f}<br>
      <b>Percentile:</b> {pct}th<br>
      <b>Lookup time slot:</b> {lookup_time}<br>
      <b>Sample size:</b> {data['sample_size']} (last {days} days)<br>
      <b>Rank:</b> {round(pct * data['sample_size'] / 100):.0f} of {data['sample_size']}
    </div>
    <table>
      <thead><tr><th>#</th><th>Date</th><th>Time</th><th>{metric}</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </body></html>"""
    return html


@app.route("/api/gex/recalc-percentiles")
def api_recalc_gex_percentiles():
    """Manually recalculate percentiles for a specific time slot.
    
    Query params:
    - ntime: time in HHMM format (required)
    
    Returns status of recalculation.
    """
    ntime = request.args.get("ntime")
    if not ntime:
        return jsonify({"error": "ntime parameter required"}), 400
    
    try:
        ntime = int(ntime)
        _recalc_gex_percentiles(ntime)
        return jsonify({
            "success": True,
            "message": f"Recalculated percentiles for time slot {ntime}"
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/gex/backfill-percentiles")
def api_backfill_gex_percentiles():
    """Recalculate percentiles for all historical time slots.
    
    This deletes old percentile records and re-computes them using the
    current 11-metric set across all snapshots in gex_strike_window.
    """
    from datetime import date
    
    try:
        with _db() as con:
            # Get all distinct ntime values from historical snapshots (excluding today)
            today = date.today()
            today_ndate = int(today.strftime("%Y%m%d"))
            rows = con.execute(
                "SELECT DISTINCT ntime FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND ndate != ? ORDER BY ntime",
                (today_ndate,)
            ).fetchall()
            
            ntimes = [r[0] for r in rows]
        
        processed = 0
        errors = []
        for ntime in ntimes:
            try:
                _recalc_gex_percentiles(ntime)
                processed += 1
            except Exception as slot_err:
                errors.append({"ntime": ntime, "error": str(slot_err)})
        
        return jsonify({
            "success": len(errors) == 0,
            "processed_slots": processed,
            "total_slots": len(ntimes),
            "errors": errors
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/gex/snapshot")
def api_gex_snapshot():
    """Get a single GEX snapshot from gex_strike_window with calculated summary metrics.
    
    Query params:
    - date: ISO date (YYYY-MM-DD)
    - time: ntime (HHMM format)
    
    Returns summary metrics calculated from the 40-strike window data.
    """
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 1000))
    
    if not date_iso:
        return jsonify({"error": "date required"}), 400
    
    ndate = int(date_iso.replace("-", ""))
    
    def calculate_sentiment(strikes):
        """% of strikes with positive net GEX."""
        if not strikes:
            return 0
        positive = sum(1 for s in strikes if (s.get("cg", 0) + s.get("pg", 0)) > 0)
        return (positive / len(strikes)) * 100
    
    def calculate_gex_ratio(strikes):
        """Use corrected GEX ratio calculation."""
        from controllers.gex_calculations import calculate_gex_ratio as centralized_ratio
        return centralized_ratio(strikes)
    
    def calculate_net_gex(strikes):
        """call_gex + put_gex."""
        return sum(s.get("cg", 0) + s.get("pg", 0) for s in strikes)
    
    def calculate_kcs(strikes, uprice):
        """Weighted formula (0.5*gex_share + 0.3*oi_share + 0.2*vol_share) * proximity * 100."""
        if not strikes or uprice == 0:
            return 0
        
        # Calculate total values
        total_cg = sum(abs(s.get("cg", 0)) for s in strikes)
        total_pg = sum(abs(s.get("pg", 0)) for s in strikes)
        total_gex = total_cg + total_pg
        total_coi = sum(s.get("coi", 0) for s in strikes)
        total_poi = sum(s.get("poi", 0) for s in strikes)
        total_oi = total_coi + total_poi
        total_cvol = sum(s.get("cvol", 0) for s in strikes)
        total_pvol = sum(s.get("pvol", 0) for s in strikes)
        total_vol = total_cvol + total_pvol
        
        if total_gex == 0 and total_oi == 0 and total_vol == 0:
            return 0
        
        # Calculate weighted concentration for each strike
        max_kcs = 0
        for s in strikes:
            strike = s.get("strike", 0)
            if strike == 0:
                continue
            
            # GEX share
            gex_abs = abs(s.get("cg", 0)) + abs(s.get("pg", 0))
            gex_share = gex_abs / total_gex if total_gex > 0 else 0
            
            # OI share
            oi_sum = s.get("coi", 0) + s.get("poi", 0)
            oi_share = oi_sum / total_oi if total_oi > 0 else 0
            
            # Vol share
            vol_sum = s.get("cvol", 0) + s.get("pvol", 0)
            vol_share = vol_sum / total_vol if total_vol > 0 else 0
            
            # Proximity (closer to uprice = higher weight)
            proximity = 1 - (abs(strike - uprice) / uprice)
            proximity = max(0, proximity)
            
            # Weighted KCS
            kcs = (0.5 * gex_share + 0.3 * oi_share + 0.2 * vol_share) * proximity * 100
            max_kcs = max(max_kcs, kcs)
        
        return max_kcs
    
    def calculate_dominance(strikes, uprice):
        """key_abs / total_abs * 100."""
        if not strikes:
            return 0
        
        total_abs = sum(abs(s.get("cg", 0)) + abs(s.get("pg", 0)) for s in strikes)
        if total_abs == 0:
            return 0
        
        # Find key strike (max absolute GEX)
        max_abs = 0
        for s in strikes:
            abs_gex = abs(s.get("cg", 0)) + abs(s.get("pg", 0))
            if abs_gex > max_abs:
                max_abs = abs_gex
        
        return (max_abs / total_abs) * 100
    
    def calculate_key_strike_stats(strikes, uprice):
        """Proximity-weighted max abs using same formula as controller."""
        import math
        if not strikes:
            return {
                "key_strike": None,
                "key_call_gex": 0,
                "key_put_gex": 0,
                "key_call_oi": 0,
                "key_put_oi": 0,
                "key_call_vol": 0,
                "key_put_vol": 0,
                "key2_strike": None,
                "key2_abs": 0,
                "key2_call_vol": 0,
                "key2_put_vol": 0,
            }
        
        # Calculate weighted score for each strike using controller formula
        scored = []
        for s in strikes:
            strike = s.get("strike", 0)
            if strike == 0:
                continue
            
            abs_gex = abs(s.get("cg", 0)) + abs(s.get("pg", 0))
            proximity = math.exp(-abs(strike - uprice) / 25.0)
            score = abs_gex * proximity
            scored.append((strike, score, s))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if not scored:
            return {
                "key_strike": None,
                "key_call_gex": 0,
                "key_put_gex": 0,
                "key_call_oi": 0,
                "key_put_oi": 0,
                "key_call_vol": 0,
                "key_put_vol": 0,
                "key2_strike": None,
                "key2_abs": 0,
                "key2_call_vol": 0,
                "key2_put_vol": 0,
            }
        
        # Key strike
        key_strike, _, key_s = scored[0]
        
        # Secondary key strike (excluding key)
        key2_strike = None
        key2_abs = 0
        key2_call_vol = 0
        key2_put_vol = 0
        if len(scored) > 1:
            key2_strike, _, key2_s = scored[1]
            key2_abs = abs(key2_s.get("cg", 0)) + abs(key2_s.get("pg", 0))
            key2_call_vol = key2_s.get("cvol", 0)
            key2_put_vol = key2_s.get("pvol", 0)
        
        return {
            "key_strike": key_strike,
            "key_call_gex": key_s.get("cg", 0),
            "key_put_gex": key_s.get("pg", 0),
            "key_call_oi": key_s.get("coi", 0),
            "key_put_oi": key_s.get("poi", 0),
            "key_call_vol": key_s.get("cvol", 0),
            "key_put_vol": key_s.get("pvol", 0),
            "key2_strike": key2_strike,
            "key2_abs": key2_abs,
            "key2_call_vol": key2_call_vol,
            "key2_put_vol": key2_put_vol,
        }
    
    def calculate_total_gex(strikes):
        """Sum of cg/pg across all strikes."""
        total_cg = sum(s.get("cg", 0) for s in strikes)
        total_pg = sum(s.get("pg", 0) for s in strikes)
        return total_cg, total_pg
    
    def calculate_total_oi_and_vol(strikes):
        """Sum of coi/poi/cvol/pvol across all strikes."""
        total_coi = sum(s.get("coi", 0) for s in strikes)
        total_poi = sum(s.get("poi", 0) for s in strikes)
        total_cvol = sum(s.get("cvol", 0) for s in strikes)
        total_pvol = sum(s.get("pvol", 0) for s in strikes)
        return total_coi, total_poi, total_cvol, total_pvol
    
    def calculate_flip(strikes, uprice):
        """Price where net GEX crosses zero."""
        if not strikes or len(strikes) < 2:
            return None
        
        # Sort by strike
        sorted_strikes = sorted(strikes, key=lambda s: s.get("strike", 0))
        
        # Find where net GEX crosses zero
        for i in range(len(sorted_strikes) - 1):
            curr = sorted_strikes[i]
            next_s = sorted_strikes[i + 1]
            curr_net = curr.get("cg", 0) + curr.get("pg", 0)
            next_net = next_s.get("cg", 0) + next_s.get("pg", 0)
            
            if (curr_net < 0 and next_net > 0) or (curr_net > 0 and next_net < 0):
                # Linear interpolation
                curr_strike = curr.get("strike", 0)
                next_strike = next_s.get("strike", 0)
                ratio = abs(curr_net) / (abs(curr_net) + abs(next_net))
                return curr_strike + ratio * (next_strike - curr_strike)
        
        return None
    
    try:
        with _db() as con:
            row = con.execute(
                "SELECT ndate, ntime, symbol, source, price, data FROM gex_strike_window WHERE ndate=? AND ntime=? AND symbol=?",
                (ndate, ntime, "SPX")
            ).fetchone()
        
        if not row:
            return jsonify({"error": "No snapshot found"}), 404
        
        strikes = json.loads(row[5])
        uprice = row[4]
        
        # Calculate all summary metrics
        sentiment = calculate_sentiment(strikes)
        gex_ratio = calculate_gex_ratio(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, uprice)
        dominance = calculate_dominance(strikes, uprice)
        total_cg, total_pg = calculate_total_gex(strikes)
        total_coi, total_poi, total_cvol, total_pvol = calculate_total_oi_and_vol(strikes)
        key_stats = calculate_key_strike_stats(strikes, uprice)
        flip = calculate_flip(strikes, uprice)
        
        # Build arrays for charts
        strikes_sorted = sorted(strikes, key=lambda s: s.get("strike", 0))
        strike_values = [s.get("strike", 0) for s in strikes_sorted]
        call_gex = [s.get("cg", 0) for s in strikes_sorted]
        put_gex = [s.get("pg", 0) for s in strikes_sorted]
        call_oi = [s.get("coi", 0) for s in strikes_sorted]
        put_oi = [s.get("poi", 0) for s in strikes_sorted]
        call_vol = [s.get("cvol", 0) for s in strikes_sorted]
        put_vol = [s.get("pvol", 0) for s in strikes_sorted]
        
        return jsonify({
            "summary": {
                "uprice": uprice,
                "sentiment_pct": sentiment,
                "gex_ratio": gex_ratio,
                "net_gex": net_gex,
                "kcs": kcs,
                "key_dominance_pct": dominance,
                "call_gex": total_cg,
                "put_gex": total_pg,
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
                "total_call_oi": total_coi,
                "total_put_oi": total_poi,
                "total_call_vol": total_cvol,
                "total_put_vol": total_pvol,
                "flip": flip,
            },
            "strikes": strike_values,
            "call_gex": call_gex,
            "put_gex": put_gex,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_vol": call_vol,
            "put_vol": put_vol,
        })
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/gex/verify-percentiles")
def api_verify_percentiles():
    """Verify that all historical dates in gex_percentile_history have data for all metrics."""
    from datetime import date, datetime
    
    METRICS = ["net_gex", "kcs", "sentiment", "gex_ratio", "dominance",
               "total_call_gex", "total_put_gex",
               "total_call_oi", "total_put_oi",
               "total_call_vol", "total_put_vol"]
    
    try:
        with _db() as con:
            # Get all distinct (ndate, ntime) pairs from gex_strike_window (excluding today)
            today = date.today()
            today_ndate = int(today.strftime("%Y%m%d"))
            
            rows = con.execute(
                "SELECT DISTINCT ndate, ntime FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND ndate != ? ORDER BY ndate, ntime",
                (today_ndate,)
            ).fetchall()
            
            results = []
            for ndate, ntime in rows:
                date_str = f"{str(ndate)[:4]}-{str(ndate)[4:6]}-{str(ndate)[6:8]}"
                
                # Get existing metrics for this date/time
                existing_rows = con.execute(
                    "SELECT metric_name FROM percentile_history WHERE ndate=? AND ntime=?",
                    (ndate, ntime)
                ).fetchall()
                existing_metrics = {r[0] for r in existing_rows}
                
                # Check which metrics are missing
                missing = [m for m in METRICS if m not in existing_metrics]
                
                results.append({
                    "date": date_str,
                    "time": ntime,
                    "missing": missing,
                    "complete": len(missing) == 0
                })
        
        return jsonify({
            "total_snapshots": len(results),
            "complete_snapshots": sum(1 for r in results if r["complete"]),
            "incomplete_snapshots": sum(1 for r in results if not r["complete"]),
            "results": results
        })
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/gex/verify-strike-window")
def api_verify_strike_window():
    """Verify that all historical dates in gex_strike_window have mandatory RTH time slots."""
    from datetime import date, datetime
    
    MANDATORY_TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555]
    
    try:
        with _db() as con:
            # Get all distinct dates (excluding today)
            today = date.today()
            today_ndate = int(today.strftime("%Y%m%d"))
            
            rows = con.execute(
                "SELECT DISTINCT ndate FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND ndate != ? ORDER BY ndate",
                (today_ndate,)
            ).fetchall()
            
            results = []
            for row in rows:
                ndate = row[0]
                date_str = f"{str(ndate)[:4]}-{str(ndate)[4:6]}-{str(ndate)[6:8]}"
                
                # Get existing time slots for this date
                existing_rows = con.execute(
                    "SELECT DISTINCT ntime FROM gex_strike_window WHERE ndate=? AND symbol='SPX' AND source='gex'",
                    (ndate,)
                ).fetchall()
                existing_times = {r[0] for r in existing_rows}
                
                # Check which mandatory times are missing
                missing = [t for t in MANDATORY_TIMES if t not in existing_times]
                
                results.append({
                    "date": date_str,
                    "ndate": ndate,
                    "missing": missing,
                    "complete": len(missing) == 0
                })
        
        return jsonify({
            "total_dates": len(results),
            "complete_dates": sum(1 for r in results if r["complete"]),
            "incomplete_dates": sum(1 for r in results if not r["complete"]),
            "results": results
        })
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/gex/distribution/snapshots")
def api_gex_distribution_snapshots():
    """Get snapshots from gex_strike_window for distribution table with pagination."""
    from controllers.gex_controller import GexController
    return GexController.get_distribution_snapshots()


@app.route("/api/gex/distribution/all-values")
def api_gex_distribution_all_values():
    """Return all historical values for a metric from gex_strike_window."""
    from controllers.gex_controller import GexController
    return GexController.get_distribution_all_values()


@app.route("/api/gex/capture-session")
def api_gex_capture_session():
    """Launch Playwright session capture (--session-only mode).

    Opens a visible Chromium window at the OptionAlpha login page.
    You have 20 seconds to log in; the session cookies are then saved
    to session.json and the browser closes automatically.
    Runs as a background subprocess so the request returns immediately
    with a status message.
    """
    import subprocess, sys
    capture_script = Path(__file__).parent / "optionalpha_capture.py"
    if not capture_script.exists():
        return jsonify({"error": "optionalpha_capture.py not found"}), 500
    try:
        subprocess.Popen(
            [sys.executable, str(capture_script), "--session-only"],
            cwd=str(Path(__file__).parent),
        )
        return jsonify({
            "status": "launched",
            "message": "Chromium is opening — log in within 60 seconds. Session will save automatically.",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gex/session-status")
def api_gex_session_status():
    """Check whether a valid session.json exists and how old it is."""
    session_file = Path(__file__).parent / "session.json"
    if not session_file.exists():
        return jsonify({"exists": False, "message": "No session — click Capture Session to log in."})
    import time as _time
    age_seconds = _time.time() - session_file.stat().st_mtime
    age_hours = round(age_seconds / 3600, 1)
    fresh = age_hours < 12
    return jsonify({
        "exists": True,
        "age_hours": age_hours,
        "fresh": fresh,
        "message": f"Session saved {age_hours}h ago — {'✓ fresh' if fresh else '⚠ may be stale, re-capture recommended'}",
    })


@app.route("/api/gex/fetch-live")
def api_gex_fetch_live():
    """Fetch live GEX data from OptionAlpha market.gex and store in gex_strike_window.
    
    This is the new GEX tab's live mode - fetches from market.gex (not histgex),
    extracts 40-strike window, and stores with source='gex'.
    """
    from time import time as _time
    from datetime import datetime, timezone
    from optionalpha_client import call_optionalpha_api, SESSION_FILE
    
    def extract_strike_window(strikes, uprice):
        """Extract 40 strikes around the SPX price."""
        if not strikes:
            return []
        sorted_strikes = sorted(strikes, key=lambda r: r["strike"])
        uprice_idx = min(range(len(sorted_strikes)),
                         key=lambda i: abs(sorted_strikes[i]["strike"] - uprice))
        exact_match = sorted_strikes[uprice_idx]["strike"] == uprice
        if exact_match:
            start_idx = max(0, uprice_idx - 20)
            end_idx = min(len(sorted_strikes), uprice_idx + 20)
            window = sorted_strikes[start_idx:end_idx]
            if len(window) > 40:
                if uprice_idx - start_idx >= 20 and end_idx - uprice_idx >= 19:
                    window = sorted_strikes[uprice_idx - 20:uprice_idx + 20]
                elif uprice_idx - start_idx >= 20:
                    window = window[:40]
                else:
                    window = window[-40:]
        else:
            start_idx = max(0, uprice_idx - 20)
            end_idx = min(len(sorted_strikes), uprice_idx + 21)
            window = sorted_strikes[start_idx:end_idx]
            if len(window) > 40:
                window = window[:40]
        return window
    
    try:
        # Build RPC payload for market.gex with current xid
        xid = current_xid("SPX")
        print(f"[DEBUG] Using xid: {xid}")
        tid = int(_time() * 1000)
        payload = [
            {
                "t": "rpc",
                "tid": f"{tid}-10071",
                "api": "market.gex",
                "args": ["SPX", xid],
            }
        ]
        print(f"[DEBUG] Payload: {payload}")
        
        # Call OptionAlpha API
        raw = call_optionalpha_api(payload, SESSION_FILE)
        print(f"[DEBUG] OptionAlpha raw response: {raw}")
        
        # Extract market.gex response
        data = None
        for item in raw:
            print(f"[DEBUG] Item: {item}")
            if item.get("api") == "market.gex":
                data = item.get("data")
                print(f"[DEBUG] Found market.gex data: {data}")
                break
        
        if not data:
            return jsonify({"error": "No market.gex data in response", "raw_response": raw}), 500
        
        # Get current date/time
        et_now = get_et_now()
        ndate = int(et_now.strftime("%Y%m%d"))
        ntime = int(et_now.strftime("%H%M"))
        uprice = data.get("last", 0)
        rows = data.get("data") or []
        
        if not rows:
            return jsonify({"error": "No strike data in market.gex response"}), 500
        
        # Extract 40-strike window
        window_strikes = extract_strike_window(rows, uprice)
        if not window_strikes:
            return jsonify({"error": "Could not extract 40-strike window"}), 500
        
        # Store in gex_strike_window with source='gex'
        from controllers.gex_calculations import calculate_flip_level
        flip = calculate_flip_level(window_strikes)
        with _db() as con:
            con.execute(
                "INSERT OR REPLACE INTO gex_strike_window "
                "(ndate, ntime, symbol, source, price, data, flip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ndate, ntime, 'SPX', 'gex', uprice, json.dumps(window_strikes), flip)
            )
        
        # Calculate HMM label for RTH captures (ntime >= 935)
        hmm_state = None
        hmm_label = None
        if ntime >= 935:
            from controllers.gex_calculations import (
                calculate_sentiment,
                calculate_net_gex,
                calculate_kcs,
                calculate_key_strike_stats,
                calculate_total_oi_and_vol,
            )
            
            sentiment = calculate_sentiment(window_strikes)
            net_gex = calculate_net_gex(window_strikes)
            kcs = calculate_kcs(window_strikes, uprice)
            key_stats = calculate_key_strike_stats(window_strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(window_strikes)
            
            snap_features = [{
                "uprice": uprice,
                "net_gex": net_gex,
                "kcs": kcs,
                "sentiment_pct": sentiment,
                "key_strike": key_stats["key_strike"],
                "total_put_vol": total_oi_vol["total_put_vol"],
            }]
            
            hmm_results = predict_hmm_sequence(snap_features)
            if hmm_results:
                hmm_state = hmm_results[0].get("state")
                hmm_label = hmm_results[0].get("label")
                
                # Update the stored record with HMM labels
                with _db() as con:
                    con.execute(
                        "UPDATE gex_strike_window SET hmm_state=?, hmm_label=? "
                        "WHERE ndate=? AND ntime=? AND symbol='SPX' AND source='gex'",
                        (hmm_state, hmm_label, ndate, ntime),
                    )
        
        # Recalculate percentiles for this time slot
        _recalc_gex_percentiles(ntime)

        # Run ML prediction for RTH snapshots and persist it
        ml_signal = None
        if ntime >= 935:
            try:
                ml_signal = _predict_snapshot(window_strikes, uprice, ntime)
                _save_prediction(ndate, ntime, ml_signal)
            except Exception as _ml_err:
                ml_signal = {"error": str(_ml_err)}

        return jsonify({
            "success": True,
            "message": f"Fetched live GEX data for {et_now.strftime('%Y-%m-%d %H:%M')}",
            "ndate": ndate,
            "ntime": ntime,
            "uprice": uprice,
            "strike_count": len(window_strikes),
            "hmm_label": hmm_label,
            "ml_signal": ml_signal,
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/api/snapshots/summary")
def api_snapshots_summary():
    """Return compact summary rows for every time-slot on a date from gex_strike_window."""
    from controllers.gex_calculations import (
        calculate_sentiment, calculate_gex_ratio, calculate_net_gex,
        calculate_kcs, calculate_dominance, calculate_key_strike_stats,
        calculate_total_oi_and_vol, calculate_total_gex, calculate_flip_level,
    )
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"date": date_iso, "rows": []})
    try:
        ndate = int(date_iso.replace("-", ""))
        with _db() as con:
            db_rows = con.execute(
                "SELECT ntime, price, data, hmm_label FROM gex_strike_window "
                "WHERE ndate=? AND symbol='SPX' AND source='gex' ORDER BY ntime",
                (ndate,),
            ).fetchall()
        rows = []
        for ntime, price, data_json, hmm_label in db_rows:
            strikes = json.loads(data_json) if data_json else []
            if not strikes:
                continue
            sentiment  = calculate_sentiment(strikes)
            gex_ratio  = calculate_gex_ratio(strikes)
            net_gex    = calculate_net_gex(strikes)
            kcs        = calculate_kcs(strikes, price)
            dominance  = calculate_dominance(strikes, price)
            key_stats  = calculate_key_strike_stats(strikes, price)
            oi_vol     = calculate_total_oi_and_vol(strikes)
            gex_totals = calculate_total_gex(strikes)
            flip       = calculate_flip_level(strikes)
            is_premarket = ntime < 935 or ntime > 1555
            rows.append({
                "ntime":        ntime,
                "spx_last":     price,
                "sentiment":    sentiment,
                "gex_ratio":    gex_ratio,
                "net_gex":      net_gex,
                "kcs":          kcs,
                "dominance":    dominance,
                "total_call_gex": gex_totals["total_call_gex"],
                "total_put_gex":  gex_totals["total_put_gex"],
                "total_call_oi":  oi_vol["total_call_oi"],
                "total_put_oi":   oi_vol["total_put_oi"],
                "total_call_vol": oi_vol["total_call_vol"],
                "total_put_vol":  oi_vol["total_put_vol"],
                "key_strike":     key_stats["key_strike"],
                "key_call_gex":   key_stats["key_call_gex"],
                "key_put_gex":    key_stats["key_put_gex"],
                "key_call_oi":    key_stats["key_call_oi"],
                "key_put_oi":     key_stats["key_put_oi"],
                "key_call_vol":   key_stats["key_call_vol"],
                "key_put_vol":    key_stats["key_put_vol"],
                "key2_strike":    key_stats["key2_strike"],
                "key2_abs":       key_stats["key2_abs"],
                "key2_call_vol":  key_stats["key2_call_vol"],
                "key2_put_vol":   key_stats["key2_put_vol"],
                "flip":           flip,
                "hmm_label":      hmm_label,
                "is_premarket":   is_premarket,
            })
        return jsonify({"date": date_iso, "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e), "date": date_iso, "rows": []}), 500


@app.route("/api/analysis")
def api_analysis():
    """Generate EOD analysis for a given date."""
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "Date parameter required"}), 400

    analysis = generate_eod_analysis(date_iso)
    return jsonify(analysis)


@app.route("/api/percentiles")
def api_percentiles():
    """Return percentile ranks for all 7 metrics for a given date/time snapshot.

    Uses pre-computed percentile_history table for fast lookup.
    net_gex:   bearish_pct = 100 - pct_rank  (higher = more bearish than historical)
    call_gex, put_gex, call_oi, put_oi, call_vol, put_vol:
               size_pct = pct_rank  (higher = larger than more historical readings)
    """
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 1000))
    if not date_iso:
        return jsonify({"error": "date required"}), 400

    ndate = int(date_iso.replace("-", ""))

    # Load snapshot stats
    stats = _snapshot_computed_stats(date_iso, ntime)
    is_live = False
    if not stats:
        # Try loading from SQLite (covers both historical and live snapshots)
        live_data = load_gex_snapshot(date_iso, ntime)
        if live_data:
            uprice = live_data.get("uprice", 0)
            all_rows = sorted(
                [r for r in (live_data.get("data") or []) if r.get("strike") is not None],
                key=lambda r: r["strike"]
            )
            below = [r for r in all_rows if r["strike"] < uprice]
            above = [r for r in all_rows if r["strike"] >= uprice]
            rows = below[-20:] + above[:20]
            if not rows:
                return jsonify({"error": "No valid rows in snapshot"}), 404
            call_gex = [r.get("cg", 0) or 0 for r in rows]
            put_gex  = [r.get("pg", 0) or 0 for r in rows]
            net_gex  = [r.get("net", 0) or 0 for r in rows]
            ks = _compute_key_strike_stats(rows, uprice)
            stats = {
                "net_gex":  sum(net_gex),
                "call_gex": sum(call_gex),
                "put_gex":  abs(sum(put_gex)),
                "call_oi":  sum(r.get("coi", 0) or 0 for r in rows),
                "put_oi":   sum(r.get("poi", 0) or 0 for r in rows),
                "call_vol": sum(r.get("cvol", 0) or 0 for r in rows),
                "put_vol":  sum(r.get("pvol", 0) or 0 for r in rows),
                "kcs":      ks.get("kcs", 0.0),
                "dominance": ks.get("key_dominance_pct", 0.0),
            }
            is_live = True
        else:
            return jsonify({"error": "No snapshot found"}), 404

    # For live snapshots, find the time slot with the most historical data for comparison
    if is_live:
        # Find the time slot with the largest sample size
        best_ntime = ntime
        best_size = 0
        with _db() as con:
            for t in TIMES:
                size = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=?",
                    (t,)
                ).fetchone()[0]
                if size > best_size:
                    best_size = size
                    best_ntime = t
        cache_ntime = best_ntime
    else:
        cache_ntime = ntime

    # Get sample size for this time slot
    with _db() as con:
        n = con.execute(
            "SELECT COUNT(DISTINCT ndate) FROM percentile_history WHERE ntime=?",
            (cache_ntime,)
        ).fetchone()[0]

    # Get pre-computed percentiles for this snapshot
    with _db() as con:
        # For historical, use exact ndate/ntime. For live, use best_ntime and current stats
        if is_live:
            # Get percentile by comparing current value to time-slot distribution
            net_pct_raw = con.execute(
                "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name='net_gex' AND value<=?",
                (cache_ntime, stats["net_gex"])
            ).fetchone()[0]
            total = con.execute(
                "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name='net_gex'",
                (cache_ntime,)
            ).fetchone()[0]
            net_pct_raw = round(net_pct_raw / total * 100, 1) if total > 0 else 50
        else:
            # Use pre-computed percentile from table
            row = con.execute(
                "SELECT percentile FROM percentile_history WHERE ndate=? AND ntime=? AND metric_name='net_gex'",
                (ndate, ntime)
            ).fetchone()
            net_pct_raw = row[0] if row else 50

        bearish_pct = 100 - net_pct_raw

        def size_entry(metric_name):
            if is_live:
                pct_raw = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=? AND value<=?",
                    (cache_ntime, metric_name, stats[metric_name])
                ).fetchone()[0]
                total = con.execute(
                    "SELECT COUNT(*) FROM percentile_history WHERE ntime=? AND metric_name=?",
                    (cache_ntime, metric_name)
                ).fetchone()[0]
                pct = round(pct_raw / total * 100, 1) if total > 0 else 50
            else:
                row = con.execute(
                    "SELECT percentile FROM percentile_history WHERE ndate=? AND ntime=? AND metric_name=?",
                    (ndate, ntime, metric_name)
                ).fetchone()
                pct = row[0] if row else 50
            return {"value": stats[metric_name], "pct": pct}

    return jsonify({
        "sample_size": n,
        "ntime": ntime,
        "net_gex": {
            "value": stats["net_gex"],
            "pct_raw": net_pct_raw,       # % of readings below (more negative)
            "bearish_pct": bearish_pct,    # more bearish than X% of readings
        },
        "call_gex": size_entry("call_gex"),
        "put_gex":  size_entry("put_gex"),
        "call_oi":  size_entry("call_oi"),
        "put_oi":   size_entry("put_oi"),
        "call_vol": size_entry("call_vol"),
        "put_vol":  size_entry("put_vol"),
        "kcs":      size_entry("kcs"),
        "dominance": size_entry("dominance"),
    })


@app.route("/api/narrative")
def api_narrative():
    """Get or generate a trading narrative for a given date."""
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "date required"}), 400

    ndate = int(date_iso.replace("-", ""))

    # Check if narrative exists
    with _db() as con:
        row = con.execute(
            "SELECT narrative, is_llm_enhanced FROM daily_narratives WHERE ndate=?",
            (ndate,)
        ).fetchone()

    if row:
        return jsonify({
            "date": date_iso,
            "narrative": row[0],
            "is_llm_enhanced": bool(row[1]),
            "generated": False
        })

    # Generate new narrative
    narrative = _generate_daily_narrative(date_iso)
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    with _db() as con:
        con.execute(
            "INSERT INTO daily_narratives (ndate, narrative, generated_at, updated_at, is_llm_enhanced) VALUES (?, ?, ?, ?, 0)",
            (ndate, narrative, now, now)
        )

    return jsonify({
        "date": date_iso,
        "narrative": narrative,
        "is_llm_enhanced": False,
        "generated": True
    })


@app.route("/api/narrative", methods=["POST"])
def api_narrative_update():
    """Update a narrative (manual edit)."""
    data = request.get_json()
    date_iso = data.get("date")
    narrative = data.get("narrative")

    if not date_iso or narrative is None:
        return jsonify({"error": "date and narrative required"}), 400

    ndate = int(date_iso.replace("-", ""))
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO daily_narratives (ndate, narrative, generated_at, updated_at, is_llm_enhanced) VALUES (?, ?, ?, ?, 0)",
            (ndate, narrative, now, now)
        )

    return jsonify({"success": True})


@app.route("/api/migrate-live", methods=["POST"])
def api_migrate_live():
    """Manually trigger promotion of prior-day live captures to historical snapshot."""
    result = _promote_live_to_historical()
    return jsonify(result)


@app.route("/api/narrative/regenerate", methods=["POST"])
def api_narrative_regenerate():
    """Regenerate a narrative (clears existing and generates new)."""
    data = request.get_json()
    date_iso = data.get("date")
    if not date_iso:
        return jsonify({"error": "date required"}), 400

    ndate = int(date_iso.replace("-", ""))

    # Delete existing
    with _db() as con:
        con.execute("DELETE FROM daily_narratives WHERE ndate=?", (ndate,))

    # Generate new
    narrative = _generate_daily_narrative(date_iso)
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    with _db() as con:
        con.execute(
            "INSERT INTO daily_narratives (ndate, narrative, generated_at, updated_at, is_llm_enhanced) VALUES (?, ?, ?, ?, 0)",
            (ndate, narrative, now, now)
        )

    return jsonify({
        "date": date_iso,
        "narrative": narrative,
        "is_llm_enhanced": False
    })


@app.route("/api/trade-signals")
def api_trade_signals():
    """Return all persisted trade signals for a date."""
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "date required"}), 400
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        rows = con.execute(
            "SELECT ntime, regime, setup_type, action, short_strike, wing_strike, "
            "short_strike2, wing_strike2, structure, rationale, invalidation, caution, "
            "prev_outcome, next_spx, next_ntime, outcome, outcome_points, generated_ts, is_llm_enhanced "
            "FROM trade_signals WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
            (ndate,)
        ).fetchall()
    cols = ["ntime", "regime", "setup_type", "action", "short_strike", "wing_strike",
            "short_strike2", "wing_strike2", "structure", "rationale", "invalidation",
            "caution", "prev_outcome", "next_spx", "next_ntime", "outcome", "outcome_points",
            "generated_ts", "is_llm_enhanced"]
    return jsonify({"date": date_iso, "signals": [dict(zip(cols, r)) for r in rows]})


@app.route("/api/trade-signals/generate", methods=["POST"])
def api_trade_signals_generate():
    """Generate and persist trade signals for all snapshots on a date."""
    body = request.get_json(force=True) or {}
    date_iso = body.get("date")
    if not date_iso:
        et_now = get_et_now()
        date_iso = et_now.strftime("%Y-%m-%d")
    ndate = int(date_iso.replace("-", ""))

    # Load all snapshots for the date in time order
    # For today's date, use snapshot; for historical dates, use snapshot
    from datetime import datetime, timedelta, timezone
    et_now = get_et_now()
    today_ndate = int(et_now.strftime("%Y%m%d"))
    use_live = (ndate == today_ndate)

    with _db() as con:
        # Query gex_strike_window table for new architecture
        snap_rows = con.execute(
            """SELECT ndate, ntime, symbol, source, price, data, hmm_label
               FROM gex_strike_window
               WHERE ndate=? AND symbol='SPX' AND source='gex'
               ORDER BY ntime""",
            (ndate,)
        ).fetchall()

    if not snap_rows:
        return jsonify({"error": "No snapshots found for date"}), 404

    # Import calculation functions
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_gex_ratio,
        calculate_net_gex,
        calculate_kcs,
        calculate_dominance,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
        calculate_total_gex,
        calculate_flip_level,
    )

    # Calculate metrics for each snapshot from raw gex_strike_window data
    snaps = []
    for row in snap_rows:
        ndate, ntime, symbol, source, price, data, hmm_label = row
        strikes = json.loads(data) if data else []
        
        if not strikes:
            continue
        
        # Calculate all metrics
        sentiment = calculate_sentiment(strikes)
        gex_ratio = calculate_gex_ratio(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, price)
        dominance = calculate_dominance(strikes, price)
        key_stats = calculate_key_strike_stats(strikes, price)
        total_oi_vol = calculate_total_oi_and_vol(strikes)
        total_gex_vals = calculate_total_gex(strikes)
        flip = calculate_flip_level(strikes)
        
        # Pre-market: times outside 09:35-15:55 range
        is_premarket = ntime < 935 or ntime > 1555
        
        snaps.append({
            "ntime": ntime,
            "uprice": price,
            "net_gex": net_gex,
            "sentiment_pct": sentiment,
            "gex_ratio": gex_ratio,
            "kcs": kcs,
            "key_dominance_pct": dominance,
            "total_call_gex": total_gex_vals["total_call_gex"],
            "total_put_gex": total_gex_vals["total_put_gex"],
            "key_strike": key_stats["key_strike"],
            "key_call_gex": key_stats["key_call_gex"],
            "key_put_gex": key_stats["key_put_gex"],
            "total_call_oi": total_oi_vol["total_call_oi"],
            "total_put_oi": total_oi_vol["total_put_oi"],
            "key_call_oi": key_stats["key_call_oi"],
            "key_put_oi": key_stats["key_put_oi"],
            "total_call_vol": total_oi_vol["total_call_vol"],
            "total_put_vol": total_oi_vol["total_put_vol"],
            "key_call_vol": key_stats["key_call_vol"],
            "key_put_vol": key_stats["key_put_vol"],
            "key2_strike": key_stats.get("key2_strike"),
            "key2_abs": key_stats.get("key2_abs"),
            "flip": flip,
            "hmm_label": hmm_label,
            "is_premarket": is_premarket,
        })

    # Load existing signals for prev_outcome chain
    with _db() as con:
        existing = con.execute(
            "SELECT ntime, action, short_strike, structure FROM trade_signals "
            "WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
            (ndate,)
        ).fetchall()
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
            wing_strike = signal.get("wing_strike")
            WING = 10

            if action == "STAY_OUT":
                move = abs(next_spx - curr_spx) if next_spx and curr_spx else 0
                if move < 5:
                    outcome = "MISSED"
                    outcome_points = 0  # Could have profited from iron condor
                elif move > 15:
                    outcome = "CORRECT"
                    outcome_points = move  # Avoided adverse move
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

    return jsonify({"date": date_iso, "generated": generated})


@app.route("/api/history")
def api_history():
    """Return historical values for all metrics at a given time slot (for scatter charts).

    Returns dates + call/put GEX, OI, Vol arrays for all available histgex dates.
    Scales GEX to billions, OI and Vol to thousands.
    """
    ntime = int(request.args.get("time", 1000))
    h = get_history_cache(ntime)
    B, K = 1e9, 1e3
    return jsonify({
        "dates":     h["dates"],
        "call_gex":  [round(v / B, 3) for v in h["call_gex"]],
        "put_gex":   [round(v / B, 3) for v in h["put_gex"]],
        "call_oi":   [round(v / K, 1) for v in h["call_oi"]],
        "put_oi":    [round(v / K, 1) for v in h["put_oi"]],
        "call_vol":  [round(v / K, 1) for v in h["call_vol"]],
        "put_vol":   [round(v / K, 1) for v in h["put_vol"]],
        "kcs":       [round(v, 2) for v in h["kcs"]],
        "dominance": [round(v, 2) for v in h["dominance"]],
    })


@app.route("/api/history/distribution")
def api_history_distribution():
    """Return distribution data for a single metric at a given time slot.

    Used for histogram view showing where a selected snapshot sits relative to history.
    Returns the full historical values array, the selected snapshot's value, and its percentile rank.

    Query params:
        time: time slot (e.g., 930, 1000)
        metric: metric name (e.g., net_gex, sentiment)
        current_date (optional): override the "current" snapshot date (YYYY-MM-DD)
        current_time (optional): override the "current" snapshot time (e.g., 930)
    """
    ntime = int(request.args.get("time", 1000))
    metric = request.args.get("metric", "net_gex")
    current_date = request.args.get("current_date")
    current_time = request.args.get("current_time")

    # Map metric names to the history cache keys and DB column names
    metric_map = {
        "net_gex": {"cache": "net_gex", "db": "net_gex"},
        "total_call_gex": {"cache": "call_gex", "db": "total_call_gex"},
        "total_put_gex": {"cache": "put_gex", "db": "total_put_gex"},
        "total_call_oi": {"cache": "call_oi", "db": "total_call_oi"},
        "total_put_oi": {"cache": "put_oi", "db": "total_put_oi"},
        "total_call_vol": {"cache": "call_vol", "db": "total_call_vol"},
        "total_put_vol": {"cache": "put_vol", "db": "total_put_vol"},
        "kcs": {"cache": "kcs", "db": "kcs"},
        "dominance": {"cache": "dominance", "db": "dominance"},
        "sentiment": {"cache": "sentiment", "db": "sentiment"},
        "gex_ratio": {"cache": "gex_ratio", "db": "gex_ratio"},
    }

    mapping = metric_map.get(metric, {"cache": metric, "db": metric})
    cache_key = mapping["cache"]
    db_col = mapping["db"]

    h = get_history_cache(ntime)

    if cache_key not in h:
        return jsonify({"error": f"Metric {metric} not available"}), 400

    values = h[cache_key]
    if not values:
        return jsonify({"error": "No data for this time slot"}), 404

    # Determine the "current" snapshot value
    current_value = None
    current_label = None

    if current_date and current_time:
        # Use the specified date/time
        ndate = int(current_date.replace("-", ""))
        ntime_current = int(current_time)
        with _db() as con:
            row = con.execute(
                f"SELECT {db_col} FROM snapshot "
                "WHERE ndate=? AND ntime=? AND symbol='SPX'",
                (ndate, ntime_current)
            ).fetchone()
        if row:
            current_value = row[0]
            current_label = f"{current_date} @ {ntime_current}"
    else:
        # Find the latest snapshot matching the requested time slot
        with _db() as con:
            # Check snapshot first for the requested ntime
            live_row = con.execute(
                f"SELECT capture_ts, {db_col} FROM snapshot "
                f"WHERE ntime=? AND {db_col} IS NOT NULL ORDER BY capture_ts DESC LIMIT 1",
                (ntime,)
            ).fetchone()
            if live_row:
                current_value = live_row[1]
                current_label = f"Live @ {live_row[0]}"
            else:
                # Fall back to latest historical snapshot matching the requested ntime
                hist_row = con.execute(
                    f"SELECT ndate, ntime, {db_col} FROM snapshot "
                    f"WHERE symbol='SPX' AND ntime=? AND {db_col} IS NOT NULL "
                    "ORDER BY ndate DESC LIMIT 1",
                    (ntime,)
                ).fetchone()
                if hist_row:
                    current_value = hist_row[2]
                    ndate_str = str(hist_row[0])
                    current_label = f"{ndate_str[:4]}-{ndate_str[4:6]}-{ndate_str[6:8]} @ {hist_row[1]}"

    # Calculate percentile rank
    sorted_vals = sorted(values)
    if current_value is not None:
        rank = sum(1 for v in sorted_vals if v <= current_value)
        percentile = round(rank / len(sorted_vals) * 100, 1)
    else:
        percentile = None

    # Scale for display (GEX to billions, OI to thousands)
    # gex_ratio, sentiment, dominance, kcs, vol are ratios/percentages/contracts - don't scale
    if metric in ["gex_ratio", "sentiment", "dominance", "kcs"] or "vol" in metric:
        scale = 1
    elif "gex" in metric:
        scale = 1e9
    elif "oi" in metric:
        scale = 1e3
    else:
        scale = 1
    scaled_values = [round(v / scale, 3) for v in values]
    scaled_current = round(current_value / scale, 3) if current_value is not None else None

    return jsonify({
        "metric": metric,
        "ntime": ntime,
        "values": scaled_values,
        "current_value": scaled_current,
        "percentile": percentile,
        "n_samples": len(values),
        "current_label": current_label,
    })


@app.route("/api/snapshots/all")
def api_snapshots_all():
    """Route now delegates to SnapshotController (Phase 5 migration)."""
    return SnapshotController.get_snapshots_all()


@app.route("/api/history/all-values")
def api_history_all_values():
    """Return all historical values for a metric across all time slots.

    Query params:
        metric: metric name (e.g., net_gex, sentiment)
        regime: time regime filter (e.g., "0930_1000", "pre")
    """
    metric = request.args.get("metric", "net_gex")
    regime_id = request.args.get("regime", "0930_1000")

    # Get time range for selected regime
    regime = next((r for r in TIME_REGIMES if r["id"] == regime_id), TIME_REGIMES[1])  # default to 0930_1000
    time_start = regime["start"]
    time_end = regime["end"]

    # Map metric names to the history cache keys
    metric_map = {
        "net_gex": "net_gex",
        "total_call_gex": "call_gex",
        "total_put_gex": "put_gex",
        "total_call_oi": "call_oi",
        "total_put_oi": "put_oi",
        "total_call_vol": "call_vol",
        "total_put_vol": "put_vol",
        "kcs": "kcs",
        "dominance": "dominance",
        "sentiment": "sentiment",
        "gex_ratio": "gex_ratio",
    }

    cache_key = metric_map.get(metric, metric)

    # Get all time slots from the history cache, filtered by regime
    with _db() as con:
        rows = con.execute(
            """SELECT DISTINCT ntime FROM snapshot
               WHERE symbol='SPX' AND ntime>=? AND ntime<=?
               ORDER BY ntime""",
            (time_start, time_end)
        ).fetchall()

    all_values = []
    for row in rows:
        ntime = row[0]
        h = get_history_cache(ntime)
        if cache_key in h and h[cache_key]:
            all_values.extend(h[cache_key])

    # Scale for display
    if metric in ["gex_ratio", "sentiment", "dominance", "kcs"]:
        scale = 1
    elif "gex" in metric:
        scale = 1e9
    elif "oi" in metric or "vol" in metric:
        scale = 1e3
    else:
        scale = 1

    # Filter out None values before scaling
    valid_values = [v for v in all_values if v is not None]
    scaled_values = [round(v / scale, 3) for v in valid_values]

    return jsonify({
        "metric": metric,
        "values": scaled_values,
        "n_samples": len(scaled_values),
    })


@app.route("/api/archived-live")
def api_archived_live():
    """Return any live/daily-capture artifacts that exist for a historical date.

    Used in the Analysis tab "Archived Live" section to compare against the
    historical (histgex) EOD analysis.
    """
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "Date parameter required"}), 400

    date_str = date_iso.replace("-", "")
    result = {
        "date": date_iso,
        "daily_summary_row": None,
        "live_analysis": None,
        "analysis_files": [],
        "raw_captures": [],
    }

    # Daily summary row
    df = get_daily_summary()
    rows = df[df["date_iso"] == date_iso]
    if not rows.empty:
        row = rows.iloc[-1].to_dict()
        result["daily_summary_row"] = row
        result["live_analysis"] = generate_live_analysis(date_iso)

    # Analysis-concise markdown files for this date
    analysis_dir = BASE_DIR / "analysis"
    if analysis_dir.exists():
        for f in sorted(analysis_dir.glob(f"analysis-concise-{date_str}-*.md")):
            result["analysis_files"].append({
                "path": str(f),
                "name": f.name,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })

    # Raw JSON captures for this date (excluding summary/window files)
    results_dir = BASE_DIR / "results"
    if results_dir.exists():
        for f in sorted(results_dir.glob(f"{date_str}_*_SPX_*.json")):
            if f.name.endswith("_gex_summary.json") or f.name.endswith("_gex_window.json"):
                continue
            result["raw_captures"].append({
                "path": str(f),
                "name": f.name,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })

    return jsonify(result)


# ---------------------------------------------------------------------------
# Live GEX (current day) — captures market.gex and stores in livegex folder
# ---------------------------------------------------------------------------

LIVE_DIR = BASE_DIR / "results" / "livegex"
LIVE_DIR.mkdir(parents=True, exist_ok=True)


def get_et_now():
    """Return current Eastern Time datetime."""
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def current_xid(symbol: str = "SPX") -> str:
    """Build xid for current trading day, e.g. SPX_20260622."""
    et_now = get_et_now()
    return f"{symbol}_{et_now.strftime('%Y%m%d')}"


def run_script(name: str, args: list[str] = None, timeout: int = 180) -> dict:
    """Run a Python script in the project virtual environment."""
    python_exe = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        return {"ok": False, "error": f"Virtual env python not found: {python_exe}"}

    cmd = [str(python_exe), str(BASE_DIR / name)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Script {name} timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_daily_summary():
    """Reload the in-memory daily summary DataFrame after an external update."""
    global DAILY_SUMMARY_DF
    DAILY_SUMMARY_DF = load_daily_summary()


INTRADAY_TIMES = [935, 1000, 1030, 1100, 1130, 1200, 1230,
                  1300, 1330, 1400, 1430, 1500, 1530, 1555]


def _existing_times(ndate: int, symbol: str = "SPX") -> set:
    """Return the set of ntimes already in the DB for this date."""
    with _db() as con:
        rows = con.execute(
            "SELECT ntime FROM snapshot WHERE ndate=? AND symbol=?",
            (ndate, symbol),
        ).fetchall()
    return {r[0] for r in rows}


def _migrate_histgex_to_db(symbol: str = "SPX") -> dict:
    """Import histgex JSON files into snapshot table."""
    migrated = 0
    skipped = 0
    dates_done = []
    if not GEX_DIR.exists():
        return {"migrated": 0, "skipped": 0, "dates": []}
    for day_dir in sorted(GEX_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        ymd = day_dir.name
        if len(ymd) != 8 or not ymd.isdigit():
            continue
        ndate = int(ymd)
        for f in sorted(day_dir.glob(f"*_{symbol}_histgex.json")):
            try:
                parts = f.stem.split("_")  # YYYYMMDD_NNNN_SPX_histgex
                ntime = int(parts[1])
            except (IndexError, ValueError):
                continue
            # Check if already in snapshot
            with _db() as con:
                exists = con.execute(
                    "SELECT 1 FROM snapshot WHERE ndate=? AND ntime=? AND symbol=?",
                    (ndate, ntime, symbol),
                ).fetchone()
            if exists:
                skipped += 1
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                rows = data.get("data") or []
                if not rows:
                    skipped += 1
                    continue
                uprice = data.get("uprice", 0)
                is_pre = 1 if ntime < RTH_OPEN else 0
                snap = _compute_flat_summary(data)
                with _db() as con:
                    con.execute(
                        "INSERT OR IGNORE INTO snapshot "
                        "(ndate, ntime, symbol, uprice, is_premarket, source, raw_json, "
                        "sentiment, gex_ratio, net_gex, kcs, dominance, "
                        "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                        "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                        "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                        "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ndate, ntime, symbol, uprice, is_pre, 'histgex', json.dumps(data),
                         snap.get("sentiment_pct"), snap.get("gex_ratio"), snap.get("net_gex"), snap.get("kcs"), snap.get("key_dominance_pct"),
                         snap.get("total_call_gex"), snap.get("total_put_gex"), snap.get("key_strike"), snap.get("key_call_gex"), snap.get("key_put_gex"),
                         snap.get("total_call_oi"), snap.get("total_put_oi"), snap.get("key_call_oi"), snap.get("key_put_oi"),
                         snap.get("total_call_vol"), snap.get("total_put_vol"), snap.get("key_call_vol"), snap.get("key_put_vol"),
                         snap.get("key2_strike"), snap.get("key2_abs"), snap.get("key2_call_vol"), snap.get("key2_put_vol"), snap.get("flip")),
                    )
                migrated += 1
            except Exception:
                skipped += 1
        if migrated > 0 and ymd not in dates_done:
            dates_done.append(ymd)
    return {"migrated": migrated, "skipped": skipped, "dates": dates_done}


def _migrate_live_snapshots_to_history(symbol: str = "SPX") -> dict:
    """Promote prior-day live JSON files into snapshot.

    Scans results/livegex/ for any date folder that is NOT today, reads each
    *_livegex.json file and inserts it into snapshot (INSERT OR IGNORE so
    already-present rows are not overwritten).

    Returns counts: {"migrated": N, "skipped": N, "dates": [...]}
    """
    from datetime import date as _date
    today_ymd = _date.today().strftime("%Y%m%d")
    migrated = 0
    skipped  = 0
    dates_done = []

    if not LIVE_DIR.exists():
        return {"migrated": 0, "skipped": 0, "dates": []}

    for day_dir in sorted(LIVE_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        ymd = day_dir.name
        if len(ymd) != 8 or not ymd.isdigit():
            continue
        ndate = int(ymd)

        for f in sorted(day_dir.glob(f"*_{symbol}_livegex.json")):
            try:
                parts = f.stem.split("_")  # YYYYMMDD_NNNN_SPX_livegex
                ntime = int(parts[1])
            except (IndexError, ValueError):
                continue

            # Check if already in snapshot
            with _db() as con:
                exists = con.execute(
                    "SELECT 1 FROM snapshot WHERE ndate=? AND ntime=? AND symbol=?",
                    (ndate, ntime, symbol),
                ).fetchone()
            if exists:
                skipped += 1
                continue

            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                rows = data.get("data") or []
                if not rows:
                    skipped += 1
                    continue
                uprice = data.get("uprice", 0)
                is_pre = 1 if ntime < RTH_OPEN else 0
                snap = _compute_flat_summary(data)
                with _db() as con:
                    con.execute(
                        "INSERT OR IGNORE INTO snapshot "
                        "(ndate, ntime, symbol, uprice, is_premarket, source, raw_json, "
                        "sentiment, gex_ratio, net_gex, kcs, dominance, "
                        "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                        "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                        "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                        "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ndate, ntime, symbol, uprice, is_pre, 'gex', json.dumps(data),
                         snap.get("sentiment_pct"), snap.get("gex_ratio"), snap.get("net_gex"), snap.get("kcs"), snap.get("key_dominance_pct"),
                         snap.get("total_call_gex"), snap.get("total_put_gex"), snap.get("key_strike"), snap.get("key_call_gex"), snap.get("key_put_gex"),
                         snap.get("total_call_oi"), snap.get("total_put_oi"), snap.get("key_call_oi"), snap.get("key_put_oi"),
                         snap.get("total_call_vol"), snap.get("total_put_vol"), snap.get("key_call_vol"), snap.get("key_put_vol"),
                         snap.get("key2_strike"), snap.get("key2_abs"), snap.get("key2_call_vol"), snap.get("key2_put_vol"), snap.get("flip")),
                    )
                migrated += 1
            except Exception:
                skipped += 1

        if migrated > 0 and ymd not in dates_done:
            dates_done.append(ymd)

    return {"migrated": migrated, "skipped": skipped, "dates": dates_done}


def _recalc_gex_percentiles(ntime: int) -> None:
    """Recalculate percentiles for all snapshots at a specific time slot.
    
    This is called after inserting new data to keep percentiles synchronized.
    """
    import json
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_gex_ratio,
        calculate_net_gex,
        calculate_kcs,
        calculate_dominance,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
        calculate_total_gex,
    )
    
    METRICS = [
        "net_gex", "kcs", "sentiment", "gex_ratio", "dominance",
        "total_call_gex", "total_put_gex",
        "total_call_oi", "total_put_oi",
        "total_call_vol", "total_put_vol",
    ]
    
    with _db() as con:
        # Get all snapshots at this time slot
        rows = con.execute(
            "SELECT ndate, ntime, price, data FROM gex_strike_window WHERE ntime=? AND symbol='SPX' AND source='gex' ORDER BY ndate",
            (ntime,)
        ).fetchall()
        
        if not rows:
            return
        
        # Calculate metrics for all snapshots at this time slot
        metric_values = {metric: [] for metric in METRICS}
        snapshot_data = []
        
        for row in rows:
            ndate, ntime, uprice, data_json = row
            if not uprice or not data_json:
                continue
            
            try:
                strikes = json.loads(data_json)
            except:
                continue
            
            if not strikes:
                continue
            
            # Calculate all metrics
            sentiment = calculate_sentiment(strikes)
            gex_ratio = calculate_gex_ratio(strikes)
            net_gex = calculate_net_gex(strikes)
            kcs = calculate_kcs(strikes, uprice)
            dominance = calculate_dominance(strikes, uprice)
            key_stats = calculate_key_strike_stats(strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(strikes)
            total_gex_vals = calculate_total_gex(strikes)
            
            snapshot_data.append({
                "ndate": ndate,
                "ntime": ntime,
                "net_gex": net_gex,
                "kcs": kcs,
                "sentiment": sentiment,
                "gex_ratio": gex_ratio,
                "dominance": dominance,
                "total_call_gex": total_gex_vals["total_call_gex"],
                "total_put_gex": total_gex_vals["total_put_gex"],
                "total_call_oi": total_oi_vol["total_call_oi"],
                "total_put_oi": total_oi_vol["total_put_oi"],
                "total_call_vol": total_oi_vol["total_call_vol"],
                "total_put_vol": total_oi_vol["total_put_vol"],
            })
            
            for metric in METRICS:
                metric_values[metric].append(snapshot_data[-1][metric])
        
        # Delete existing percentile records for this time slot
        con.execute(
            "DELETE FROM percentile_history WHERE ntime=?",
            (ntime,)
        )
        
        # Calculate percentile ranks for each metric
        for metric in METRICS:
            values = metric_values[metric]
            if not values:
                continue
            
            sorted_vals = sorted(values)
            
            for snap in snapshot_data:
                value = snap[metric]
                rank = sum(1 for v in sorted_vals if v <= value)
                percentile = round(rank / len(sorted_vals) * 100, 1)
                
                con.execute(
                    "INSERT INTO percentile_history (ndate, ntime, metric_name, value, percentile) VALUES (?, ?, ?, ?, ?)",
                    (snap["ndate"], snap["ntime"], metric, value, percentile)
                )


def sync_historical_gex(symbol: str = "SPX", mode: str = "all", target_date: str = None, target_time: str = None, max_days: int = 30, year: int = None, month: int = None) -> dict:
    """Fetch GEX data from OptionAlpha and store only in gex_strike_window table.

    Modes:
    - "all": Fetch missing data for last max_days days
    - "date": Fetch all missing times for a specific date
    - "datetime": Fetch a single snapshot for specific date+time
    - "timeslot": Fetch a specific time slot for all dates (uses random sleep 2-4s)

    For timeslot mode:
    - If year/month provided: fetch for that month only (Mon-Fri only)
    - Otherwise: fetch for last max_days days

    This function intentionally does NOT touch the snapshot table or any old logic.
    """
    print(f"[SYNC] Starting sync_historical_gex: mode={mode}, symbol={symbol}, max_days={max_days}, target_date={target_date}, target_time={target_time}, year={year}, month={month}")
    import time as _time_mod
    import random
    from datetime import date, timedelta
    from gex_historical_intraday import fetch_histgex

    def extract_strike_window(strikes, uprice):
        """Extract 40 strikes around the SPX price."""
        if not strikes:
            return []
        sorted_strikes = sorted(strikes, key=lambda r: r["strike"])
        uprice_idx = min(range(len(sorted_strikes)),
                         key=lambda i: abs(sorted_strikes[i]["strike"] - uprice))
        exact_match = sorted_strikes[uprice_idx]["strike"] == uprice
        if exact_match:
            start_idx = max(0, uprice_idx - 20)
            end_idx = min(len(sorted_strikes), uprice_idx + 20)
            window = sorted_strikes[start_idx:end_idx]
            if len(window) > 40:
                if uprice_idx - start_idx >= 20 and end_idx - uprice_idx >= 19:
                    window = sorted_strikes[uprice_idx - 20:uprice_idx + 20]
                elif uprice_idx - start_idx >= 20:
                    window = window[:40]
                else:
                    window = window[-40:]
        else:
            start_idx = max(0, uprice_idx - 20)
            end_idx = min(len(sorted_strikes), uprice_idx + 21)
            window = sorted_strikes[start_idx:end_idx]
            if len(window) > 40:
                window = window[:40]
        return window

    def _existing_gex_times(ndate: int, symbol: str = "SPX") -> set:
        """Return ntimes already in gex_strike_window for this date."""
        with _db() as con:
            rows = con.execute(
                "SELECT ntime FROM gex_strike_window WHERE ndate=? AND symbol=?",
                (ndate, symbol),
            ).fetchall()
        times = {r[0] for r in rows}
        print(f"[SYNC] Existing times for {ndate}: {len(times)} found")
        return times

    def _fetch_and_store(ndate: int, ntime: int) -> bool:
        """Fetch one snapshot from OptionAlpha and store in gex_strike_window."""
        print(f"[SYNC] Fetching {ndate}@{ntime:04d} for {symbol}...")
        data = fetch_histgex(symbol=symbol, ndate=ndate, ntime=ntime)
        print(f"[SYNC] fetch_histgex returned data keys={list(data.keys()) if isinstance(data, dict) else 'N/A'} for {ndate}@{ntime:04d}")
        if not data:
            raise ValueError(f"market.histgex returned no data for {ntime}")
        rows = data.get("data") or []
        if not rows:
            raise ValueError(f"no strike rows for {ntime}")
        uprice = data.get("uprice", 0)
        window_strikes = extract_strike_window(rows, uprice)
        if not window_strikes:
            raise ValueError(f"could not extract 40-strike window for {ntime}")
        from controllers.gex_calculations import calculate_flip_level
        flip = calculate_flip_level(window_strikes)
        with _db() as con:
            con.execute(
                "INSERT OR REPLACE INTO gex_strike_window "
                "(ndate, ntime, symbol, source, price, data, flip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ndate, ntime, symbol, 'gex', uprice, json.dumps(window_strikes), flip)
            )
        print(f"[SYNC] Stored {ndate}@{ntime:04d} price={uprice}, flip={flip}")
        
        # Calculate HMM label for RTH snapshots (ntime >= 935)
        hmm_state = None
        hmm_label = None
        if ntime >= 935:
            from controllers.gex_calculations import (
                calculate_sentiment,
                calculate_net_gex,
                calculate_kcs,
                calculate_key_strike_stats,
                calculate_total_oi_and_vol,
            )
            
            sentiment = calculate_sentiment(window_strikes)
            net_gex = calculate_net_gex(window_strikes)
            kcs = calculate_kcs(window_strikes, uprice)
            key_stats = calculate_key_strike_stats(window_strikes, uprice)
            total_oi_vol = calculate_total_oi_and_vol(window_strikes)
            
            snap_features = [{
                "net_gex": net_gex,
                "kcs": kcs,
                "sentiment_pct": sentiment,
                "key_strike": key_stats["key_strike"],
                "total_put_vol": total_oi_vol["total_put_vol"],
            }]
            
            hmm_results = predict_hmm_sequence(snap_features)
            if hmm_results:
                hmm_state = hmm_results[0].get("state")
                hmm_label = hmm_results[0].get("label")
                
                # Update the stored record with HMM labels
                with _db() as con:
                    con.execute(
                        "UPDATE gex_strike_window SET hmm_state=?, hmm_label=? "
                        "WHERE ndate=? AND ntime=? AND symbol=? AND source='gex'",
                        (hmm_state, hmm_label, ndate, ntime, symbol),
                    )
            print(f"[SYNC] HMM for {ndate}@{ntime:04d}: state={hmm_state}, label={hmm_label}")
        else:
            print(f"[SYNC] Skipping HMM for {ndate}@{ntime:04d} (pre-market)")
        
        # Recalculate percentiles for this time slot
        print(f"[SYNC] Recalculating percentiles for time slot {ntime:04d}")
        _recalc_gex_percentiles(ntime)
        print(f"[SYNC] Completed {ndate}@{ntime:04d}")
        return True

    fetched = []
    skipped = []
    failed = []

    target_ndate = None
    if target_date:
        target_ndate = int(target_date.replace("-", ""))
    target_ntime = None
    if target_time:
        # Convert HH:MM format to HHMM integer
        if ":" in target_time:
            target_ntime = int(target_time.replace(":", ""))
        else:
            target_ntime = int(target_time)

    if mode == "datetime" and target_ndate and target_ntime:
        iso = target_date
        ndate = target_ndate
        ntime = target_ntime
        existing = _existing_gex_times(ndate, symbol)
        print(f"[SYNC] datetime mode: {iso}@{ntime:04d}, exists={ntime in existing}")
        if ntime in existing:
            skipped.append(f"{iso}@{ntime}")
        else:
            try:
                _fetch_and_store(ndate, ntime)
                fetched.append(f"{iso}@{ntime}")
            except Exception as e:
                import traceback
                print(f"[SYNC ERROR] datetime mode failed {iso}@{ntime:04d}: {e}")
                traceback.print_exc()
                failed.append({"date": f"{iso}@{ntime}", "error": str(e)[:80]})

    elif mode == "date" and target_ndate:
        iso = target_date
        ndate = target_ndate
        existing = _existing_gex_times(ndate, symbol)
        missing = [t for t in INTRADAY_TIMES if t not in existing]
        print(f"[SYNC] date mode: {iso}, missing={len(missing)} slots: {missing}")
        if not missing:
            skipped.append(iso)
        else:
            day_fetched = 0
            for ntime in missing:
                try:
                    _fetch_and_store(ndate, ntime)
                    day_fetched += 1
                    _time_mod.sleep(0.5)
                except Exception as e:
                    import traceback
                    print(f"[SYNC ERROR] date mode failed {iso}@{ntime:04d}: {e}")
                    traceback.print_exc()
                    failed.append({"date": f"{iso}@{ntime}", "error": str(e)[:80]})
            if day_fetched > 0:
                fetched.append(f"{iso}({day_fetched}/{len(missing)} slots)")
            print(f"[SYNC] date mode result for {iso}: fetched {day_fetched}/{len(missing)}")

    elif mode == "timeslot" and target_ntime:
        # Fetch specific time slot for all dates
        if year and month:
            # Process specific month (Mon-Fri only)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            dates_to_process = []
            for day in range(1, last_day + 1):
                d = date(year, month, day)
                # Only process Mon-Fri (weekday 0-4)
                if d.weekday() < 5:
                    dates_to_process.append(d)
        else:
            # Process last max_days days
            yesterday = date.today() - timedelta(days=1)
            dates_to_process = [yesterday - timedelta(days=i) for i in range(max_days)]
        
        print(f"[SYNC] timeslot mode: target_ntime={target_ntime:04d}, processing {len(dates_to_process)} dates")
        for d in dates_to_process:
            iso = d.isoformat()
            ndate = int(d.strftime("%Y%m%d"))
            existing = _existing_gex_times(ndate, symbol)
            print(f"[SYNC] timeslot mode: checking {iso}@{target_ntime:04d}, exists={target_ntime in existing}")
            if target_ntime in existing:
                skipped.append(f"{iso}@{target_ntime}")
                continue
            try:
                _fetch_and_store(ndate, target_ntime)
                fetched.append(f"{iso}@{target_ntime}")
                # Random sleep 2-4 seconds to avoid detection
                sleep_time = random.uniform(2, 4)
                print(f"[SYNC] timeslot mode: sleeping {sleep_time:.2f}s")
                _time_mod.sleep(sleep_time)
            except Exception as e:
                import traceback
                print(f"[SYNC ERROR] timeslot mode failed {iso}@{target_ntime:04d}: {e}")
                traceback.print_exc()
                failed.append({"date": f"{iso}@{target_ntime}", "error": str(e)[:80]})

    else:
        # "all" mode
        print(f"[SYNC] all mode: processing last {max_days} days ending yesterday")
        yesterday = date.today() - timedelta(days=1)
        for i in range(max_days):
            d = yesterday - timedelta(days=i)
            iso = d.isoformat()
            ndate = int(d.strftime("%Y%m%d"))
            existing = _existing_gex_times(ndate, symbol)
            missing = [t for t in INTRADAY_TIMES if t not in existing]
            print(f"[SYNC] all mode: {iso} missing={len(missing)} slots: {missing}")
            if not missing:
                skipped.append(iso)
                continue
            day_fetched = 0
            for ntime in missing:
                try:
                    _fetch_and_store(ndate, ntime)
                    day_fetched += 1
                    _time_mod.sleep(0.5)
                except Exception as e:
                    import traceback
                    print(f"[SYNC ERROR] all mode failed {iso}@{ntime:04d}: {e}")
                    traceback.print_exc()
                    failed.append({"date": f"{iso}@{ntime}", "error": str(e)[:80]})
            if day_fetched > 0:
                fetched.append(f"{iso}({day_fetched}/{len(missing)} slots)")
            print(f"[SYNC] all mode result for {iso}: fetched {day_fetched}/{len(missing)}")

    print(f"[SYNC] Complete: fetched={len(fetched)}, skipped={len(skipped)}, failed={len(failed)}")
    return {"fetched": fetched, "skipped": skipped, "failed": failed}


@app.route("/api/sync-historical")
def api_sync_historical():
    """Sync historical GEX data to gex_strike_window table only."""
    symbol = request.args.get("symbol", "SPX")
    mode = request.args.get("mode", "all")
    max_days = int(request.args.get("max_days", 30))
    target_date = request.args.get("date")
    target_time = request.args.get("time")
    year = request.args.get("year")
    month = request.args.get("month")
    
    print(f"[SYNC API] Request: symbol={symbol}, mode={mode}, max_days={max_days}, date={target_date}, time={target_time}, year={year}, month={month}")
    
    if year:
        year = int(year)
    if month:
        month = int(month)
    
    result = sync_historical_gex(symbol=symbol, mode=mode, target_date=target_date, target_time=target_time, max_days=max_days, year=year, month=month)
    print(f"[SYNC API] Result: fetched={len(result.get('fetched', []))}, skipped={len(result.get('skipped', []))}, failed={len(result.get('failed', []))}")
    return jsonify(result)


@app.route("/api/spx-prices")
def api_spx_prices():
    """Return SPX price history from gex_strike_window table.

    Query params:
    - mode: 'eod' (default) or 'single'
    - date: ISO date (YYYY-MM-DD) for single mode
    """
    mode = request.args.get("mode", "eod")
    target_date = request.args.get("date")

    prices = []

    if mode == "single" and target_date:
        # Single date mode: all times for that date
        ndate = int(target_date.replace("-", ""))
        with _db() as con:
            rows = con.execute(
                """SELECT ntime, price FROM gex_strike_window
                   WHERE ndate=? AND symbol='SPX' AND source='gex'
                   ORDER BY ntime""",
                (ndate,)
            ).fetchall()
        for ntime, uprice in rows:
            if uprice:
                prices.append({
                    "date": target_date,
                    "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                    "uprice": uprice
                })
    else:
        # EOD mode: latest time per day
        with _db() as con:
            rows = con.execute(
                """SELECT ndate, MAX(ntime) as ntime, price FROM gex_strike_window
                   WHERE symbol='SPX' AND source='gex'
                   GROUP BY ndate ORDER BY ndate"""
            ).fetchall()
        for ndate, ntime, uprice in rows:
            if uprice:
                s = str(ndate)
                date_iso = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                prices.append({
                    "date": date_iso,
                    "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                    "uprice": uprice
                })

    return jsonify({"prices": prices})


@app.route("/api/live/capture")
def api_live_capture():
    """Run optionalpha_capture.py --session-only to refresh the Playwright session cookies."""
    result = run_script("optionalpha_capture.py", args=["--session-only"], timeout=180)
    if not result["ok"]:
        return jsonify({
            "error": result.get("error") or result.get("stderr", "Capture failed"),
            "stdout": result.get("stdout", ""),
        }), 500
    return jsonify({
        "ok": True,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    })


@app.route("/api/live/fetch")
def api_live_fetch():
    """Fetch live GEX and run the full daily pipeline.

    1. Runs optionalpha_daily.py --symbol SPX
    2. Runs optionalpha_daily-summary.py
    3. Generates a concise analysis markdown file
    4. Returns the latest live snapshot for display
    """
    try:
        return _api_live_fetch_inner()
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


def _api_live_fetch_inner():
    # Step 1: fetch live data via the daily script
    daily_result = run_script("optionalpha_daily.py", ["--symbol", "SPX"], timeout=180)
    if not daily_result["ok"]:
        return jsonify({
            "error": daily_result.get("error") or daily_result.get("stderr", "daily.py failed"),
            "stdout": daily_result.get("stdout", ""),
        }), 500

    # Step 2: rebuild the concise summary CSV
    summary_result = run_script("optionalpha_daily-summary.py", timeout=120)
    if not summary_result["ok"]:
        return jsonify({
            "error": summary_result.get("error") or summary_result.get("stderr", "daily-summary.py failed"),
            "stdout": summary_result.get("stdout", ""),
        }), 500

    # Reload the daily summary so the live analysis uses fresh data
    refresh_daily_summary()

    # Step 3: generate the concise analysis markdown file
    et_now = get_et_now()
    date_iso = et_now.strftime("%Y-%m-%d")
    report_path = generate_concise_report(date_iso)

    # Step 4: return the latest live snapshot for the UI
    data = fetch_live_gex()
    if data is None:
        return jsonify({
            "error": "Pipeline completed but no live snapshot could be loaded for display",
            "stdout": daily_result.get("stdout", "") + "\n" + summary_result.get("stdout", ""),
            "report_path": str(report_path) if report_path else None,
        }), 502

    path = save_live_snapshot(data)
    divergence = detect_volume_divergence(data)
    snap = summarise_snapshot(data)

    # HMM regime prediction — save to snapshot with regime label
    hmm = {}
    if data["ntime"] >= 935:
        with _db() as _hcon:
            prior_rows = _hcon.execute(
                "SELECT uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
                "FROM snapshot WHERE ndate=? AND ntime>=935 AND source='gex' ORDER BY ntime",
                (data["ndate"],)
            ).fetchall()
        prior_snaps = [
            {"uprice": r[0], "net_gex": r[1], "kcs": r[2],
             "sentiment_pct": r[3], "key_strike": r[4], "total_put_vol": r[5]}
            for r in prior_rows
        ]
        all_snaps = prior_snaps + [snap]
        seq_results = predict_hmm_sequence(all_snaps)
        hmm = seq_results[-1] if seq_results else {}

    # Persist to snapshot for regime tracking
    from datetime import datetime, timezone
    _ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _is_premarket = 1 if data["ntime"] < RTH_OPEN else 0
    with _db() as _con:
        _con.execute("""
            INSERT OR REPLACE INTO snapshot (
                ndate, ntime, symbol, uprice, raw_json, capture_ts, source,
                sentiment, gex_ratio, net_gex, kcs, dominance,
                total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex,
                total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                is_premarket, hmm_state, hmm_label
            ) VALUES (?, ?, 'SPX', ?, ?, ?, 'gex',
                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["ndate"], data["ntime"],
            snap.get("uprice"), json.dumps(data), _ts,
            snap.get("sentiment_pct"), snap.get("gex_ratio"),
            snap.get("net_gex"), snap.get("kcs"), snap.get("key_dominance_pct"),
            snap.get("call_gex"), snap.get("put_gex"),
            snap.get("key_strike"), snap.get("key_call_gex"), snap.get("key_put_gex"),
            snap.get("total_call_oi"), snap.get("total_put_oi"),
            snap.get("key_call_oi"), snap.get("key_put_oi"),
            snap.get("total_call_vol"), snap.get("total_put_vol"),
            snap.get("key_call_vol"), snap.get("key_put_vol"),
            snap.get("key2_strike"), snap.get("key2_abs"),
            snap.get("key2_call_vol"), snap.get("key2_put_vol"),
            snap.get("flip"),
            _is_premarket,
            hmm.get("state"), hmm.get("label"),
        ))

    uprice = snap.get("uprice", 0)
    all_rows = sorted(
        [r for r in (data.get("data") or []) if r.get("strike") is not None],
        key=lambda r: r["strike"]
    )
    below = [r for r in all_rows if r["strike"] < uprice]
    above = [r for r in all_rows if r["strike"] >= uprice]
    rows = below[-20:] + above[:20]

    strikes = [r["strike"] for r in rows]
    call_gex = [r.get("cg", 0) or 0 for r in rows]
    put_gex = [r.get("pg", 0) or 0 for r in rows]
    net_gex = [r.get("net", 0) or 0 for r in rows]
    call_oi = [r.get("coi", 0) or 0 for r in rows]
    put_oi = [-(r.get("poi", 0) or 0) for r in rows]
    call_vol = [r.get("cvol", 0) or 0 for r in rows]
    put_vol = [-(r.get("pvol", 0) or 0) for r in rows]

    cumulative_gex = []
    running = 0.0
    for v in net_gex:
        running += v
        cumulative_gex.append(round(running, 2))

    total_call_oi = sum(r.get("coi", 0) or 0 for r in rows)
    total_put_oi = sum(r.get("poi", 0) or 0 for r in rows)
    total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
    total_put_vol = sum(r.get("pvol", 0) or 0 for r in rows)

    pos_bars = sum(1 for n in net_gex if n > 0)
    sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50

    # Use corrected GEX ratio calculation
    from controllers.gex_calculations import calculate_gex_ratio
    gex_ratio = calculate_gex_ratio(rows)
    net_g = sum(net_gex)

    snap["sentiment_pct"] = sentiment_pct
    snap["gex_ratio"] = gex_ratio
    snap["net_gex"] = net_g
    snap["total_call_oi"] = int(total_call_oi)
    snap["total_put_oi"] = int(total_put_oi)
    snap["total_call_vol"] = int(total_call_vol)
    snap["total_put_vol"] = int(total_put_vol)

    # HMM regime prediction — use full day's sequence for context (proper Viterbi)
    # Only for RTH (ntime >= 935) — pre-market data is outside training distribution
    hmm = {}
    if data["ntime"] >= 935:
        with _db() as _hcon:
            prior_rows = _hcon.execute(
                "SELECT uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
                "FROM snapshot WHERE ndate=? AND ntime>=935 ORDER BY ntime",
                (data["ndate"],)
            ).fetchall()
        prior_snaps = [
            {"uprice": r[0], "net_gex": r[1], "kcs": r[2],
             "sentiment_pct": r[3], "key_strike": r[4], "total_put_vol": r[5]}
            for r in prior_rows
        ]
        all_snaps = prior_snaps + [snap]
        seq_results = predict_hmm_sequence(all_snaps)
        hmm = seq_results[-1] if seq_results else {}

    # Build teaching points for the live snapshot
    live_thesis = build_thesis(
        uprice=snap.get("uprice", 0),
        net_gex=snap.get("net_gex", 0),
        wall=snap.get("wall"),
        flip=snap.get("flip"),
        key_call_oi=0,
        key_put_oi=0,
        key_call_vol=0,
        key_put_vol=0,
        date_iso=date_iso,
        detect_divergence=True,
        divergence_source="snapshot",
    )
    live_points = teaching_points_for_snapshot(snap)
    if live_thesis.get("divergence"):
        live_points.insert(0, {
            "title": "Volume Divergence Warning",
            "text": live_thesis["divergence"],
            "type": "danger",
        })

    # Persist this capture to SQLite for intraday trend tracking
    from datetime import datetime, timezone
    _ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _is_premarket = 1 if data["ntime"] < RTH_OPEN else 0
    with _db() as _con:
        _con.execute("""
            INSERT OR REPLACE INTO snapshot (
                capture_ts, ndate, ntime,
                spx_last, sentiment, gex_ratio, net_gex, kcs, dominance,
                total_call_gex, total_put_gex,
                key_strike, key_call_gex, key_put_gex,
                total_call_oi, total_put_oi, key_call_oi, key_put_oi,
                total_call_vol, total_put_vol, key_call_vol, key_put_vol,
                key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip,
                is_premarket, hmm_state, hmm_label, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            _ts, data["ndate"], data["ntime"],
            snap.get("uprice"), snap.get("sentiment_pct"), snap.get("gex_ratio"),
            snap.get("net_gex"), snap.get("kcs"), snap.get("key_dominance_pct"),
            snap.get("call_gex"), snap.get("put_gex"),
            snap.get("key_strike"), snap.get("key_call_gex"), snap.get("key_put_gex"),
            snap.get("total_call_oi"), snap.get("total_put_oi"),
            snap.get("key_call_oi"), snap.get("key_put_oi"),
            snap.get("total_call_vol"), snap.get("total_put_vol"),
            snap.get("key_call_vol"), snap.get("key_put_vol"),
            snap.get("key2_strike"), snap.get("key2_abs"),
            snap.get("key2_call_vol"), snap.get("key2_put_vol"),
            snap.get("flip"),
            _is_premarket,
            hmm.get("state"), hmm.get("label"),
            json.dumps(data),
        ))

    return jsonify({
        "summary": snap,
        "strikes": strikes,
        "call_gex": call_gex,
        "put_gex": put_gex,
        "net_gex": net_gex,
        "cumulative_gex": cumulative_gex,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_vol": call_vol,
        "put_vol": put_vol,
        "ntime": data["ntime"],
        "ndate": data["ndate"],
        "saved_to": str(path),
        "divergence": divergence,
        "report_path": str(report_path) if report_path else None,
        "points": live_points,
        "hmm": hmm,
    })


@app.route("/api/live/analysis")
def api_live_analysis():
    """Return live/current-day analysis and persist it to live_analysis table."""
    import json as _json
    et_now = get_et_now()
    date_iso = et_now.strftime("%Y-%m-%d")
    analysis = generate_live_analysis(date_iso)
    if "error" in analysis:
        return jsonify(analysis), 404

    # Persist: upsert keyed on (ndate, ntime) from the latest capture
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        latest_cap = con.execute(
            "SELECT ntime, uprice, net_gex, key_strike, flip FROM snapshot "
            "WHERE ndate=? ORDER BY id DESC LIMIT 1", (ndate,)
        ).fetchone()
    ntime = latest_cap[0] if latest_cap else 0
    spx_last  = latest_cap[1] if latest_cap else None
    net_gex   = latest_cap[2] if latest_cap else None
    key_strike = latest_cap[3] if latest_cap else None
    flip      = latest_cap[4] if latest_cap else None

    thesis    = analysis.get("thesis") or {}
    intraday  = analysis.get("intraday") or {}
    saved_ts  = et_now.strftime("%Y-%m-%dT%H:%M:%S")

    with _db() as con:
        con.execute("""
            INSERT INTO live_analysis
                (saved_ts, ndate, ntime, spx_last, net_gex, key_strike, flip,
                 regime, thesis_text, verdict, signals_json, intraday_summary, full_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ndate, ntime) DO UPDATE SET
                saved_ts        = excluded.saved_ts,
                spx_last        = excluded.spx_last,
                net_gex         = excluded.net_gex,
                key_strike      = excluded.key_strike,
                flip            = excluded.flip,
                regime          = excluded.regime,
                thesis_text     = excluded.thesis_text,
                verdict         = excluded.verdict,
                signals_json    = excluded.signals_json,
                intraday_summary = excluded.intraday_summary,
                full_json       = excluded.full_json
        """, (
            saved_ts, ndate, ntime, spx_last, net_gex, key_strike, flip,
            thesis.get("regime"),
            thesis.get("thesis"),
            analysis.get("verdict"),
            _json.dumps(intraday.get("signals", [])),
            intraday.get("summary"),
            _json.dumps(analysis),
        ))

    analysis["saved_ts"] = saved_ts
    analysis["ntime"] = ntime
    return jsonify(analysis)


@app.route("/api/live/analysis/history")
def api_live_analysis_history():
    """Return list of all saved analysis snapshots for a date (default today)."""
    date_iso = request.args.get("date")
    if not date_iso:
        date_iso = get_et_now().strftime("%Y-%m-%d")
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        rows = con.execute(
            "SELECT id, saved_ts, ndate, ntime, uprice, net_gex, key_strike, "
            "flip, regime, thesis_text, verdict, intraday_summary "
            "FROM live_analysis WHERE ndate=? ORDER BY ntime DESC",
            (ndate,),
        ).fetchall()
    cols = ["id", "saved_ts", "ndate", "ntime", "spx_last", "net_gex",
            "key_strike", "flip", "regime", "thesis_text", "verdict", "intraday_summary"]
    return jsonify({"date": date_iso, "rows": [dict(zip(cols, r)) for r in rows]})


@app.route("/api/live/analysis/saved")
def api_live_analysis_saved():
    """Return full persisted analysis JSON for a given ndate+ntime."""
    import json as _json
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 0))
    if not date_iso:
        date_iso = get_et_now().strftime("%Y-%m-%d")
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        row = con.execute(
            "SELECT full_json FROM live_analysis WHERE ndate=? AND ntime=?",
            (ndate, ntime),
        ).fetchone()
    if not row:
        return jsonify({"error": "No saved analysis for this date/time"}), 404
    return jsonify(_json.loads(row[0]))


def fetch_live_gex(symbol: str = "SPX") -> dict | None:
    """Call market.gex for the current day and normalize to histgex format."""
    from optionalpha_client import call_optionalpha_api
    from time import time as _time

    xid = current_xid(symbol)
    tid = int(_time() * 1000)
    payload = [
        {
            "t": "rpc",
            "tid": f"{tid}-10071",
            "api": "market.gex",
            "args": [symbol, xid],
        }
    ]
    raw = call_optionalpha_api(payload)

    # Find the market.gex response
    gex_data = None
    for item in raw:
        if item.get("api") == "market.gex":
            gex_data = item.get("data")
            break
    if not gex_data:
        return None

    # Normalize: market.gex uses "last" for price, histgex uses "uprice"
    et_now = get_et_now()
    ndate = int(et_now.strftime("%Y%m%d"))
    ntime = int(et_now.strftime("%H%M"))

    normalized = {
        "symbol": symbol,
        "ndate": ndate,
        "ntime": ntime,
        "uprice": gex_data.get("last", 0),
        "data": gex_data.get("data", []),
    }
    return normalized


def detect_volume_divergence(data: dict) -> str | None:
    """Detect volume divergence at the wall strike."""
    wall = None
    uprice = data.get("uprice", 0)
    gex_rows = data.get("data", [])

    # Find wall (highest absolute GEX)
    max_abs = 0
    for row in gex_rows:
        abs_gex = abs(row.get("net", 0) or 0)
        if abs_gex > max_abs:
            max_abs = abs_gex
            wall = row.get("strike")

    if not wall:
        return None

    # Check volume at wall
    for row in gex_rows:
        if row.get("strike") == wall:
            cvol = row.get("cvol", 0) or 0
            pvol = row.get("pvol", 0) or 0
            coi = row.get("coi", 0) or 0
            poi = row.get("poi", 0) or 0

            # If call wall (coi > poi) but heavy put volume -> bearish divergence
            if coi > poi and pvol > cvol * 1.5:
                return f"BEARISH at {wall}: heavy put vol ({pvol}) vs call vol ({cvol})"
            # If put wall (poi > coi) but heavy call volume -> bullish divergence
            elif poi > coi and cvol > pvol * 1.5:
                return f"BULLISH at {wall}: heavy call vol ({cvol}) vs put vol ({pvol})"
            # If put wall (poi > coi) with extremely heavy put volume -> bearish (aggressive downside positioning)
            elif poi > coi and pvol > cvol * 3:
                return f"BEARISH at {wall}: aggressive put vol ({pvol}) vs call vol ({cvol})"
            # If call wall (coi > poi) with extremely heavy call volume -> bullish (aggressive upside positioning)
            elif coi > poi and cvol > pvol * 3:
                return f"BULLISH at {wall}: aggressive call vol ({cvol}) vs put vol ({pvol})"

    return None


def save_live_snapshot(data: dict) -> None:
    """Save a live snapshot to SQLite snapshot."""
    ndate = data["ndate"]
    ntime = data["ntime"]
    rows = data.get("data") or []
    uprice = data.get("uprice", 0)
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO snapshot (ndate, ntime, symbol, uprice, raw_json, is_premarket, source) "
            "VALUES (?, ?, 'SPX', ?, ?, ?, 'gex')",
            (ndate, ntime, uprice, json.dumps(rows), 1 if ntime < 935 else 0),
        )


def load_live_snapshots(date_iso: str | None = None) -> list:
    """Load all live snapshots from snapshot table (date > yesterday ET)."""
    from datetime import timedelta
    et_now = get_et_now()
    yesterday = et_now - timedelta(days=1)
    yesterday_ndate = int(yesterday.strftime("%Y%m%d"))
    
    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, uprice, raw_json FROM snapshot "
            "WHERE ndate > ? AND symbol='SPX' ORDER BY ndate, ntime",
            (yesterday_ndate,)
        ).fetchall()
    snapshots = []
    for ndate, ntime, uprice, raw_json in rows:
        try:
            d = json.loads(raw_json) if raw_json else []
            snapshots.append({"ndate": ndate, "ntime": ntime, "uprice": uprice, "data": d})
        except Exception:
            continue
    return snapshots


def live_dates() -> list:
    """Return list of dates that have live snapshots (from DB)."""
    today_et = get_et_now()
    today_ndate = int(today_et.strftime("%Y%m%d"))
    with _db() as con:
        rows = con.execute(
            "SELECT DISTINCT ndate FROM snapshot "
            "WHERE ndate <= ? ORDER BY ndate",
            (today_ndate,),
        ).fetchall()
    return [
        f"{str(r[0])[:4]}-{str(r[0])[4:6]}-{str(r[0])[6:8]}"
        for r in rows
    ]


@app.route("/api/live/snapshots")
def api_live_snapshots():
    """Return all live snapshots for today (or specified date)."""
    date_iso = request.args.get("date")
    if not date_iso:
        et_now = get_et_now()
        date_iso = et_now.strftime("%Y-%m-%d")

    snapshots_raw = load_live_snapshots(date_iso)
    if not snapshots_raw:
        return jsonify({"date": date_iso, "snapshots": [], "times": []})

    times = [s.get("ntime", 0) for s in snapshots_raw]
    return jsonify({"date": date_iso, "snapshots_count": len(times), "times": times})


@app.route("/api/live/captures")
def api_live_captures():
    """Return snapshot rows for a given date (default: today ET), newest first."""
    date_iso = request.args.get("date")
    if not date_iso:
        date_iso = get_et_now().strftime("%Y-%m-%d")
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, uprice, sentiment, gex_ratio, net_gex, kcs, dominance, "
            "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
            "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
            "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
            "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip, "
            "is_premarket, hmm_state, hmm_label "
            "FROM snapshot WHERE ndate=? AND source='gex' ORDER BY ntime DESC",
            (ndate,),
        ).fetchall()
    cols = [
        "ndate", "ntime", "uprice", "sentiment", "gex_ratio", "net_gex", "kcs", "dominance",
        "total_call_gex", "total_put_gex", "key_strike", "key_call_gex", "key_put_gex",
        "total_call_oi", "total_put_oi", "key_call_oi", "key_put_oi",
        "total_call_vol", "total_put_vol", "key_call_vol", "key_put_vol",
        "key2_strike", "key2_abs", "key2_call_vol", "key2_put_vol", "flip",
        "is_premarket", "hmm_state", "hmm_label",
    ]
    return jsonify({"date": date_iso, "rows": [dict(zip(cols, r)) for r in rows]})


@app.route("/api/live/open-price", methods=["GET"])
def api_live_open_price_get():
    """Return the persisted SPX open price for a date (default today)."""
    date_iso = request.args.get("date")
    if not date_iso:
        date_iso = get_et_now().strftime("%Y-%m-%d")
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        row = con.execute(
            "SELECT open_price, set_ts FROM spx_open_prices WHERE ndate=?", (ndate,)
        ).fetchone()
    if row:
        return jsonify({"date": date_iso, "open_price": row[0], "set_ts": row[1]})
    return jsonify({"date": date_iso, "open_price": None, "set_ts": None})


@app.route("/api/live/open-price", methods=["POST"])
def api_live_open_price_post():
    """Persist the SPX open price for a date."""
    body = request.get_json(force=True) or {}
    date_iso = body.get("date") or get_et_now().strftime("%Y-%m-%d")
    open_price = body.get("open_price")
    if open_price is None:
        return jsonify({"error": "open_price required"}), 400
    ndate = int(date_iso.replace("-", ""))
    set_ts = get_et_now().strftime("%Y-%m-%dT%H:%M:%S")
    with _db() as con:
        con.execute(
            "INSERT INTO spx_open_prices (ndate, open_price, set_ts) VALUES (?,?,?) "
            "ON CONFLICT(ndate) DO UPDATE SET open_price=excluded.open_price, set_ts=excluded.set_ts",
            (ndate, float(open_price), set_ts),
        )
    return jsonify({"date": date_iso, "open_price": float(open_price), "set_ts": set_ts})


@app.route("/api/live/snapshot")
def api_live_snapshot():
    """Return a specific live snapshot by date and time."""
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 0))
    if not date_iso:
        et_now = get_et_now()
        date_iso = et_now.strftime("%Y-%m-%d")
    
    print(f"[DEBUG] api_live_snapshot: date_iso={date_iso}, ntime={ntime}")

    try:
        data = load_snapshot(date_iso, ntime)
        print(f"[DEBUG] load_snapshot returned: {data is not None}")
        if not data:
            return jsonify({"error": "Snapshot not found"}), 404

        snap = summarise_snapshot(data)
    except Exception as e:
        import traceback
        print(f"[ERROR] api_live_snapshot failed: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    uprice = snap.get("uprice", 0)
    all_rows = sorted(
        [r for r in (data.get("data") or []) if r.get("strike") is not None],
        key=lambda r: r["strike"]
    )
    below = [r for r in all_rows if r["strike"] < uprice]
    above = [r for r in all_rows if r["strike"] >= uprice]
    rows = below[-20:] + above[:20]

    strikes  = [r["strike"] for r in rows]
    call_gex = [r.get("calls", r.get("cg", 0)) or 0 for r in rows]
    put_gex  = [r.get("puts", r.get("pg", 0)) or 0 for r in rows]
    net_gex  = [r.get("net", 0) or 0 for r in rows]
    call_oi  = [r.get("coi", 0) or 0 for r in rows]
    put_oi   = [-(r.get("poi", 0) or 0) for r in rows]
    call_vol = [r.get("cvol", 0) or 0 for r in rows]
    put_vol  = [-(r.get("pvol", 0) or 0) for r in rows]

    cumulative_gex = []
    running = 0.0
    for v in net_gex:
        running += v
        cumulative_gex.append(round(running, 2))

    total_call_oi  = sum(r.get("coi", 0) or 0 for r in rows)
    total_put_oi   = sum(r.get("poi", 0) or 0 for r in rows)
    total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
    total_put_vol  = sum(r.get("pvol", 0) or 0 for r in rows)

    pos_bars = sum(1 for n in net_gex if n > 0)
    sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50
    # Use corrected GEX ratio calculation
    from controllers.gex_calculations import calculate_gex_ratio
    gex_ratio = calculate_gex_ratio(rows)
    net_g = sum(net_gex)

    snap["sentiment_pct"]  = sentiment_pct
    snap["gex_ratio"]      = gex_ratio
    snap["net_gex"]        = net_g
    snap["total_call_oi"]  = int(total_call_oi)
    snap["total_put_oi"]   = int(total_put_oi)
    snap["total_call_vol"] = int(total_call_vol)
    snap["total_put_vol"]  = int(total_put_vol)
    snap.update(_compute_key_strike_stats(rows, uprice))

    # Teaching points (no prev_snap for live)
    points = teaching_points(snap, None, [])

    is_pre = 1 if ntime < RTH_OPEN else 0
    snap["is_premarket"] = is_pre

    # Fetch hmm_label from snapshot if available
    ndate = int(date_iso.replace("-", ""))
    with _db() as con:
        live_row = con.execute(
            "SELECT hmm_state, hmm_label FROM snapshot WHERE ndate=? AND ntime=?",
            (ndate, ntime),
        ).fetchone()
    if live_row:
        snap["hmm_state"] = live_row[0]
        snap["hmm_label"] = live_row[1]

    return jsonify({
        "summary":        snap,
        "strikes":        strikes,
        "call_gex":       call_gex,
        "put_gex":        put_gex,
        "net_gex":        net_gex,
        "cumulative_gex": cumulative_gex,
        "call_oi":        call_oi,
        "put_oi":         put_oi,
        "call_vol":       call_vol,
        "put_vol":        put_vol,
        "points":         points,
        "date":           date_iso,
        "ntime":          ntime,
        "is_premarket":   is_pre,
    })


# ---------------------------------------------------------------------------
# HTML Template (legacy — now served from templates/gex_viewer.html)
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GEX Intraday Viewer</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; }
    .card { background: #161b22; border: 1px solid #30363d; }
    .card-header { background: #21262d; border-bottom: 1px solid #30363d; }
    select, .btn { border-radius: 6px; }
    #spx-chart { width: 100%; height: 340px; }
    #gex-chart { width: 100%; height: 400px; }
    .point-card { border-left: 4px solid; margin-bottom: 8px; padding: 10px 14px;
                  border-radius: 4px; background: #21262d; font-size: 0.88rem; }
    .point-card.danger  { border-color: #f85149; }
    .point-card.success { border-color: #3fb950; }
    .point-card.warning { border-color: #d29922; }
    .point-card.info    { border-color: #58a6ff; }
    .point-card.primary { border-color: #388bfd; }
    .point-card.secondary { border-color: #8b949e; }
    .point-card.dark    { border-color: #6e7681; }
    .point-title { font-weight: 600; margin-bottom: 3px; }
    .time-badge { font-size: 1.1rem; font-weight: 700; color: #58a6ff; }
    .regime-badge { padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
    .regime-neg { background: #3d1f1f; color: #f85149; }
    .regime-pos { background: #1f3d25; color: #3fb950; }
    .stat-val { font-size: 1.05rem; font-weight: 600; }
  </style>
</head>
<body>
<div class="container-fluid px-3 py-3">

  <!-- Header controls -->
  <div class="card mb-3">
    <div class="card-body py-2">
      <div class="row align-items-center g-2">
        <div class="col-auto">
          <label class="form-label mb-0 me-2 fw-semibold">Date</label>
          <select id="date-sel" class="form-select form-select-sm d-inline-block" style="width:auto"></select>
        </div>
        <div class="col-auto">
          <button class="btn btn-sm btn-outline-secondary" id="btn-prev" disabled>&#8592; Prev 30m</button>
          <span class="time-badge mx-3" id="lbl-time">09:30</span>
          <button class="btn btn-sm btn-primary" id="btn-next">Next 30m &#8594;</button>
        </div>
        <div class="col-auto ms-auto">
          <span id="regime-badge" class="regime-badge">—</span>
        </div>
        <div class="col-auto">
          <small class="text-muted" id="lbl-uprice">SPX —</small>
        </div>
        <div class="col-auto">
          <small class="text-muted" id="lbl-wall">Wall —</small>
        </div>
        <div class="col-auto">
          <small class="text-muted" id="lbl-flip">Flip —</small>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <!-- Left: charts -->
    <div class="col-lg-8">
      <div class="card mb-3">
        <div class="card-header py-2 fw-semibold">SPX Price — GEX Levels Overlaid</div>
        <div class="card-body p-1"><div id="spx-chart"></div></div>
      </div>
      <div class="card">
        <div class="card-header py-2 fw-semibold">GEX by Strike — Current Snapshot</div>
        <div class="card-body p-1"><div id="gex-chart"></div></div>
      </div>
    </div>

    <!-- Right: teaching points -->
    <div class="col-lg-4">
      <div class="card h-100">
        <div class="card-header py-2 fw-semibold">&#127979; GEX Teaching Points</div>
        <div class="card-body" id="points-panel" style="overflow-y:auto;max-height:720px">
          <p class="text-muted">Select a date to begin.</p>
        </div>
      </div>
    </div>
  </div>

</div>

<script>
const TIMES = [930,1000,1030,1100,1130,1200,1230,1300,1330,1400,1430,1500,1530];
let timeIdx = 0;
let prevTime = null;
let currentDate = null;

function fmtTime(t) {
  const s = t.toString().padStart(4,'0');
  return s.slice(0,2)+':'+s.slice(2);
}

function fmtBig(n) {
  if (Math.abs(n) >= 1e9) return (n/1e9).toFixed(1)+'B';
  if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(0)+'M';
  return n.toFixed(0);
}

async function loadDates() {
  const r = await fetch('/api/dates');
  const dates = await r.json();
  const sel = document.getElementById('date-sel');
  dates.forEach(d => {
    const opt = document.createElement('option'); opt.value = d; opt.textContent = d; sel.appendChild(opt);
  });
  if (dates.length) { sel.value = dates[dates.length-1]; loadDay(dates[dates.length-1]); }
}

function loadDay(date) {
  currentDate = date; timeIdx = 0; prevTime = null;
  document.getElementById('btn-prev').disabled = true;
  document.getElementById('btn-next').disabled = false;
  loadSnapshot();
}

async function loadSnapshot() {
  const ntime = TIMES[timeIdx];
  const url = `/api/snapshot?date=${currentDate}&time=${ntime}` + (prevTime ? `&prev_time=${prevTime}` : '');
  const r = await fetch(url);
  if (!r.ok) { alert('No data for this slot'); return; }
  const d = await r.json();

  document.getElementById('lbl-time').textContent = fmtTime(ntime);
  document.getElementById('lbl-uprice').textContent = 'SPX ' + d.summary.uprice.toFixed(2);

  const wall = d.summary.wall;
  const flip = d.summary.flip;
  const net  = d.summary.net_gex;

  document.getElementById('lbl-wall').textContent = wall ? 'Wall '+wall : 'Wall —';
  document.getElementById('lbl-flip').textContent = flip ? 'Flip '+flip.toFixed(0) : 'Flip —';

  const rb = document.getElementById('regime-badge');
  if (net < 0) { rb.textContent='NEGATIVE GEX'; rb.className='regime-badge regime-neg'; }
  else         { rb.textContent='POSITIVE GEX'; rb.className='regime-badge regime-pos'; }

  renderSpxChart(d, wall, flip);
  renderGexChart(d);
  renderPoints(d.points);
}

function renderSpxChart(d, wall, flip) {
  const bars = d.spx_bars;
  const traces = [];

  if (bars.length) {
    traces.push({
      type: 'candlestick',
      x: bars.map(b=>b.time_str),
      open:  bars.map(b=>b.Open),
      high:  bars.map(b=>b.High),
      low:   bars.map(b=>b.Low),
      close: bars.map(b=>b.Close),
      name: 'SPX',
      increasing: {line:{color:'#3fb950'}},
      decreasing: {line:{color:'#f85149'}},
    });
  } else {
    // Fall back to GEX uprice dot
    traces.push({
      type:'scatter', mode:'markers',
      x:[fmtTime(TIMES[timeIdx])], y:[d.summary.uprice],
      marker:{color:'#58a6ff', size:10}, name:'SPX (uprice)'
    });
  }

  const shapes = [];
  if (wall) shapes.push({ type:'line', x0:0,x1:1, xref:'paper', y0:wall,y1:wall,
    line:{color:'#58a6ff', width:1.5, dash:'dash'} });
  if (flip) shapes.push({ type:'line', x0:0,x1:1, xref:'paper', y0:flip,y1:flip,
    line:{color:'#d29922', width:1.5, dash:'dot'} });

  const annotations = [];
  if (wall) annotations.push({xref:'paper',yref:'y',x:1.01,y:wall,text:'<b>Wall '+wall+'</b>',
    showarrow:false,font:{color:'#58a6ff',size:11},xanchor:'left'});
  if (flip) annotations.push({xref:'paper',yref:'y',x:1.01,y:flip,text:'Flip '+flip.toFixed(0),
    showarrow:false,font:{color:'#d29922',size:11},xanchor:'left'});

  Plotly.react('spx-chart', traces, {
    paper_bgcolor:'#161b22', plot_bgcolor:'#0d1117',
    font:{color:'#e6edf3', size:11},
    margin:{t:10,b:40,l:60,r:80},
    xaxis:{gridcolor:'#21262d', type:'category', nticks:13},
    yaxis:{gridcolor:'#21262d'},
    showlegend:false, shapes, annotations,
  }, {responsive:true, displayModeBar:false});
}

function renderGexChart(d) {
  const strikes = d.strikes;
  const uprice  = d.summary.uprice;
  const wall    = d.summary.wall;

  // Call GEX (positive) = green, Put GEX (negative, flip sign for display) = red
  const callColors = strikes.map(s => s === wall ? '#1f6feb' : '#3fb950');
  const putColors  = strikes.map(s => s === wall ? '#1f6feb' : '#f85149');

  const traces = [
    { type:'bar', name:'Call GEX', x:strikes, y:d.call_gex,
      marker:{color:callColors}, hovertemplate:'%{x}: %{y:.2e}<extra>Call GEX</extra>' },
    { type:'bar', name:'Put GEX',  x:strikes, y:d.put_gex,
      marker:{color:putColors},  hovertemplate:'%{x}: %{y:.2e}<extra>Put GEX</extra>' },
  ];

  const shapes = [
    { type:'line', x0:uprice,x1:uprice, yref:'paper',y0:0,y1:1,
      line:{color:'#ffffff',width:2} }
  ];

  if (d.summary.flip) {
    shapes.push({ type:'line', x0:d.summary.flip,x1:d.summary.flip, yref:'paper',y0:0,y1:1,
      line:{color:'#d29922',width:1.5,dash:'dot'} });
  }

  Plotly.react('gex-chart', traces, {
    barmode:'relative',
    paper_bgcolor:'#161b22', plot_bgcolor:'#0d1117',
    font:{color:'#e6edf3', size:11},
    margin:{t:10,b:50,l:70,r:20},
    xaxis:{
      gridcolor:'#21262d',
      title:{text:'Strike', font:{size:11}},
      range:[uprice - 125, uprice + 125],
      tickmode:'linear', dtick:25,
    },
    yaxis:{
      gridcolor:'#21262d',
      title:{text:'GEX ($)', font:{size:11}},
      zeroline:true, zerolinecolor:'#444c56', zerolinewidth:1,
    },
    showlegend:true,
    legend:{orientation:'h', y:1.05, font:{size:10}},
    shapes,
  }, {responsive:true, displayModeBar:false});
}

function renderPoints(points) {
  const panel = document.getElementById('points-panel');
  if (!points || !points.length) { panel.innerHTML='<p class="text-muted">No teaching points.</p>'; return; }
  panel.innerHTML = points.map(p => `
    <div class="point-card ${p.type}">
      <div class="point-title">${p.icon} ${p.title}</div>
      <div>${p.text}</div>
    </div>`).join('');
}

document.getElementById('date-sel').addEventListener('change', e => loadDay(e.target.value));

document.getElementById('btn-next').addEventListener('click', () => {
  if (timeIdx < TIMES.length - 1) {
    prevTime = TIMES[timeIdx];
    timeIdx++;
    document.getElementById('btn-prev').disabled = false;
    document.getElementById('btn-next').disabled = (timeIdx === TIMES.length - 1);
    loadSnapshot();
  }
});

document.getElementById('btn-prev').addEventListener('click', () => {
  if (timeIdx > 0) {
    timeIdx--;
    prevTime = timeIdx > 0 ? TIMES[timeIdx-1] : null;
    document.getElementById('btn-next').disabled = false;
    document.getElementById('btn-prev').disabled = (timeIdx === 0);
    loadSnapshot();
  }
});

loadDates();
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _verify_data() -> dict:
    """Verify data integrity - basic table existence check only.

    gex_strike_window uses raw JSON data with on-the-fly calculations,
    so flat column verification is not applicable.
    """
    from datetime import datetime

    with _db() as con:
        # Basic check: count SPX snapshots in gex_strike_window
        count = con.execute(
            "SELECT COUNT(*) FROM gex_strike_window WHERE symbol='SPX'"
        ).fetchone()[0]

    return {
        "timestamp": datetime.now().isoformat(),
        "total_snapshots": count,
        "status": "ok"
    }


if __name__ == "__main__":
    import argparse, webbrowser, threading

    # Run startup migrations and backfills only when the server is launched directly.
    # _ensure_snapshot_table()  # REMOVED: snapshot table no longer used
    # _migrate_to_snapshot()  # Already run manually
    # _ensure_snapshot_table()  # REMOVED: snapshot table no longer used
    _ensure_live_analysis_table()
    _ensure_spx_ohlc_table()
    _ensure_magnet_days_table()
    _ensure_ml_labels_current()
    _ensure_ml_models_table()
    _ensure_ml_predictions_table()
    _maybe_retrain_ml_models()
    _backfill_prediction_outcomes()
    _ensure_spx_open_prices_table()
    _populate_spx_open_prices_from_csv()  # fill spx_open_prices from CSV (ignores existing)
    # _ensure_snapshot_premarket()  # REMOVED: snapshot table no longer used
    # _ensure_snapshot_summary_columns()  # REMOVED: snapshot table no longer used
    # _drop_legacy_snapshots_table()  # REMOVED: snapshot table no longer used
    _ensure_hmm_tables()
    _ensure_metric_history_table()
    # _backfill_snapshot_gex_ratio()  # REMOVED: snapshot table no longer used
    # _backfill_snapshot_nulls()  # REMOVED: snapshot table no longer used
    # _backfill_snapshot_nulls()  # REMOVED: snapshot table no longer used
    # _promote_live_to_historical()  # REMOVED: snapshot table no longer used
    # _backfill_snapshot_summary(force=True)  # REMOVED: snapshot table no longer used
    # _HISTORY_CACHE.clear()  # REMOVED: no longer needed
    # _populate_metric_history()  # populate EOD metric values from histograms - DISABLED TEMPORARILY
    _ensure_percentile_history_table()
    # _populate_percentile_history()  # populate time-slot percentiles for rankings - DISABLED TEMPORARILY
    _ensure_narratives_table()
    # _train_hmm()  # train on startup if model is missing or >7 days old; also backfills HMM labels - DISABLED TEMPORARILY
    # _backfill_hmm_labels_for_snapshot(only_null=True)  # fill labels for any newly added snapshots - DISABLED TEMPORARILY

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()
    PORT = args.port
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()
    print(f"GEX Viewer running at http://localhost:{PORT}")
    print("Bot routes:", [str(r) for r in app.url_map.iter_rules() if 'bot' in str(r)])
    print("Press Ctrl+C to stop.")
    app.run(port=PORT, debug=False)
    # _populate_percentile_history()  # populate time-slot percentiles for rankings - DISABLED TEMPORARILY
    _ensure_narratives_table()
    # _train_hmm()  # train on startup if model is missing or >7 days old; also backfills HMM labels - DISABLED TEMPORARILY
    # _backfill_hmm_labels_for_snapshot(only_null=True)  # fill labels for any newly added snapshots - DISABLED TEMPORARILY

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()
    PORT = args.port
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()
    print(f"GEX Viewer running at http://localhost:{PORT}")
    print("Bot routes:", [str(r) for r in app.url_map.iter_rules() if 'bot' in str(r)])
    print("Press Ctrl+C to stop.")
    app.run(port=PORT, debug=False)
