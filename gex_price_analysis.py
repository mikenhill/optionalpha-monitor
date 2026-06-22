"""
GEX Intraday Price Analysis
============================
Loads the captured gex_intraday_summary.csv and analyses how GEX structure
relates to subsequent intraday price behaviour.

The goal is to LEARN about GEX — specifically:
  1. Regime effect    — do moves amplify when net GEX is negative?
  2. Wall magnetism   — does price gravitate toward the highest-abs-GEX strike?
  3. Flip level       — does crossing the GEX flip level predict acceleration?
  4. Wall proximity   — does being near the GEX wall suppress volatility?

ORB correlation is included as section 5 (secondary).

Usage
-----
  python gex_price_analysis.py                         # uses default paths
  python gex_price_analysis.py --orb orb_webhook_simulation.csv
"""

import argparse
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR    = Path(__file__).resolve().parent
DEFAULT_GEX = BASE_DIR / "results" / "histgex" / "gex_intraday_summary.csv"
DEFAULT_ORB = Path(r"g:\My Drive\Colab Notebooks\optionalpha_orb\orb_webhook_simulation.csv")
OUT_CSV     = BASE_DIR / "results" / "histgex" / "gex_price_analysis.csv"


# ---------------------------------------------------------------------------
# Load & enrich
# ---------------------------------------------------------------------------

