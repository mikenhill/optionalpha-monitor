"""
optionalpha_daily-summary.py

Produces a concise CSV (daily_gex_summary-concise.csv) from existing captured
JSON result files. Includes the core actionable metrics plus all optional fields
recommended from the transcript analysis.

Usage:
    python optionalpha_daily-summary.py                        # all found JSON files
    python optionalpha_daily-summary.py --dates 20260603 20260604 20260605
    python optionalpha_daily-summary.py --file results/20260605_141640_SPX_SPX_20260605.json
"""

import argparse
import csv
import re
import os
from pathlib import Path
from typing import Optional

try:
    import requests as _requests
except ImportError:
    _requests = None

from market_data import backfill_ohlc, fetch_spx_ohlc
from process_gex_window import summarize_file

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
CONCISE_CSV = RESULTS_DIR / "daily_gex_summary-concise.csv"
DAILY_SUMMARY_CSV = RESULTS_DIR / "daily_gex_summary.csv"

# Ordered list of fields for the concise output.
# Groups: identity | price | key strike core | key strike detail | optional | bias | spreads | ohlc
CONCISE_FIELDS = [
    # Identity
    "symbol",
    "date",
    # Price
    "last",
    # Overall bias
    "sentiment",
    "gex_ratio",
    "net_gex",
    # Key strike core
    "key_strike",
    "key_absolute",
    "key_net",
    "key_dominance_pct",
    # Key strike call/put breakdown
    "key_call_gex",
    "key_put_gex",
    # Key strike OI & volume
    "key_call_oi",
    "key_put_oi",
    "key_net_oi",
    "key_call_vol",
    "key_put_vol",
    "key_vol_net",
    # Second strike
    "key2_strike",
    "key2_absolute",
    # OHLC (backfilled separately by optionalpha_daily.py)
    "ohlc_open",
    "ohlc_high",
    "ohlc_low",
    "ohlc_close",
]


def is_source_json(path: Path) -> bool:
    """Return True for raw capture files, excluding *_gex_summary.json and *_gex_window.json."""
    name = path.name
    return (
        path.suffix == ".json"
        and not name.endswith("_gex_summary.json")
        and not name.endswith("_gex_window.json")
    )


def date_prefix(path: Path) -> str:
    """Extract YYYYMMDD from filename like 20260605_141640_SPX_SPX_20260605.json."""
    m = re.match(r"^(\d{8})", path.name)
    return m.group(1) if m else ""


def find_source_jsons(dates: list[str] | None = None) -> list[Path]:
    candidates = sorted(
        (p for p in RESULTS_DIR.glob("*.json") if is_source_json(p)),
        key=lambda p: p.name,
    )
    if dates:
        candidates = [p for p in candidates if date_prefix(p) in dates]
    return candidates


def pick_one_per_day(paths: list[Path]) -> list[Path]:
    """For each calendar day keep only the latest file (largest timestamp)."""
    by_day: dict[str, Path] = {}
    for p in paths:
        day = date_prefix(p)
        if day not in by_day or p.name > by_day[day].name:
            by_day[day] = p
    return sorted(by_day.values(), key=lambda p: p.name)


BILLION_FIELDS = {
    "net_gex",
    "key_absolute",
    "key_net",
    "key_call_gex",
    "key_put_gex",
    "key2_absolute",
}

# Maps concise output field name -> source field name in process_gex_window summary.
# Fields not listed here are fetched using the same name as in the summary dict.
SOURCE_FIELD = {
    "key_strike":      "highest_absolute_gex_strike",
    "key_absolute":    "highest_absolute_gex_absolute_gex",
    "key_net":         "highest_absolute_gex_net_gex",
    "key_dominance_pct": "key_strike_dominance_pct",
    "key_call_gex":    "highest_absolute_gex_calls_gex",
    "key_put_gex":     "highest_absolute_gex_puts_gex",
    "key_call_oi":     "highest_absolute_gex_oi_call",
    "key_put_oi":      "highest_absolute_gex_oi_put",
    "key_call_vol":    "highest_absolute_gex_call_vol",
    "key_put_vol":     "highest_absolute_gex_put_vol",
    "key2_strike":     "second_highest_gex_strike",
    "key2_absolute":   "second_highest_gex_absolute",
}

# Fields whose value is computed as (source_a - source_b) rather than fetched directly
NET_DIFF_FIELD = {
    "key_net_oi":  ("highest_absolute_gex_oi_call",  "highest_absolute_gex_oi_put"),
    "key_vol_net": ("highest_absolute_gex_call_vol", "highest_absolute_gex_put_vol"),
}


