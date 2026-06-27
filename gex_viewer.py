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
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request

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
            if "disk I/O" in str(exc):
                # Try to remove stale WAL/SHM left by Drive sync
                for f in (wal, shm):
                    try:
                        if f.exists() and f.stat().st_size == 0:
                            f.unlink()
                    except OSError:
                        pass
                _time.sleep(0.5 * (attempt + 1))
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
    rth_snaps = [s for s in snapshots if s["ntime"] >= 930]
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
            con.execute("UPDATE snapshot SET is_premarket=1 WHERE ntime < 930")
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
    """Recompute gex_ratio for all snapshot rows using the new flip-sign formula."""
    updated = 0
    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, total_call_gex, total_put_gex FROM snapshot WHERE total_call_gex IS NOT NULL"
        ).fetchall()

    for ndate, ntime, total_call_gex, total_put_gex in rows:
        # New formula: flip sign based on which side is larger
        total_call_gex_sum = total_call_gex or 0
        total_put_gex_sum = abs(total_put_gex or 0)
        if total_call_gex_sum > total_put_gex_sum:
            gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
        else:
            gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0

        with _db() as con:
            con.execute(
                "UPDATE snapshot SET gex_ratio=? WHERE ndate=? AND ntime=?",
                (gex_ratio, ndate, ntime)
            )
        updated += 1

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

    Only updates RTH snapshots (ntime >= 930). Pre-market rows keep hmm_label=NULL.

    If only_null=True, only dates with at least one RTH row lacking a label are
    processed, which is useful for filling labels after new snapshots are added
    without retraining the model.
    """
    with _db() as con:
        if only_null:
            dates = [r[0] for r in con.execute(
                "SELECT DISTINCT ndate FROM snapshot "
                "WHERE symbol='SPX' AND ntime>=930 AND hmm_label IS NULL ORDER BY ndate"
            ).fetchall()]
        else:
            dates = [r[0] for r in con.execute(
                "SELECT DISTINCT ndate FROM snapshot WHERE symbol='SPX' AND ntime>=930 ORDER BY ndate"
            ).fetchall()]
    updated = 0
    for ndate in dates:
        with _db() as con:
            rows = con.execute(
                "SELECT ntime, uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
                "FROM snapshot WHERE ndate=? AND symbol='SPX' AND ntime>=930 ORDER BY ntime",
                (ndate,),
            ).fetchall()
        snaps = [
            {"uprice": r[1], "net_gex": r[2], "kcs": r[3], "sentiment_pct": r[4],
             "key_strike": r[5], "total_put_vol": r[6]}
            for r in rows
        ]
        if not snaps:
            continue
        hmm_results = predict_hmm_sequence(snaps)
        for (ntime, *_), hmm in zip(rows, hmm_results):
            state = hmm.get("state")
            label = hmm.get("label")
            with _db() as con:
                con.execute(
                    "UPDATE snapshot SET hmm_state=?, hmm_label=? "
                    "WHERE ndate=? AND ntime=? AND symbol='SPX'",
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
                    (ndate, ntime, spx_last or 0, 1 if ntime < 930 else 0,
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
        caps = [r[1] for r in con.execute("PRAGMA table_info(snapshot)").fetchall()]
        if "hmm_state" not in caps:
            con.execute("ALTER TABLE snapshot ADD COLUMN hmm_state INTEGER")
        if "hmm_label" not in caps:
            con.execute("ALTER TABLE snapshot ADD COLUMN hmm_label TEXT")


# HMM feature set (5 features covering the 5 independent PCA dimensions)
HMM_FEATURES = ["net_gex", "kcs", "sentiment_pct", "dist_to_key", "total_put_vol"]
HMM_N_STATES = 4


def _build_hmm_matrix() -> tuple:
    """Collect all RTH snapshots and build a normalised feature matrix.

    Reads directly from the flat summary columns stored in snapshot, so
    no JSON parsing or re-summarisation is needed.

    Returns (X_scaled, scaler, raw_df) or (None, None, None) if insufficient data.
    """
    import numpy as np
    import pandas as pd
    from sklearn.preprocessing import StandardScaler

    with _db() as con:
        rows = con.execute(
            "SELECT ndate, ntime, uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
            "FROM snapshot "
            "WHERE symbol='SPX' AND ntime>=930 AND net_gex IS NOT NULL "
            "ORDER BY ndate, ntime"
        ).fetchall()

    records = []
    for ndate, ntime, uprice, net_gex, kcs, sentiment, key_strike, total_put_vol in rows:
        if not uprice:
            continue
        key = key_strike or uprice
        records.append({
            "net_gex":       (net_gex or 0) / 1e9,
            "kcs":           kcs or 0,
            "sentiment_pct": sentiment or 50,
            "dist_to_key":   abs(uprice - key),
            "total_put_vol": (total_put_vol or 0) / 1e3,
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
    """Compute PCA over the flat summary features stored in snapshot.

    Returns explained variance, cumulative variance, per-component feature
    loadings, and the list of features used. Used to visualise the independent
    dimensions that drive the HMM feature selection.
    """
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA

    FEATURES = [
        "net_gex", "total_call_gex", "total_put_gex",
        "sentiment", "gex_ratio", "kcs", "dominance",
        "total_call_oi", "total_put_oi",
        "total_call_vol", "total_put_vol",
        "key_call_gex", "key_put_gex",
        "key_call_oi", "key_put_oi",
        "key_call_vol", "key_put_vol",
        "dist_to_key", "dist_to_flip", "key2_abs",
    ]

    with _db() as con:
        rows = con.execute(
            "SELECT uprice, net_gex, total_call_gex, total_put_gex, sentiment, gex_ratio, kcs, dominance, "
            "total_call_oi, total_put_oi, total_call_vol, total_put_vol, "
            "key_call_gex, key_put_gex, key_call_oi, key_put_oi, key_call_vol, key_put_vol, "
            "key_strike, flip, key2_abs "
            "FROM snapshot WHERE symbol='SPX' AND ntime>=930 AND net_gex IS NOT NULL"
        ).fetchall()

    records = []
    for r in rows:
        (uprice, net_gex, total_call_gex, total_put_gex, sentiment, gex_ratio, kcs, dominance,
         total_call_oi, total_put_oi, total_call_vol, total_put_vol,
         key_call_gex, key_put_gex, key_call_oi, key_put_oi, key_call_vol, key_put_vol,
         key_strike, flip, key2_abs) = r
        if not uprice:
            continue
        key = key_strike or uprice
        dist_to_key = abs(uprice - key)
        dist_to_flip = abs(uprice - flip) if flip else 0
        records.append({
            "net_gex": net_gex or 0,
            "total_call_gex": total_call_gex or 0,
            "total_put_gex": total_put_gex or 0,
            "sentiment": sentiment or 50,
            "gex_ratio": gex_ratio or 0,
            "kcs": kcs or 0,
            "dominance": dominance or 0,
            "total_call_oi": total_call_oi or 0,
            "total_put_oi": total_put_oi or 0,
            "total_call_vol": total_call_vol or 0,
            "total_put_vol": total_put_vol or 0,
            "key_call_gex": key_call_gex or 0,
            "key_put_gex": key_put_gex or 0,
            "key_call_oi": key_call_oi or 0,
            "key_put_oi": key_put_oi or 0,
            "key_call_vol": key_call_vol or 0,
            "key_put_vol": key_put_vol or 0,
            "dist_to_key": dist_to_key,
            "dist_to_flip": dist_to_flip,
            "key2_abs": key2_abs or 0,
        })

    if len(records) < 5:
        return {"status": "error", "reason": "insufficient data (<5 snapshots)"}

    df = pd.DataFrame(records)[FEATURES]
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
            "top_features": [{"feature": f, "loading": round(l, 3)} for f, l in loadings[:5]],
        })

    return {
        "status": "ok",
        "n_samples": len(records),
        "n_features": len(FEATURES),
        "features": FEATURES,
        "hmm_features": HMM_FEATURES,
        "explained_variance_ratio": evr,
        "cumulative_variance": cumulative,
        "components": component_details,
    }


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
TIMES = [930, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555, 1600]

# Time regimes for Distribution page filtering
TIME_REGIMES = [
    {"id": "pre", "label": "Pre-Market", "start": 0, "end": 929},
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


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_spx() -> pd.DataFrame:
    """Legacy CSV loader - kept for reference only. SPX price data now sourced from DB."""
    return pd.DataFrame()


RTH_OPEN = 930   # Regular Trading Hours start (ET)
RTH_CLOSE = 1600  # Regular Trading Hours end (ET)


def get_spx_ohlc_from_db(date_iso: str) -> dict | None:
    """Derive SPX OHLC for a date from the uprice values stored in snapshot.

    Only uses RTH prices (ntime >= 930) so pre-market captures don't corrupt
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
    for all ntimes in [930, up_to_ntime].
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
    # New formula: flip sign based on which side is larger
    if cg > abs(pg):
        gex_ratio = round(cg / abs(pg), 2) if pg else 0
    else:
        gex_ratio = round(-abs(pg) / cg, 2) if cg else 0

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

    # Ratio flips sign based on which side is larger
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum = abs(sum(put_gex))
    if total_call_gex_sum > total_put_gex_sum:
        gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
    else:
        gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0

    net_g = sum(net_gex)

    key_stats = _compute_key_strike_stats(window_rows, uprice)

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

    # Ratio flips sign based on which side is larger
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum = abs(sum(put_gex))
    if total_call_gex_sum > total_put_gex_sum:
        gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
    else:
        gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0

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
    from time import time
    return render_template("historical.html", cache_bust=int(time()))