def load_gex(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"]   = pd.to_datetime(df["date"], format="%m/%d/%Y")
    df["ntime"]  = df["ntime"].astype(int)
    df = df.sort_values(["date", "ntime"]).reset_index(drop=True)

    # ---- Forward-looking price change (next 30-min slot) ----
    # For each row, the NEXT row's uprice (if same day) is where price ended up.
    df["uprice_next"] = df.groupby("date")["uprice"].shift(-1)
    df["price_chg"]   = df["uprice_next"] - df["uprice"]
    df["abs_chg"]     = df["price_chg"].abs()

    # ---- GEX regime ----
    df["gex_regime"] = df["net_gex"].apply(lambda x: "POSITIVE" if x >= 0 else "NEGATIVE")

    # ---- Distance from current price to GEX wall (highest abs strike) ----
    df["dist_to_wall"]  = df["highest_abs_strike"] - df["uprice"]
    df["above_wall"]    = df["uprice"] > df["highest_abs_strike"]

    # ---- Distance from current price to GEX flip level ----
    df["dist_to_flip"]  = df["gex_flip_level"] - df["uprice"]
    df["above_flip"]    = df["uprice"] > df["gex_flip_level"]   # NaN if flip not found

    # ---- Price moving toward or away from GEX wall ----
    # Positive = moving toward wall, Negative = moving away
    df["toward_wall"] = np.sign(df["dist_to_wall"]) * np.sign(df["price_chg"])

    # ---- Flip crossed in next period ----
    # True if the price crossed the flip level between this and next snapshot
    df["flip_crossed"] = (
        (df["above_flip"] != df.groupby("date")["above_flip"].shift(-1)) &
        df["gex_flip_level"].notna()
    )

    return df


# ---------------------------------------------------------------------------
# Analysis sections
# ---------------------------------------------------------------------------

def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def analyse_regime_effect(df: pd.DataFrame):
    """Section 1: Do price moves amplify under negative GEX?"""
    section("1. GEX REGIME vs SUBSEQUENT PRICE MOVE (next 30 min)")

    # Exclude last slot of each day (no next-period data)
    d = df.dropna(subset=["price_chg"])

    stats = d.groupby("gex_regime").agg(
        snapshots   = ("price_chg", "count"),
        mean_abs_chg= ("abs_chg",   "mean"),
        median_abs_chg=("abs_chg",  "median"),
        max_abs_chg = ("abs_chg",   "max"),
        pct_up      = ("price_chg", lambda x: (x > 0).mean() * 100),
        mean_chg    = ("price_chg", "mean"),
    ).round(2)
    print(stats.to_string())

    pos = d[d["gex_regime"] == "POSITIVE"]["abs_chg"]
    neg = d[d["gex_regime"] == "NEGATIVE"]["abs_chg"]
    if len(pos) > 1 and len(neg) > 1:
        amplification = neg.mean() / pos.mean() if pos.mean() else float("nan")
        print(f"\n  Negative GEX amplification factor: {amplification:.2f}x")
        print(f"  (avg abs move is {amplification:.2f}x larger under negative GEX)")


def analyse_wall_magnetism(df: pd.DataFrame):
    """Section 2: Does price gravitate toward the GEX wall?"""
    section("2. GEX WALL MAGNETISM")
    d = df.dropna(subset=["price_chg", "dist_to_wall"])

    # Bin by distance from wall
    bins   = [-500, -50, -20, -5, 5, 20, 50, 500]
    labels = ["wall >50 below", "wall 20-50 below", "wall 5-20 below",
              "at wall (±5)",
              "wall 5-20 above", "wall 20-50 above", "wall >50 above"]
    d = d.copy()
    d["wall_zone"] = pd.cut(d["dist_to_wall"], bins=bins, labels=labels)

    stats = d.groupby("wall_zone", observed=True).agg(
        snapshots     = ("price_chg", "count"),
        mean_chg      = ("price_chg", "mean"),
        toward_wall_pct = ("toward_wall", lambda x: (x > 0).mean() * 100),
        mean_abs_chg  = ("abs_chg",   "mean"),
    ).round(2)
    print(stats.to_string())
    print("\n  toward_wall_pct > 50% = price tends to move toward the GEX wall")
    print("  mean_chg > 0 in 'above' zones = price pulled back down toward wall")


def analyse_flip_level(df: pd.DataFrame):
    """Section 3: Does the GEX flip level act as support/resistance?"""
    section("3. GEX FLIP LEVEL as SUPPORT / RESISTANCE")
    d = df.dropna(subset=["dist_to_flip", "price_chg"])

    if d.empty:
        print("  Insufficient flip level data (NaN for all rows)")
        return

    bins   = [-1000, -50, -20, -5, 5, 20, 50, 1000]
    labels = ["flip >50 below", "flip 20-50 below", "flip 5-20 below",
              "at flip (±5)",
              "flip 5-20 above", "flip 20-50 above", "flip >50 above"]
    d = d.copy()
    d["flip_zone"] = pd.cut(d["dist_to_flip"], bins=bins, labels=labels)

    stats = d.groupby("flip_zone", observed=True).agg(
        snapshots  = ("price_chg", "count"),
        mean_chg   = ("price_chg", "mean"),
        mean_abs   = ("abs_chg",   "mean"),
        pct_up     = ("price_chg", lambda x: (x > 0).mean() * 100),
    ).round(2)
    print(stats.to_string())
    print("\n  pct_up > 50% above flip, < 50% below flip = flip acted as support/resistance")


def analyse_wall_proximity_volatility(df: pd.DataFrame):
    """Section 4: Does proximity to the GEX wall suppress volatility?"""
    section("4. GEX WALL PROXIMITY vs VOLATILITY (price compression)")
    d = df.dropna(subset=["abs_chg", "dist_to_wall"])
    d = d.copy()
    d["wall_dist_abs"] = d["dist_to_wall"].abs()

    # Correlation between distance-to-wall and subsequent move size
    corr = d["wall_dist_abs"].corr(d["abs_chg"])
    print(f"  Correlation (distance from wall → abs move size): {corr:.3f}")
    print(f"  Negative = closer to wall means SMALLER moves (compression)")
    print(f"  Positive = closer to wall means LARGER moves")

    # Bins
    d["dist_bin"] = pd.cut(d["wall_dist_abs"],
                           bins=[0, 10, 25, 50, 100, 1000],
                           labels=["0-10", "10-25", "25-50", "50-100", ">100"])
    stats = d.groupby("dist_bin", observed=True).agg(
        snapshots    = ("abs_chg", "count"),
        mean_abs_chg = ("abs_chg", "mean"),
        median_abs   = ("abs_chg", "median"),
    ).round(2)
    print(f"\n  |dist to wall|  →  next 30-min abs move\n")
    print(stats.to_string())


def analyse_orb_correlation(df: pd.DataFrame, orb_path: Path):
    """Section 5 (secondary): ORB entry outcomes vs GEX state at signal time."""
    section("5. ORB SIGNAL OUTCOME vs GEX STATE AT ENTRY TIME (secondary)")

    if not orb_path.exists():
        print(f"  ORB file not found: {orb_path}")
        return

    orb = pd.read_csv(orb_path)
    orb["date"] = pd.to_datetime(orb["Date"], format="%Y-%m-%d")

    # Match each ORB entry to the nearest GEX snapshot at or before entry time
    # Entry times are like "10:25" — convert to ntime int
    orb["entry_ntime"] = orb["Entry Time"].str.replace(":", "").astype(int)

    merged_rows = []
    for _, trade in orb.iterrows():
        day_gex = df[df["date"] == trade["date"]].copy()
        if day_gex.empty:
            continue
        # Last GEX snapshot at or before entry
        before = day_gex[day_gex["ntime"] <= trade["entry_ntime"]]
        if before.empty:
            before = day_gex.iloc[[0]]
        snap = before.iloc[-1]

        merged_rows.append({
            "date":              trade["date"].strftime("%m/%d/%Y"),
            "entry_time":        trade["Entry Time"],
            "direction":         trade["Direction"],
            "exit_reason":       trade["Exit Reason"],
            "pnl_r":             trade["P&L (R)"],
            "gex_ntime":         snap["ntime"],
            "gex_regime":        snap["gex_regime"],
            "net_gex":           snap["net_gex"],
            "gex_flip_level":    snap["gex_flip_level"],
            "dist_to_wall":      snap["dist_to_wall"],
            "uprice_at_gex":     snap["uprice"],
        })

    if not merged_rows:
        print("  No ORB trades matched to GEX data (need overlapping dates).")
        print("  Capture more historical GEX dates to populate this section.")
        return

    m = pd.DataFrame(merged_rows)
    print(f"\n  Matched {len(m)} ORB trades to GEX snapshots\n")

    print("  --- P&L by GEX regime at entry ---")
    print(m.groupby("gex_regime").agg(
        trades    = ("pnl_r", "count"),
        targets   = ("exit_reason", lambda x: (x == "TARGET").sum()),
        stops     = ("exit_reason", lambda x: (x == "STOP").sum()),
        eod       = ("exit_reason", lambda x: (x == "EOD").sum()),
        mean_r    = ("pnl_r", "mean"),
        total_r   = ("pnl_r", "sum"),
    ).round(2).to_string())

    print("\n  --- P&L by direction × GEX regime ---")
    print(m.groupby(["direction", "gex_regime"]).agg(
        trades  = ("pnl_r", "count"),
        mean_r  = ("pnl_r", "mean"),
        total_r = ("pnl_r", "sum"),
    ).round(2).to_string())

    return m


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gex", default=str(DEFAULT_GEX),
                        help="Path to gex_intraday_summary.csv")
    parser.add_argument("--orb", default=str(DEFAULT_ORB),
                        help="Path to orb_webhook_simulation.csv")
    args = parser.parse_args()

    gex_path = Path(args.gex)
    orb_path = Path(args.orb)

    if not gex_path.exists():
        print(f"GEX summary not found: {gex_path}")
        print("Run gex_historical_intraday.py first to capture data.")
        raise SystemExit(1)

    df = load_gex(gex_path)
    days = df["date"].nunique()
    snaps = len(df)
    print(f"\nLoaded {snaps} snapshots across {days} trading day(s).")
    print(f"Dates: {df['date'].dt.strftime('%Y-%m-%d').unique().tolist()}")

    if days < 5:
        print(f"\n  NOTE: Only {days} day(s) of data loaded.")
        print("  Statistics will be more meaningful with 20+ days.")
        print("  Run: python gex_historical_intraday.py --from YYYYMMDD --to YYYYMMDD")

    analyse_regime_effect(df)
    analyse_wall_magnetism(df)
    analyse_flip_level(df)
    analyse_wall_proximity_volatility(df)
    orb_merged = analyse_orb_correlation(df, orb_path)

    # Save enriched data
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nEnriched analysis CSV saved: {OUT_CSV}")
    print("\nTo get meaningful statistics, capture more days:")
    print("  python gex_historical_intraday.py --from 20260601 --to 20260618")