# ---------------------------------------------------------------------------
# Setup classification
# ---------------------------------------------------------------------------

# Setup codes and their human-readable labels.
SETUP_LABELS = {
    "PIN":          "GEX Pin / Magnet",
    "PUT_PILLAR":   "Put Pillar / Support",
    "CALL_WALL":    "Call Wall / Resistance",
    "NEG_GAMMA":    "Negative Gamma Acceleration",
    "LOW_CONV":     "Low Conviction / No Clear Setup",
    "NO_SETUP":     "No Clear Setup",
}


def classify_setup(row: dict, summary: dict) -> str:
    """Classify today's GEX profile into one of the setup codes.

    Uses the concise row (formatted strings) and the raw summary dict.
    Returns a SETUP code string.
    """
    def raw(key):
        """Get a raw float from the summary dict, returning 0.0 on failure."""
        try:
            return float(summary.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    key_abs     = raw("highest_absolute_gex_absolute_gex")
    key_net     = raw("highest_absolute_gex_net_gex")
    key_call    = raw("highest_absolute_gex_calls_gex")
    key_put     = raw("highest_absolute_gex_puts_gex")   # negative value
    key2_abs    = raw("second_highest_gex_absolute")
    net_gex     = raw("net_gex")
    key_net_oi  = raw("highest_absolute_gex_oi_call") - raw("highest_absolute_gex_oi_put")
    key_vol_net = raw("highest_absolute_gex_call_vol") - raw("highest_absolute_gex_put_vol")
    dominance   = raw("key_strike_dominance_pct")

    # Low conviction: key_absolute is tiny (< 1.5B) — unreliable signal
    LOW_CONV_THRESHOLD = 1_500_000_000
    if key_abs < LOW_CONV_THRESHOLD:
        return "LOW_CONV"

    # Two-strike tie qualifier: key2 within 20% of key weakens single-strike setups
    two_strike_tie = key2_abs > 0 and (key2_abs / key_abs) >= 0.80

    # Call/put balance at key strike: positive = call-heavy, negative = put-heavy
    total_abs_at_key = abs(key_call) + abs(key_put)
    call_put_balance = (abs(key_call) - abs(key_put)) / total_abs_at_key if total_abs_at_key else 0

    # PIN: both sides large and balanced (balance within ±25%), key is dominant outlier
    if abs(call_put_balance) <= 0.25 and not two_strike_tie:
        return "PIN"

    # PIN (weak): balanced but two-strike tie — still classify as PIN, caller can note qualifier
    if abs(call_put_balance) <= 0.25 and two_strike_tie:
        return "PIN"

    # PUT PILLAR: put side strongly dominant (balance < -0.35) and put OI dominant
    if call_put_balance < -0.35 and key_net_oi < -100:
        return "PUT_PILLAR"

    # CALL WALL: call side strongly dominant (balance > 0.35) and call OI dominant
    if call_put_balance > 0.35 and key_net_oi > 100:
        return "CALL_WALL"

    # NEGATIVE GAMMA: net_gex strongly negative (< -5B) even if key strike is ambiguous
    if net_gex < -5_000_000_000:
        return "NEG_GAMMA"

    return "NO_SETUP"


# ---------------------------------------------------------------------------
# Webhook firing
# ---------------------------------------------------------------------------

# Map setup codes to environment variable names holding the webhook URL.
# Set these in your environment or a .env file before running with --webhooks.
WEBHOOK_ENV = {
    "PIN":        "OA_WEBHOOK_PIN",
    "PUT_PILLAR": "OA_WEBHOOK_PUT_PILLAR",
    "CALL_WALL":  "OA_WEBHOOK_CALL_WALL",
    "NEG_GAMMA":  "OA_WEBHOOK_NEG_GAMMA",
    "LOW_CONV":   "OA_WEBHOOK_LOW_CONV",
    "NO_SETUP":   "OA_WEBHOOK_NO_SETUP",
}


def fire_webhook(setup: str, row: dict, dry_run: bool = False) -> None:
    """Fire the Option Alpha webhook for the given setup code.

    The URL is read from an environment variable (see WEBHOOK_ENV).
    Pass dry_run=True to print the URL without making the HTTP call.
    """
    env_var = WEBHOOK_ENV.get(setup)
    if not env_var:
        print(f"  [webhook] No env var mapping for setup '{setup}' — skipping.")
        return

    url = os.environ.get(env_var, "").strip()
    if not url:
        print(f"  [webhook] {env_var} not set — skipping webhook for setup '{setup}'.")
        return

    label = SETUP_LABELS.get(setup, setup)
    if dry_run:
        print(f"  [webhook DRY-RUN] Would POST to {env_var}: {url}")
        print(f"    Setup: {setup} ({label})  key_strike={row.get('key_strike')}  key_absolute={row.get('key_absolute')}")
        return

    if _requests is None:
        print("  [webhook] 'requests' library not installed — cannot fire webhook.")
        return

    try:
        resp = _requests.get(url, timeout=10)
        print(f"  [webhook] {setup} ({label}) -> HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [webhook] ERROR firing {setup}: {exc}")


def fmt_billion(value) -> str:
    """Format a raw GEX value as xB with 2 decimal places (sign preserved)."""
    if value == "" or value is None:
        return ""
    try:
        f = float(value)
    except (ValueError, TypeError):
        return str(value)
    return f"{f / 1_000_000_000:.2f}B"


def fmt_2dp(value) -> str:
    """Round to 2 decimal places."""
    if value == "" or value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return str(value)


def to_concise(summary: dict) -> dict:
    row = {}
    for field in CONCISE_FIELDS:
        if field in NET_DIFF_FIELD:
            src_a, src_b = NET_DIFF_FIELD[field]
            a = summary.get(src_a) or 0
            b = summary.get(src_b) or 0
            row[field] = a - b
        else:
            src = SOURCE_FIELD.get(field, field)
            raw = summary.get(src, "")
            if field in BILLION_FIELDS:
                row[field] = fmt_billion(raw)
            elif field == "gex_ratio":
                row[field] = fmt_2dp(raw)
            else:
                row[field] = raw
    return row


OHLC_FIELDS = ("ohlc_open", "ohlc_high", "ohlc_low", "ohlc_close")


def load_ohlc_from_daily_csv() -> dict:
    """Return {date_str: {ohlc_open:..., ohlc_high:..., ohlc_low:..., ohlc_close:...}}
    from daily_gex_summary.csv, skipping rows where all four values are empty."""
    ohlc_by_date = {}
    if not DAILY_SUMMARY_CSV.exists():
        return ohlc_by_date
    with DAILY_SUMMARY_CSV.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            date_str = row.get("date", "")[:10]
            if all(row.get(k) not in ("", "0", "0.0", None) for k in OHLC_FIELDS):
                ohlc_by_date[date_str] = {k: row.get(k, "") for k in OHLC_FIELDS}
    return ohlc_by_date


def merge_ohlc(rows: list[dict], output_path: Path) -> list[dict]:
    """Merge OHLC into rows: first from daily_gex_summary.csv, then fetch missing from Yahoo."""
    from datetime import date as _date
    ohlc_by_date = load_ohlc_from_daily_csv()
    today_str = _date.today().isoformat()
    for row in rows:
        date_str = str(row.get("date", ""))[:10]
        if ohlc_by_date.get(date_str):
            row.update(ohlc_by_date[date_str])
        elif date_str and date_str < today_str:
            d = _date.fromisoformat(date_str)
            ohlc = fetch_spx_ohlc(d)
            if ohlc:
                row.update(ohlc)
                backfill_ohlc(DAILY_SUMMARY_CSV, date_str, ohlc)
                print(f"  Fetched OHLC for {date_str}: {ohlc}")
    return rows


def write_concise_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONCISE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

SETUP_COLOURS = {
    "PIN":        "#29B6F6",   # bright sky blue
    "PUT_PILLAR": "#66BB6A",   # bright green
    "CALL_WALL":  "#FF7043",   # bright deep orange
    "NEG_GAMMA":  "#CE93D8",   # bright lavender
    "LOW_CONV":   "#B0BEC5",   # light blue-grey
    "NO_SETUP":   "#B0BEC5",   # light blue-grey
}


def _safe_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_billion(v, default=None):
    """Parse '7.65B' or raw float string -> float in billions."""
    if v is None or v == "":
        return default
    s = str(v).strip().upper().rstrip("B")
    try:
        return float(s)
    except ValueError:
        return default


def _derive_setup(row: dict) -> str:
    """Re-derive setup code from concise row values (setup column absent from CSV)."""
    kabs    = _parse_billion(row.get("key_absolute"), 0)
    kcall_g = _parse_billion(row.get("key_call_gex"), 0)
    kput_g  = _parse_billion(row.get("key_put_gex"), 0)
    ngex    = _parse_billion(row.get("net_gex"), 0)
    knet_oi = _safe_float(row.get("key_net_oi"), 0)
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


def generate_dashboard(rows: list[dict], output_path: Path) -> None:
    """Generate a clean two-chart HTML dashboard from concise CSV rows."""
    import json as _json

    if not rows:
        return

    # ---- parse all rows ----------------------------------------------------
    dates, lasts, sentiments, net_gexs = [], [], [], []
    key_strikes, key2_strikes, setups  = [], [], []
    hovers = []

    for row in rows:
        date_s = str(row.get("date", ""))[:10]
        last   = _safe_float(row.get("last"))
        senti  = _safe_float(row.get("sentiment"))
        ngex   = _parse_billion(row.get("net_gex"))
        kstr   = _safe_float(row.get("key_strike"))
        k2str  = _safe_float(row.get("key2_strike"))
        kabs   = _parse_billion(row.get("key_absolute"))
        kdom   = _safe_float(row.get("key_dominance_pct"))
        setup  = _derive_setup(row)

        dates.append(date_s)
        lasts.append(last)
        sentiments.append(senti)
        net_gexs.append(ngex)
        key_strikes.append(kstr)
        key2_strikes.append(k2str)
        setups.append(setup)

        gap = ""
        if last is not None and kstr is not None:
            diff = kstr - last
            gap = f"Key vs Price: {diff:+.0f} pts<br>"
        net_gex_str = f"{ngex:+.2f}B" if ngex is not None else "n/a"
        kabs_str    = f"{kabs:.2f}B"  if kabs  is not None else "n/a"
        hovers.append(
            f"<b>{date_s}</b><br>"
            f"Setup: <b>{SETUP_LABELS.get(setup, setup)}</b><br>"
            f"SPX Last: {last}<br>"
            f"Net GEX: {net_gex_str}<br>"
            f"Sentiment: {senti}%<br>"
            f"Key Strike: {kstr}  Key2: {k2str}<br>"
            f"{gap}"
            f"Key Abs GEX: {kabs_str}  Dom: {kdom}%"
        )

    n        = len(rows)
    today_i  = n - 1   # latest row is "today"
    colours  = [SETUP_COLOURS.get(s, "#9E9E9E") for s in setups]

    # ========================================================================
    # CHART 1 — Regime scatter: Net GEX (x) vs Sentiment (y)
    # Historical dots (all but latest) + one highlighted dot for today
    # ========================================================================
    hist_x = net_gexs[:today_i]
    hist_y = sentiments[:today_i]
    hist_c = colours[:today_i]
    hist_h = hovers[:today_i]
    hist_d = dates[:today_i]

    scatter_hist = {
        "type": "scatter", "mode": "markers+text",
        "name": "Prior days",
        "x": hist_x, "y": hist_y,
        "text": hist_d, "textposition": "top center",
        "textfont": {"size": 9, "color": "#555555"},
        "hovertext": hist_h, "hovertemplate": "%{hovertext}<extra></extra>",
        "marker": {
            "color": hist_c, "size": 12, "opacity": 0.65,
            "line": {"width": 1, "color": "#555"},
        },
    }

    today_label = dates[today_i] + " ◀ TODAY"
    scatter_today = {
        "type": "scatter", "mode": "markers+text",
        "name": "Today",
        "x": [net_gexs[today_i]], "y": [sentiments[today_i]],
        "text": [today_label], "textposition": "top right",
        "textfont": {"size": 11, "color": "#ffffff"},
        "hovertext": [hovers[today_i]], "hovertemplate": "%{hovertext}<extra></extra>",
        "marker": {
            "color": colours[today_i], "size": 20, "opacity": 1.0,
            "symbol": "star",
            "line": {"width": 2, "color": "#ffffff"},
        },
    }

    # Quadrant reference lines and labels
    layout1 = {
        "title": {"text": "Regime map — Net GEX vs Sentiment  (hover for detail)", "font": {"size": 14}},
        "xaxis": {"title": "Net GEX (billions)", "zeroline": False, "gridcolor": "#e0e0e0"},
        "yaxis": {"title": "Sentiment %", "range": [0, 110], "zeroline": False, "gridcolor": "#e0e0e0"},
        "plot_bgcolor": "#ffffff",
        "paper_bgcolor": "#f5f5f5",
        "font": {"color": "#222222"},
        "showlegend": False,
        "height": 460,
        "shapes": [
            # vertical zero line
            {"type": "line", "x0": 0, "x1": 0, "y0": 0, "y1": 110,
             "line": {"color": "#aaaaaa", "width": 1, "dash": "dash"}},
            # horizontal neutral band 45–55%
            {"type": "rect",
             "x0": min((v for v in net_gexs if v is not None), default=-25),
             "x1": max((v for v in net_gexs if v is not None), default=25),
             "y0": 45, "y1": 55,
             "fillcolor": "#FFF9C4", "opacity": 0.6, "line": {"width": 0}},
        ],
        "annotations": [
            {"x": 0.02, "y": 0.98, "xref": "paper", "yref": "paper",
             "text": "POS GAMMA / HIGH SENTIMENT<br><i>stabilising, bullish lean</i>",
             "showarrow": False, "font": {"size": 9, "color": "#4CAF50"}, "align": "left"},
            {"x": 0.02, "y": 0.02, "xref": "paper", "yref": "paper",
             "text": "POS GAMMA / LOW SENTIMENT<br><i>mixed signal</i>",
             "showarrow": False, "font": {"size": 9, "color": "#9E9E9E"}, "align": "left"},
            {"x": 0.98, "y": 0.98, "xref": "paper", "yref": "paper",
             "text": "NEG GAMMA / HIGH SENTIMENT<br><i>mixed signal</i>",
             "showarrow": False, "font": {"size": 9, "color": "#9E9E9E"}, "align": "right"},
            {"x": 0.98, "y": 0.02, "xref": "paper", "yref": "paper",
             "text": "NEG GAMMA / LOW SENTIMENT<br><i>acceleration risk</i>",
             "showarrow": False, "font": {"size": 9, "color": "#9C27B0"}, "align": "right"},
        ],
        "margin": {"t": 50, "b": 50, "l": 60, "r": 20},
    }

    # ========================================================================
    # CHART 2 — Timeline: SPX price vs Key Strike
    # ========================================================================
    line_price = {
        "type": "scatter", "mode": "lines+markers",
        "name": "SPX Last",
        "x": dates, "y": lasts,
        "hovertext": hovers, "hovertemplate": "%{hovertext}<extra></extra>",
        "line": {"color": "#333333", "width": 2},
        "marker": {"color": colours, "size": 9, "line": {"width": 1, "color": "#333"}},
    }
    line_key = {
        "type": "scatter", "mode": "lines+markers",
        "name": "Key Strike",
        "x": dates, "y": key_strikes,
        "hovertext": hovers, "hovertemplate": "%{hovertext}<extra></extra>",
        "line": {"color": "#FF5722", "width": 2, "dash": "dot"},
        "marker": {"color": "#FF5722", "size": 7, "symbol": "diamond"},
    }
    # Highlight today on both lines
    highlight_price = {
        "type": "scatter", "mode": "markers",
        "name": "Today (price)",
        "x": [dates[today_i]], "y": [lasts[today_i]],
        "hovertext": [hovers[today_i]], "hovertemplate": "%{hovertext}<extra></extra>",
        "marker": {"color": "#ffffff", "size": 14, "symbol": "star",
                   "line": {"width": 2, "color": colours[today_i]}},
        "showlegend": False,
    }
    highlight_key = {
        "type": "scatter", "mode": "markers",
        "name": "Today (key)",
        "x": [dates[today_i]], "y": [key_strikes[today_i]],
        "hovertext": [hovers[today_i]], "hovertemplate": "%{hovertext}<extra></extra>",
        "marker": {"color": "#FF5722", "size": 14, "symbol": "star",
                   "line": {"width": 2, "color": "#ffffff"}},
        "showlegend": False,
    }

    layout2 = {
        "title": {"text": "SPX Price vs Key Strike over time  (colour = setup type)", "font": {"size": 14}},
        "xaxis": {"title": "Date", "gridcolor": "#e0e0e0"},
        "yaxis": {"title": "Level", "gridcolor": "#e0e0e0"},
        "plot_bgcolor": "#ffffff",
        "paper_bgcolor": "#f5f5f5",
        "font": {"color": "#222222"},
        "legend": {"orientation": "h", "y": -0.18, "font": {"size": 11}},
        "height": 380,
        "margin": {"t": 50, "b": 60, "l": 60, "r": 20},
        "annotations": [
            {"x": dates[today_i], "y": lasts[today_i],
             "text": "today", "showarrow": True, "arrowhead": 2,
             "arrowcolor": "#555", "font": {"size": 9, "color": "#555"},
             "ax": 20, "ay": -20},
        ],
    }

    # ---- legend swatches ---------------------------------------------------
    legend_html = "".join(
        f'<span style="display:inline-block;width:12px;height:12px;background:{col};'
        f'border-radius:2px;margin-right:4px;vertical-align:middle"></span>'
        f'<span style="margin-right:14px;font-size:11px;color:#333">{SETUP_LABELS[code]}</span>'
        for code, col in SETUP_COLOURS.items() if code not in ("NO_SETUP", "LOW_CONV")
    )
    legend_html += (
        f'<span style="display:inline-block;width:12px;height:12px;background:#9E9E9E;'
        f'border-radius:2px;margin-right:4px;vertical-align:middle"></span>'
        f'<span style="font-size:11px;color:#333">Low Conviction</span>'
    )

    # ---- assemble HTML -----------------------------------------------------
    plotly_cdn   = "https://cdn.plot.ly/plotly-2.27.0.min.js"
    data1_json   = _json.dumps([scatter_hist, scatter_today])
    layout1_json = _json.dumps(layout1)
    data2_json   = _json.dumps([line_price, line_key, highlight_price, highlight_key])
    layout2_json = _json.dumps(layout2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SPX GEX Dashboard</title>
<script src="{plotly_cdn}"></script>
<style>
  body        {{ font-family: -apple-system, Arial, sans-serif; background:#f0f0f0; color:#222; margin:0; padding:20px; }}
  h1          {{ font-size:17px; font-weight:600; color:#111; margin:0 0 3px; }}
  .sub        {{ font-size:11px; color:#888; margin-bottom:14px; }}
  .legend     {{ margin-bottom:18px; line-height:2; }}
  .chart-wrap {{ background:#ffffff; border-radius:8px; padding:14px 10px 4px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.1); }}
</style>
</head>
<body>
<h1>SPX GEX Dashboard</h1>
<div class="sub">Auto-generated · {n} trading day(s) · hover any point for detail</div>
<div class="legend">{legend_html}</div>
<div class="chart-wrap"><div id="c1"></div></div>
<div class="chart-wrap"><div id="c2"></div></div>
<script>
var cfg = {{responsive:true, displayModeBar:false}};
Plotly.newPlot('c1', {data1_json}, {layout1_json}, cfg);
Plotly.newPlot('c2', {data2_json}, {layout2_json}, cfg);
</script>
</body>
</html>"""

    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard:  {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Build concise GEX summary CSV")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dates",
        nargs="+",
        metavar="YYYYMMDD",
        help="One or more date prefixes to include (e.g. 20260603 20260604 20260605)",
    )
    group.add_argument(
        "--file",
        metavar="PATH",
        help="Process a single JSON file",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=str(CONCISE_CSV),
        help=f"Output CSV path (default: {CONCISE_CSV})",
    )
    parser.add_argument(
        "--all-snapshots",
        action="store_true",
        help="Include all snapshots per day (default: latest per day only)",
    )
    parser.add_argument(
        "--webhooks",
        action="store_true",
        help="Fire Option Alpha webhooks based on GEX setup classification",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --webhooks: print webhook URLs without making HTTP calls",
    )
    args = parser.parse_args()

    if args.file:
        source_files = [Path(args.file)]
    else:
        source_files = find_source_jsons(args.dates)
        if not args.all_snapshots:
            source_files = pick_one_per_day(source_files)

    if not source_files:
        print("No matching JSON files found.")
        return

    rows = []
    for path in source_files:
        try:
            summary = summarize_file(path)
            concise = to_concise(summary)
            rows.append(concise)
            setup = classify_setup(concise, summary)
            label = SETUP_LABELS.get(setup, setup)
            print(f"Processed: {path.name}  date={summary.get('date', '')[:10]}  last={summary.get('last')}  key_strike={summary.get('highest_absolute_gex_strike')}  dominance={summary.get('key_strike_dominance_pct')}%  setup={setup} ({label})")
            if args.webhooks:
                fire_webhook(setup, concise, dry_run=args.dry_run)
        except Exception as exc:
            print(f"ERROR processing {path.name}: {exc}")

    output_path = Path(args.output)
    rows = merge_ohlc(rows, output_path)
    write_concise_csv(rows, output_path)
    print(f"\nWrote {len(rows)} row(s) to: {output_path}")

    dashboard_path = output_path.parent / "gex_dashboard.html"
    generate_dashboard(rows, dashboard_path)


if __name__ == "__main__":
    main()