@app.route("/old")
def index_old():
    from time import time
    return render_template("gex_viewer.html", cache_bust=int(time()))

@app.route("/simple")
def simple():
    from time import time
    return render_template("gex_viewer_simple.html", cache_bust=int(time()))

@app.route("/live")
def live():
    from time import time
    return render_template("live.html", cache_bust=int(time()))

@app.route("/analysis")
def analysis():
    from time import time
    return render_template("analysis.html", cache_bust=int(time()))

@app.route("/hscatter")
def hscatter():
    from time import time
    return render_template("hscatter.html", cache_bust=int(time()))

@app.route("/admin")
def admin():
    from time import time
    return render_template("admin.html", cache_bust=int(time()))

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
    ntime = int(request.args.get("time", 930))

    dates = available_dates()
    rows = []

    for date_iso in dates:
        data = load_gex_snapshot(date_iso, ntime)
        if data is None:
            continue

        rows_data = data.get("data", [])
        if not rows_data:
            continue

        uprice = data.get("uprice", 0)

        # Use 40-strike window method (same as api_snapshot)
        all_rows = sorted(
            [r for r in rows_data if r.get("strike") is not None],
            key=lambda r: r["strike"]
        )
        below = [r for r in all_rows if r["strike"] < uprice]
        above = [r for r in all_rows if r["strike"] >= uprice]
        window_rows = below[-20:] + above[:20]

        call_gex = [r.get("cg", 0) or 0 for r in window_rows]
        put_gex = [r.get("pg", 0) or 0 for r in window_rows]
        net_gex = [r.get("net", 0) or 0 for r in window_rows]

        # Sentiment = % of positive net GEX bars within the 40 strikes
        pos_bars = sum(1 for n in net_gex if n > 0)
        sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50

        # Ratio flips sign based on which side is larger
        total_call_gex_sum = sum(call_gex)
        total_put_gex_sum = abs(sum(put_gex))
        if total_call_gex_sum > total_put_gex_sum:
            gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
        else:
            gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0

        # Net GEX
        net_g = sum(net_gex)

        # Key stats
        key_stats = _compute_key_strike_stats(window_rows, uprice)

        # Total OI and Vol
        total_call_oi = sum(r.get("coi", 0) or 0 for r in window_rows)
        total_put_oi = sum(r.get("poi", 0) or 0 for r in window_rows)
        total_call_vol = sum(r.get("cvol", 0) or 0 for r in window_rows)
        total_put_vol = sum(r.get("pvol", 0) or 0 for r in window_rows)

        row = {
            "date": date_iso,
            "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
            "SPX-last": uprice,
            "sentiment": sentiment_pct,
            "gex_ratio": gex_ratio,
            "net_gex": net_g,
            "key_strike": key_stats.get("key_strike"),
            "key_absolute": key_stats.get("key_dominance_pct"),
            "key_net": key_stats.get("key_call_gex", 0) - key_stats.get("key_put_gex", 0),
            "key_dominance_pct": key_stats.get("key_dominance_pct"),
            "key_call_gex": key_stats.get("key_call_gex"),
            "key_put_gex": key_stats.get("key_put_gex"),
            "key_call_oi": key_stats.get("key_call_oi"),
            "key_put_oi": key_stats.get("key_put_oi"),
            "key_net_oi": key_stats.get("key_call_oi", 0) - key_stats.get("key_put_oi", 0),
            "key_call_vol": key_stats.get("key_call_vol"),
            "OI Calls": total_call_oi,
            "OI Puts": total_put_oi,
            "Vol Calls": total_call_vol,
            "Vol Puts": total_put_vol,
        }
        rows.append(row)

    columns = [
        "date", "time", "SPX-last", "sentiment", "gex_ratio", "net_gex",
        "key_strike", "key_absolute", "key_net", "key_dominance_pct",
        "key_call_gex", "key_put_gex", "key_call_oi", "key_put_oi", "key_net_oi",
        "key_call_vol", "OI Calls", "OI Puts", "Vol Calls", "Vol Puts"
    ]

    # Reverse rows so newest dates come first
    rows.reverse()

    return jsonify({"columns": columns, "rows": rows})


