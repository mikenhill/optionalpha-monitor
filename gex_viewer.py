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
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR  = Path(__file__).resolve().parent
GEX_DIR   = BASE_DIR / "results" / "histgex"
SPX_FILES = [
    BASE_DIR / "spx-5min.csv",
    Path(r"g:\My Drive\Colab Notebooks\optionalpha_orb\spx-5min-20250201.csv"),
]
TIMES = [930, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555, 1600]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_spx() -> pd.DataFrame:
    frames = []
    for p in SPX_FILES:
        if p.exists():
            df = pd.read_csv(p)
            df.columns = [c.strip().strip('"') for c in df.columns]
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["dt"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%m/%d/%Y %H:%M")
    # CSV times are EST (UTC-5); market/GEX times are ET/EDT (UTC-4) — add 1 hour
    df["dt"] = df["dt"] + pd.Timedelta(hours=1)
    df = df.drop_duplicates("dt").sort_values("dt").reset_index(drop=True)
    df["date_iso"] = df["dt"].dt.strftime("%Y-%m-%d")
    df["time_str"] = df["dt"].dt.strftime("%H:%M")
    return df


def available_dates() -> list:
    dirs = sorted(GEX_DIR.glob("2*/"), key=lambda p: p.name)
    dates = []
    for d in dirs:
        name = d.name   # YYYYMMDD
        if len(name) == 8 and name.isdigit():
            iso = f"{name[:4]}-{name[4:6]}-{name[6:8]}"
            # Check if any snapshot for this date has valid GEX data
            has_valid_data = False
            for f in d.glob(f"{name}_*_SPX_histgex.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    gex_rows = data.get("data", [])
                    if gex_rows and len(gex_rows) > 0:
                        has_valid_data = True
                        break
                except:
                    continue
            if has_valid_data:
                dates.append(iso)
    return dates


def load_gex_snapshot(date_iso: str, ntime: int) -> dict | None:
    name   = date_iso.replace("-", "")
    path   = GEX_DIR / name / f"{name}_{ntime:04d}_SPX_histgex.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summarise_snapshot(data: dict) -> dict:
    rows   = data.get("data") or []
    uprice = data.get("uprice", 0)
    if not rows:
        return {"uprice": uprice}

    valid = [r for r in rows if r.get("strike") is not None]

    # 40-strike window: 20 strikes below + 20 strikes above underlying price
    below = [r for r in valid if r["strike"] < uprice]
    above = [r for r in valid if r["strike"] >= uprice]
    window_rows = below[-20:] + above[:20]
    if not window_rows:
        return {"uprice": uprice}

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

    snap = {
        "uprice": uprice, "net_gex": net, "call_gex": cg, "put_gex": pg,
        "total_abs": total_abs, "wall": wall, "wall2": wall2, "flip": flip,
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


def compare_thesis_with_actuals(date_iso: str, thesis: dict, spx_df: pd.DataFrame) -> dict:
    """Compare historical thesis with actual OHLC from SPX CSV and generate verdict.
    
    Historical analysis uses ONLY the SPX CSV — not the daily summary CSV or analysis files.
    """
    day_rows = spx_df[spx_df["date_iso"] == date_iso]
    if day_rows.empty:
        return {"error": "No SPX data for this date"}
    open_price = day_rows["Open"].iloc[0]
    high_price = day_rows["High"].max()
    low_price = day_rows["Low"].min()
    close_price = day_rows["Close"].iloc[-1]

    return _build_verdict(thesis, open_price, high_price, low_price, close_price)


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

    # Fallback to SPX CSV
    return compare_thesis_with_actuals(date_iso, thesis, SPX_DF)


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

    comparison = compare_thesis_with_actuals(date_iso, thesis, SPX_DF)
    if "error" in comparison:
        return comparison

    return {
        "date": date_iso,
        "thesis": thesis,
        "actuals": comparison["ohlc"],
        "verdict": comparison["verdict"],
    }


def generate_live_analysis(date_iso: str) -> dict:
    """Generate live/current-day analysis from the daily summary CSV."""
    thesis = generate_thesis_from_daily_summary(date_iso)
    if "error" in thesis:
        return thesis

    comparison = compare_thesis_with_daily_summary_actuals(date_iso, thesis)
    if "error" in comparison:
        return comparison

    return {
        "date": date_iso,
        "thesis": thesis,
        "actuals": comparison["ohlc"],
        "verdict": comparison["verdict"],
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
_HISTORY_CACHE: dict = {}  # {ntime: {metric: [values in date order], "dates": [...]}}
_STATS_CACHE_METRICS = ["net_gex", "call_gex", "put_gex", "call_oi", "put_oi", "call_vol", "put_vol", "kcs", "dominance"]


def _snapshot_computed_stats(date_iso: str, ntime: int) -> dict | None:
    """Load a histgex snapshot and compute the same 40-strike window stats as the API."""
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
    call_gex = [r.get("cg", 0) or 0 for r in rows]
    put_gex  = [r.get("pg", 0) or 0 for r in rows]
    net_gex  = [r.get("net", 0) or 0 for r in rows]
    ks = _compute_key_strike_stats(rows, uprice)
    return {
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

SPX_DF = load_spx()


@app.route("/")
def index():
    from time import time
    return render_template("gex_viewer.html", cache_bust=int(time()))


@app.route("/api/dates")
def api_dates():
    return jsonify(available_dates())


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

        # Ratio = total_put_gex / total_call_gex
        total_call_gex_sum = sum(call_gex)
        total_put_gex_sum = abs(sum(put_gex))
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
    date_iso = request.args.get("date")
    ntime    = int(request.args.get("time", 930))
    prev_t   = request.args.get("prev_time")

    data = load_gex_snapshot(date_iso, ntime)
    if data is None:
        return jsonify({"error": "No GEX data for this date/time"}), 404

    snap = summarise_snapshot(data)
    prev_snap = None
    if prev_t:
        prev_data = load_gex_snapshot(date_iso, int(prev_t))
        if prev_data:
            prev_snap = summarise_snapshot(prev_data)

    # Strike data — use OptionAlpha method: 20 strikes below + 20 above underlying
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

    # Cumulative net GEX from left to right (used for area overlay)
    cumulative_gex = []
    running = 0.0
    for v in net_gex:
        running += v
        cumulative_gex.append(round(running, 2))

    # Summary stats — computed from the 40-strike window only (matches OptionAlpha)
    total_call_oi  = sum(r.get("coi", 0) or 0 for r in rows)
    total_put_oi   = sum(r.get("poi", 0) or 0 for r in rows)
    total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
    total_put_vol  = sum(r.get("pvol", 0) or 0 for r in rows)

    # Sentiment = % of positive net GEX bars within the 40 strikes
    pos_bars = sum(1 for n in net_gex if n > 0)
    sentiment_pct = round(pos_bars / len(net_gex) * 100) if net_gex else 50

    # Ratio = total_put_gex / total_call_gex (matches OptionAlpha display)
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum  = abs(sum(put_gex))
    gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0

    # Net GEX = sum of all net within the window
    net_g = sum(net_gex)

    snap["sentiment_pct"]  = sentiment_pct
    snap["gex_ratio"]      = gex_ratio
    snap["net_gex"]        = net_g
    snap["total_call_oi"]  = int(total_call_oi)
    snap["total_put_oi"]   = int(total_put_oi)
    snap["total_call_vol"] = int(total_call_vol)
    snap["total_put_vol"]  = int(total_put_vol)
    snap.update(_compute_key_strike_stats(rows, uprice))

    # SPX price data up to current time
    time_cutoff = f"{ntime:04d}"
    hh = int(time_cutoff[:2])
    mm = int(time_cutoff[2:])
    cutoff_str = f"{hh:02d}:{mm:02d}"

    spx_bars = []
    if not SPX_DF.empty:
        day_df = SPX_DF[SPX_DF["date_iso"] == date_iso].copy()
        day_df = day_df[day_df["time_str"] >= "09:30"]
        day_df = day_df[day_df["time_str"] <= cutoff_str]
        spx_bars = day_df[["time_str", "Open", "High", "Low", "Close"]].to_dict("records")

    points = teaching_points(snap, prev_snap, spx_bars)

    # Day classification (only computed once per date change)
    day_type = classify_gex_day(date_iso, SPX_DF)

    return jsonify({
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
    })


@app.route("/api/snapshots")
def api_snapshots():
    """Return all available snapshot times for a given date."""
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"times": []})

    ymd = date_iso.replace("-", "")
    date_dir = GEX_DIR / ymd
    times = []
    if date_dir.exists():
        for f in date_dir.glob(f"{ymd}_*_SPX_histgex.json"):
            try:
                ntime = int(f.stem.split("_")[1])
                if ntime in TIMES:
                    times.append(ntime)
            except:
                continue
    times.sort()
    return jsonify({"times": times})


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

    net_gex:   bearish_pct = 100 - pct_rank  (higher = more bearish than historical)
    call_gex, put_gex, call_oi, put_oi, call_vol, put_vol:
               size_pct = pct_rank  (higher = larger than more historical readings)
    """
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 1000))
    if not date_iso:
        return jsonify({"error": "date required"}), 400

    stats = _snapshot_computed_stats(date_iso, ntime)
    is_live = False
    if not stats:
        # Try live snapshot if not found in historical data
        name = date_iso.replace("-", "")
        live_path = LIVE_DIR / name / f"{name}_{ntime:04d}_SPX_livegex.json"
        if live_path.exists():
            live_data = json.loads(live_path.read_text(encoding="utf-8"))
            uprice = live_data.get("uprice", 0)
            all_rows = sorted(
                [r for r in (live_data.get("data") or []) if r.get("strike") is not None],
                key=lambda r: r["strike"]
            )
            below = [r for r in all_rows if r["strike"] < uprice]
            above = [r for r in all_rows if r["strike"] >= uprice]
            rows = below[-20:] + above[:20]
            if not rows:
                return jsonify({"error": "No valid rows in live snapshot"}), 404
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
        for t in TIMES:
            temp_cache = get_stats_cache(t)
            size = len(temp_cache.get("net_gex", []))
            if size > best_size:
                best_size = size
                best_ntime = t
        cache_ntime = best_ntime
    else:
        cache_ntime = ntime

    cache = get_stats_cache(cache_ntime)
    n = len(cache.get("net_gex", []))

    net_pct_raw = pct_rank(stats["net_gex"], cache["net_gex"])
    # bearish_pct: how much more bearish this reading is vs history
    bearish_pct = 100 - net_pct_raw

    def size_entry(key):
        pct = pct_rank(stats[key], cache[key])
        return {"value": stats[key], "pct": pct}

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
        "kcs": {
            "value": stats["kcs"],
            "pct":   pct_rank(stats["kcs"], cache["kcs"]),
        },
        "dominance": {
            "value": stats["dominance"],
            "pct":   pct_rank(stats["dominance"], cache["dominance"]),
        },
    })


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


def sync_historical(symbol: str = "SPX", max_days: int = 30) -> dict:
    """Fetch missing historical GEX data working backwards from yesterday.

    Returns dict with fetched, skipped, and failed counts with details.
    """
    from datetime import date, timedelta
    from optionalpha_client import fetch_market_data
    from process_gex_window import summarize_file, write_summary_files

    yesterday = date.today() - timedelta(days=1)
    existing = set(available_dates())
    fetched = []
    skipped = []
    failed = []

    for i in range(max_days):
        d = yesterday - timedelta(days=i)
        iso = d.isoformat()
        ymd = d.strftime("%Y%m%d")

        if iso in existing:
            skipped.append(iso)
            continue

        try:
            xid = f"{symbol}_{ymd}"
            data = fetch_market_data(symbol=symbol, xid=xid)

            # Save in histgex format (same as histgex snapshots)
            hist_dir = GEX_DIR / ymd
            hist_dir.mkdir(parents=True, exist_ok=True)

            # Use 1530 (3:30pm ET) as the snapshot time for historical daily data
            snapshot_file = hist_dir / f"{ymd}_1530_SPX_histgex.json"
            snapshot = {
                "uprice": data[0].get("data", {}).get("uprice", 0) if data else 0,
                "data": data[0].get("data", {}).get("gex", []) if data else [],
            }
            snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

            # Also save the raw capture for daily summary
            output_file = BASE_DIR / "results" / f"{ymd}_1530_{symbol}_{xid}.json"
            output = {
                "captured_at": d.isoformat(),
                "symbol": symbol,
                "xid": xid,
                "data": data,
            }
            output_file.write_text(json.dumps(output, indent=2), encoding="utf-8")

            # Generate summary and append to daily summary CSV
            summary = summarize_file(output_file)
            summary_file, csv_file = write_summary_files(
                output_file,
                summary,
                include_csv=True,
                append_path=BASE_DIR / "results" / "daily_gex_summary.csv",
            )

            fetched.append(iso)
        except Exception as e:
            failed.append({"date": iso, "error": str(e)[:100]})  # Truncate long errors

    return {"fetched": fetched, "skipped": skipped, "failed": failed}


@app.route("/api/sync-historical")
def api_sync_historical():
    """Sync historical GEX data working backwards from yesterday."""
    symbol = request.args.get("symbol", "SPX")
    max_days = int(request.args.get("max_days", 30))
    result = sync_historical(symbol=symbol, max_days=max_days)
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
        ymd = target_date.replace("-", "")
        date_dir = GEX_DIR / ymd
        print(f"[DEBUG] Single date mode: ymd={ymd}, date_dir={date_dir}, exists={date_dir.exists()}")
        if date_dir.exists():
            for f in sorted(date_dir.glob(f"{ymd}_*_SPX_histgex.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    ntime = data.get("ntime", 0)
                    uprice = data.get("uprice", 0)
                    if uprice:
                        prices.append({
                            "date": target_date,
                            "time": f"{ntime // 100:02d}:{ntime % 100:02d}",
                            "uprice": uprice
                        })
                except:
                    continue
    else:
        # EOD mode: latest time per day
        dates = available_dates()
        print(f"[DEBUG] EOD mode: available_dates={len(dates)} dates")
        for date_iso in dates:
            ymd = date_iso.replace("-", "")
            date_dir = GEX_DIR / ymd
            if not date_dir.exists():
                continue

            # Find the latest time for this date
            latest_file = None
            latest_time = 0
            for f in date_dir.glob(f"{ymd}_*_SPX_histgex.json"):
                try:
                    ntime = int(f.stem.split("_")[1])
                    if ntime > latest_time:
                        latest_time = ntime
                        latest_file = f
                except:
                    continue

            if latest_file:
                try:
                    data = json.loads(latest_file.read_text(encoding="utf-8"))
                    uprice = data.get("uprice", 0)
                    if uprice:
                        prices.append({
                            "date": date_iso,
                            "time": f"{latest_time // 100:02d}:{latest_time % 100:02d}",
                            "uprice": uprice
                        })
                except:
                    continue

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
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum  = abs(sum(put_gex))
    gex_ratio = round(-total_put_gex_sum / total_call_gex_sum, 1) if total_call_gex_sum else 0
    net_g = sum(net_gex)

    snap["sentiment_pct"] = sentiment_pct
    snap["gex_ratio"] = gex_ratio
    snap["net_gex"] = net_g
    snap["total_call_oi"] = int(total_call_oi)
    snap["total_put_oi"] = int(total_put_oi)
    snap["total_call_vol"] = int(total_call_vol)
    snap["total_put_vol"] = int(total_put_vol)

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
    })


@app.route("/api/live/analysis")
def api_live_analysis():
    """Return live/current-day analysis based on the latest daily summary row."""
    et_now = get_et_now()
    date_iso = et_now.strftime("%Y-%m-%d")
    analysis = generate_live_analysis(date_iso)
    if "error" in analysis:
        return jsonify(analysis), 404
    return jsonify(analysis)


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


def save_live_snapshot(data: dict) -> Path:
    """Save a live snapshot to the livegex folder."""
    ndate = data["ndate"]
    ntime = data["ntime"]
    day_dir = LIVE_DIR / str(ndate)
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{ndate}_{ntime:04d}_SPX_livegex.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_live_snapshots(date_iso: str) -> list:
    """Load all live snapshots for a given date, sorted by time."""
    name = date_iso.replace("-", "")
    day_dir = LIVE_DIR / name
    if not day_dir.exists():
        return []
    files = sorted(day_dir.glob(f"{name}_*_SPX_livegex.json"))
    snapshots = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            snapshots.append(d)
        except Exception:
            continue
    return snapshots


def live_dates() -> list:
    """Return list of dates that have live snapshots."""
    dirs = sorted(LIVE_DIR.glob("2*/"), key=lambda p: p.name)
    dates = []
    for d in dirs:
        name = d.name
        if len(name) == 8 and name.isdigit():
            iso = f"{name[:4]}-{name[4:6]}-{name[6:8]}"
            dates.append(iso)
    return dates


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


@app.route("/api/live/snapshot")
def api_live_snapshot():
    """Return a specific live snapshot by date and time."""
    date_iso = request.args.get("date")
    ntime = int(request.args.get("time", 0))
    if not date_iso:
        et_now = get_et_now()
        date_iso = et_now.strftime("%Y-%m-%d")

    name = date_iso.replace("-", "")
    path = LIVE_DIR / name / f"{name}_{ntime:04d}_SPX_livegex.json"
    if not path.exists():
        return jsonify({"error": "Snapshot not found"}), 404

    data = json.loads(path.read_text(encoding="utf-8"))
    snap = summarise_snapshot(data)

    uprice = snap.get("uprice", 0)
    all_rows = sorted(
        [r for r in (data.get("data") or []) if r.get("strike") is not None],
        key=lambda r: r["strike"]
    )
    below = [r for r in all_rows if r["strike"] < uprice]
    above = [r for r in all_rows if r["strike"] >= uprice]
    rows = below[-20:] + above[:20]

    strikes  = [r["strike"] for r in rows]
    call_gex = [r.get("cg", 0) or 0 for r in rows]
    put_gex  = [r.get("pg", 0) or 0 for r in rows]
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
    total_call_gex_sum = sum(call_gex)
    total_put_gex_sum  = abs(sum(put_gex))
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

if __name__ == "__main__":
    import argparse, webbrowser, threading
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