@app.route("/api/snapshot")
def api_snapshot():
    """Route now delegates to SnapshotController (Phase 5 migration)."""
    return SnapshotController.get_snapshot()


@app.route("/api/snapshots")
def api_snapshots():
    """Route now delegates to SnapshotController (Phase 5 migration)."""
    return SnapshotController.get_snapshots()


@app.route("/api/snapshots/summary")
def api_snapshots_summary():
    """Return a compact summary row for every available time-slot on a date.

    Sourced from the unified snapshot table.
    Columns match the snapshot table schema so both tabs can share the
    same frontend table renderer.
    """
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"date": date_iso, "rows": []})
    ndate = int(date_iso.replace("-", ""))
    fields = [
        "ntime", "uprice", "sentiment", "gex_ratio", "net_gex", "kcs", "dominance",
        "total_call_gex", "total_put_gex", "key_strike", "key_call_gex", "key_put_gex",
        "total_call_oi", "total_put_oi", "key_call_oi", "key_put_oi",
        "total_call_vol", "total_put_vol", "key_call_vol", "key_put_vol",
        "key2_strike", "key2_abs", "key2_call_vol", "key2_put_vol", "flip",
        "hmm_state", "hmm_label", "is_premarket",
    ]
    sql = f"SELECT {', '.join(fields)} FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime DESC"
    with _db() as con:
        rows = con.execute(sql, (ndate,)).fetchall()

    result = []
    for r in rows:
        result.append({
            "ntime":          r[0],
            "spx_last":       r[1],
            "sentiment":      r[2],
            "gex_ratio":      r[3],
            "net_gex":        r[4],
            "kcs":            r[5],
            "dominance":      r[6],
            "total_call_gex": r[7],
            "total_put_gex":  r[8],
            "key_strike":     r[9],
            "key_call_gex":   r[10],
            "key_put_gex":    r[11],
            "total_call_oi":  r[12],
            "total_put_oi":   r[13],
            "key_call_oi":    r[14],
            "key_put_oi":     r[15],
            "total_call_vol": r[16],
            "total_put_vol":  r[17],
            "key_call_vol":   r[18],
            "key_put_vol":    r[19],
            "key2_strike":    r[20],
            "key2_abs":       r[21],
            "key2_call_vol":  r[22],
            "key2_put_vol":   r[23],
            "flip":           r[24],
            "hmm_state":      r[25],
            "hmm_label":      r[26],
            "is_premarket":   r[27] if r[27] is not None else (1 if r[0] < RTH_OPEN else 0),
        })
    return jsonify({"date": date_iso, "rows": result})


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
        if use_live:
            snap_rows = con.execute(
                "SELECT ntime, uprice, net_gex, sentiment, gex_ratio, kcs, dominance, "
                "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                "key2_strike, key2_abs, flip, hmm_label, 0 as is_premarket "
                "FROM snapshot WHERE ndate=? ORDER BY ntime",
                (ndate,)
            ).fetchall()
        else:
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
        return jsonify({"error": "No snapshots found for date"}), 404

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
    """Return all snapshots with pagination for Distribution page.

    Includes both snapshot (historical) and snapshot (today's live data).

    Query params:
        offset: pagination offset (default 0)
        limit: rows per page (default 200, max 500)
        regime: time regime filter (e.g., "0930_1000", "pre")
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt
    today_ndate = int(_dt.now(ZoneInfo("America/New_York")).strftime("%Y%m%d"))

    offset = int(request.args.get("offset", 0))
    limit = min(int(request.args.get("limit", 200)), 500)
    regime_id = request.args.get("regime", "0930_1000")

    # Get time range for selected regime
    regime = next((r for r in TIME_REGIMES if r["id"] == regime_id), TIME_REGIMES[1])  # default to 0930_1000
    time_start = regime["start"]
    time_end = regime["end"]

    with _db() as con:
        # Get total count (snapshot historical + today's snapshot) filtered by regime
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

        # Get paginated rows from snapshot (historical only, exclude today, filtered by regime)
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

        # Get today's snapshot (only on first page, filtered by regime)
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

    # Process live rows first (they have priority for duplicates)
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

    return jsonify({
        "snapshots": snapshots,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    })


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


INTRADAY_TIMES = [930, 1000, 1030, 1100, 1130, 1200, 1230,
                  1300, 1330, 1400, 1430, 1500, 1530]


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


def sync_historical(symbol: str = "SPX", max_days: int = 30) -> dict:
    """Fetch missing historical GEX data working backwards from yesterday.

    First promotes any prior-day live snapshots into snapshot, then
    fetches remaining missing slots from the OptionAlpha histgex API.

    Uses market.histgex (not market.gex) — market.gex returns 501 for historical
    dates because it only serves the current live trading day.

    Fetches all 13 intraday time slots (930–1530) per date.
    Skips a date only when all 13 slots are already present.

    Returns dict with fetched, skipped, failed counts and migration summary.
    """
    import time as _time_mod
    from datetime import date, timedelta
    from gex_historical_intraday import fetch_histgex

    # Step 1: migrate prior-day live snapshots into snapshot first
    migration = _migrate_live_snapshots_to_history(symbol)

    yesterday = date.today() - timedelta(days=1)
    fetched = []
    skipped = []
    failed = []

    for i in range(max_days):
        d = yesterday - timedelta(days=i)
        iso = d.isoformat()
        ymd = d.strftime("%Y%m%d")
        ndate = int(ymd)

        existing_times = _existing_times(ndate, symbol)
        missing_times = [t for t in INTRADAY_TIMES if t not in existing_times]

        if not missing_times:
            skipped.append(iso)
            continue

        day_fetched = 0
        day_failed = 0

        for ntime in missing_times:
            try:
                data = fetch_histgex(symbol=symbol, ndate=ndate, ntime=ntime)
                if not data:
                    raise ValueError(f"market.histgex returned no data for {ntime}")
                rows = data.get("data") or []
                if not rows:
                    raise ValueError(f"no strike rows for {ntime}")
                uprice = data.get("uprice", 0)

                # Write to SQLite with flat summary columns
                snap = _compute_flat_summary({"uprice": uprice, "data": rows})
                with _db() as con:
                    con.execute(
                        "INSERT OR IGNORE INTO snapshot "
                        "(ndate, ntime, symbol, uprice, data, is_premarket, source, raw_json, "
                        "sentiment, gex_ratio, net_gex, kcs, dominance, "
                        "total_call_gex, total_put_gex, key_strike, key_call_gex, key_put_gex, "
                        "total_call_oi, total_put_oi, key_call_oi, key_put_oi, "
                        "total_call_vol, total_put_vol, key_call_vol, key_put_vol, "
                        "key2_strike, key2_abs, key2_call_vol, key2_put_vol, flip) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ndate, ntime, symbol, uprice, json.dumps(rows), 1 if ntime < RTH_OPEN else 0, 'histgex', json.dumps(data),
                         snap.get("sentiment_pct"), snap.get("gex_ratio"), snap.get("net_gex"), snap.get("kcs"), snap.get("key_dominance_pct"),
                         snap.get("total_call_gex"), snap.get("total_put_gex"), snap.get("key_strike"), snap.get("key_call_gex"), snap.get("key_put_gex"),
                         snap.get("total_call_oi"), snap.get("total_put_oi"), snap.get("key_call_oi"), snap.get("key_put_oi"),
                         snap.get("total_call_vol"), snap.get("total_put_vol"), snap.get("key_call_vol"), snap.get("key_put_vol"),
                         snap.get("key2_strike"), snap.get("key2_abs"), snap.get("key2_call_vol"), snap.get("key2_put_vol"), snap.get("flip")),
                    )
                day_fetched += 1
                _time_mod.sleep(0.5)  # rate-limit between slots
            except Exception as e:
                day_failed += 1
                failed.append({"date": f"{iso}@{ntime}", "error": str(e)[:80]})

        if day_fetched > 0:
            fetched.append(f"{iso}({day_fetched}/{len(missing_times)} slots)")
        if day_failed > 0 and day_fetched == 0:
            # All slots failed — count as a failed date
            pass  # already recorded per-slot above

    return {
        "fetched": fetched,
        "skipped": skipped,
        "failed": failed,
        "migration": migration,
    }


@app.route("/api/sync-historical")
def api_sync_historical():
    """Sync historical GEX data working backwards from yesterday."""
    symbol = request.args.get("symbol", "SPX")
    max_days = int(request.args.get("max_days", 30))
    result = sync_historical(symbol=symbol, max_days=max_days)
    # Retrain HMM after new historical data is added
    hmm_result = _train_hmm(force=True)
    result["hmm_retrain"] = hmm_result
    return jsonify(result)


@app.route("/api/spx-prices")
def api_spx_prices():
    """Return SPX price history from histgex files.

    Query params:
    - mode: 'eod' (default) or 'single'
    - date: ISO date (YYYY-MM-DD) for single mode
    """
    mode = request.args.get("mode", "eod")
    target_date = request.args.get("date")

    print(f"[DEBUG] api_spx_prices called: mode={mode}, target_date={target_date}")

    prices = []

    if mode == "single" and target_date:
        # Single date mode: all times for that date
        ndate = int(target_date.replace("-", ""))
        with _db() as con:
            rows = con.execute(
                "SELECT ntime, uprice FROM snapshot WHERE ndate=? AND symbol='SPX' ORDER BY ntime",
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
                "SELECT ndate, MAX(ntime) as ntime, uprice FROM snapshot "
                "WHERE symbol='SPX' GROUP BY ndate ORDER BY ndate"
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

    print(f"[DEBUG] Returning {len(prices)} prices")
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
    if data["ntime"] >= 930:
        with _db() as _hcon:
            prior_rows = _hcon.execute(
                "SELECT uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
                "FROM snapshot WHERE ndate=? AND ntime>=930 AND source='gex' ORDER BY ntime",
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

    # Ratio flips sign based on which side is larger
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum = abs(sum(put_gex))
    if total_call_gex_sum > total_put_gex_sum:
        gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
    else:
        gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0
    net_g = sum(net_gex)

    snap["sentiment_pct"] = sentiment_pct
    snap["gex_ratio"] = gex_ratio
    snap["net_gex"] = net_g
    snap["total_call_oi"] = int(total_call_oi)
    snap["total_put_oi"] = int(total_put_oi)
    snap["total_call_vol"] = int(total_call_vol)
    snap["total_put_vol"] = int(total_put_vol)

    # HMM regime prediction — use full day's sequence for context (proper Viterbi)
    # Only for RTH (ntime >= 930) — pre-market data is outside training distribution
    hmm = {}
    if data["ntime"] >= 930:
        with _db() as _hcon:
            prior_rows = _hcon.execute(
                "SELECT uprice, net_gex, kcs, sentiment, key_strike, total_put_vol "
                "FROM snapshot WHERE ndate=? AND ntime>=930 ORDER BY ntime",
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
            (ndate, ntime, uprice, json.dumps(rows), 1 if ntime < 930 else 0),
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
    # Ratio flips sign based on which side is larger
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum = abs(sum(put_gex))
    if total_call_gex_sum > total_put_gex_sum:
        gex_ratio = round(total_call_gex_sum / total_put_gex_sum, 1) if total_put_gex_sum else 0
    else:
        gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0
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
    """Verify data integrity across the unified snapshot table.
    
    Checks:
    1. Source field is 'gex' or 'histgex'
    2. Raw JSON presence (excludes known-missing gex snapshots from dates 20260622-20260626)
    3. Deep verification: recalculate from raw data and compare to persisted values
    
    Returns dict with verification results.
    """
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_snapshots": 0,
        "source_errors": [],
        "raw_json_errors": [],
        "calculation_errors": [],
        "known_missing_json": 0,
        "summary": {}
    }
    
    # Known-missing JSON: source='gex' snapshots from 20260622-20260626
    known_missing_dates = [20260622, 20260623, 20260624, 20260625, 20260626]
    
    with _db() as con:
        # Get all SPX snapshots from snapshot table
        cursor = con.execute('''
            SELECT ndate, ntime, symbol, source, raw_json, uprice,
                   net_gex, total_call_gex, total_put_gex, sentiment, gex_ratio,
                   kcs, key_strike, key_call_gex, key_put_gex
            FROM snapshot 
            WHERE symbol='SPX'
            ORDER BY ndate, ntime
        ''')
        rows = cursor.fetchall()
        results["total_snapshots"] = len(rows)
        
        for row in rows:
            (ndate, ntime, symbol, source, raw_json, uprice,
             db_net_gex, db_total_call_gex, db_total_put_gex, db_sentiment, db_gex_ratio,
             db_kcs, db_key_strike, db_key_call_gex, db_key_put_gex) = row
            
            # Check 1: Source field
            if source not in ['gex', 'histgex']:
                results["source_errors"].append({
                    "ndate": ndate,
                    "ntime": ntime,
                    "error": f"Invalid source: {source}"
                })
            
            # Check 2: Raw JSON (exclude known-missing gex snapshots)
            if raw_json is None:
                if source == 'gex' and ndate in known_missing_dates:
                    results["known_missing_json"] += 1
                else:
                    results["raw_json_errors"].append({
                        "ndate": ndate,
                        "ntime": ntime,
                        "source": source,
                        "error": "Missing raw_json"
                    })
            
            # Check 3: Deep verification (recalculate from raw data)
            # Skip for known-missing dates (20260622-20260626) which have API errors in raw_json
            if raw_json is not None and ndate not in known_missing_dates:
                try:
                    raw_data = json.loads(raw_json)
                    # If raw_data is a list, wrap with uprice so windowing works correctly
                    if isinstance(raw_data, list):
                        raw_data = {"data": raw_data, "uprice": uprice or 0}
                    elif isinstance(raw_data, dict) and "uprice" not in raw_data:
                        raw_data["uprice"] = uprice or 0
                    recalculated = _compute_flat_summary(raw_data)
                    
                    # Compare key fields (allow small floating point differences)
                    tolerance = 0.01
                    
                    if abs(recalculated.get("net_gex", 0) - db_net_gex) > tolerance:
                        results["calculation_errors"].append({
                            "ndate": ndate,
                            "ntime": ntime,
                            "field": "net_gex",
                            "db_value": db_net_gex,
                            "calc_value": recalculated.get("net_gex", 0)
                        })
                    
                    if abs(recalculated.get("total_call_gex", 0) - db_total_call_gex) > tolerance:
                        results["calculation_errors"].append({
                            "ndate": ndate,
                            "ntime": ntime,
                            "field": "total_call_gex",
                            "db_value": db_total_call_gex,
                            "calc_value": recalculated.get("total_call_gex", 0)
                        })
                    
                    if abs(recalculated.get("total_put_gex", 0) - db_total_put_gex) > tolerance:
                        results["calculation_errors"].append({
                            "ndate": ndate,
                            "ntime": ntime,
                            "field": "total_put_gex",
                            "db_value": db_total_put_gex,
                            "calc_value": recalculated.get("total_put_gex", 0)
                        })
                    
                    if abs(recalculated.get("gex_ratio", 0) - db_gex_ratio) > tolerance:
                        results["calculation_errors"].append({
                            "ndate": ndate,
                            "ntime": ntime,
                            "field": "gex_ratio",
                            "db_value": db_gex_ratio,
                            "calc_value": recalculated.get("gex_ratio", 0)
                        })
                    
                    if abs(recalculated.get("kcs", 0) - db_kcs) > tolerance:
                        results["calculation_errors"].append({
                            "ndate": ndate,
                            "ntime": ntime,
                            "field": "kcs",
                            "db_value": db_kcs,
                            "calc_value": recalculated.get("kcs", 0)
                        })
                    
                except Exception as e:
                    results["calculation_errors"].append({
                        "ndate": ndate,
                        "ntime": ntime,
                        "error": f"Recalculation failed: {str(e)[:100]}"
                    })
    
    # Summary
    results["summary"] = {
        "total_snapshots": results["total_snapshots"],
        "source_errors": len(results["source_errors"]),
        "raw_json_errors": len(results["raw_json_errors"]),
        "calculation_errors": len(results["calculation_errors"]),
        "known_missing_json": results["known_missing_json"],
        "valid_snapshots": results["total_snapshots"] - len(results["source_errors"]) - len(results["raw_json_errors"]) - len(results["calculation_errors"])
    }
    
    return results


if __name__ == "__main__":
    import argparse, webbrowser, threading

    # Run startup migrations and backfills only when the server is launched directly.
    _ensure_snapshot_table()
    # _migrate_to_snapshot()  # Already run manually
    _ensure_snapshot_table()
    _ensure_live_analysis_table()
    _ensure_spx_open_prices_table()
    _populate_spx_open_prices_from_csv()  # fill spx_open_prices from CSV (ignores existing)
    _ensure_snapshot_premarket()
    _ensure_snapshot_summary_columns()  # add flat summary columns to snapshot
    _drop_legacy_snapshots_table()  # remove legacy pre-SQLite table
    _ensure_hmm_tables()
    _ensure_metric_history_table()
    _backfill_snapshot_gex_ratio()  # recompute gex_ratio for snapshot with new formula
    _backfill_snapshot_nulls()  # set default values for null computed columns in snapshot
    _backfill_snapshot_nulls()  # set default values for null computed columns in snapshot
    _promote_live_to_historical()  # auto-promote prior-day live snapshots on every startup
    # _backfill_snapshot_summary(force=True)  # re-backfill all rows with corrected gex_ratio formula - DISABLED: run manually when calculation logic changes
    _HISTORY_CACHE.clear()  # clear cache after backfill to rebuild with new values
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
    print("Press Ctrl+C to stop.")
    app.run(port=PORT, debug=False)
