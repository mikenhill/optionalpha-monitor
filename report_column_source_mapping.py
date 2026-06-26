import csv
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "column_source_mapping_report.csv"

# Column mapping based on code analysis
columns = [
    {
        "Column": "Time (ET)",
        "Display Name": "Time (ET)",
        "Source": "DB field: ntime (integer HHMM format)",
        "Raw JSON Field": "N/A - derived from snapshot metadata",
        "Calculation": "Formatted as HH:MM from ntime field",
        "DB Flat Column": "ntime",
        "Function": "load_gex_snapshot()",
        "Notes": "Stored as integer (e.g., 930, 1000, 1032)"
    },
    {
        "Column": "SPX",
        "Display Name": "SPX",
        "Source": "DB flat column: uprice",
        "Raw JSON Field": "market.gex: 'last' / market.histgex: 'uprice'",
        "Calculation": "Direct read from DB flat column",
        "DB Flat Column": "uprice",
        "Function": "load_gex_snapshot()",
        "Notes": "CRITICAL RULE: market.gex uses 'last', market.histgex uses 'uprice'"
    },
    {
        "Column": "Senti%",
        "Display Name": "Senti%",
        "Source": "DB flat column: sentiment",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "% of positive net GEX bars in 40-strike window: (pos_bars / total_bars) * 100",
        "DB Flat Column": "sentiment",
        "Function": "_compute_flat_summary()",
        "Notes": "Calculated from raw JSON data array, stored in DB"
    },
    {
        "Column": "Ratio",
        "Display Name": "Ratio",
        "Source": "DB flat column: gex_ratio",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "If call_gex > put_gex: call_gex/put_gex (positive). If put_gex > call_gex: -put_gex/call_gex (negative)",
        "DB Flat Column": "gex_ratio",
        "Function": "_compute_flat_summary()",
        "Notes": "Flips sign based on which side is larger"
    },
    {
        "Column": "Net GEX",
        "Display Name": "Net GEX",
        "Source": "DB flat column: net_gex",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Sum of 'net' field across 40-strike window (20 below + 20 above uprice)",
        "DB Flat Column": "net_gex",
        "Function": "_compute_flat_summary()",
        "Notes": "40-strike window: below[-20:] + above[:20]"
    },
    {
        "Column": "KCS",
        "Display Name": "KCS",
        "Source": "DB flat column: kcs",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Key Strike Confluence Score = (0.5*gex_share + 0.3*oi_share + 0.2*vol_share) * proximity_factor * 100",
        "DB Flat Column": "kcs",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Proximity factor = exp(-distance/25), distance = |key_strike - uprice|"
    },
    {
        "Column": "Regime",
        "Display Name": "Regime",
        "Source": "DB flat column: hmm_label",
        "Raw JSON Field": "N/A - HMM model prediction",
        "Calculation": "HMM (Gaussian Hidden Markov Model) prediction based on: net_gex, kcs, sentiment_pct, dist_to_key, total_put_vol",
        "DB Flat Column": "hmm_label",
        "Function": "predict_hmm_sequence()",
        "Notes": "Only for RTH (ntime >= 930). Pre-market shows null/empty"
    },
    {
        "Column": "Put GEX",
        "Display Name": "Put GEX",
        "Source": "DB flat column: total_put_gex",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Sum of 'pg' (put gamma exposure) across 40-strike window",
        "DB Flat Column": "total_put_gex",
        "Function": "_compute_flat_summary()",
        "Notes": "Negative values indicate put dominance"
    },
    {
        "Column": "cVol",
        "Display Name": "cVol",
        "Source": "DB flat column: total_call_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Sum of 'cvol' (call volume) across 40-strike window",
        "DB Flat Column": "total_call_vol",
        "Function": "_compute_flat_summary()",
        "Notes": "Calculated from raw JSON strike data"
    },
    {
        "Column": "pVol",
        "Display Name": "pVol",
        "Source": "DB flat column: total_put_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Sum of 'pvol' (put volume) across 40-strike window",
        "DB Flat Column": "total_put_vol",
        "Function": "_compute_flat_summary()",
        "Notes": "Calculated from raw JSON strike data"
    },
    {
        "Column": "Flip",
        "Display Name": "Flip",
        "Source": "DB flat column: flip",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Strike level where cumulative net GEX crosses zero within 40-strike window",
        "DB Flat Column": "flip",
        "Function": "_compute_flat_summary()",
        "Notes": "Linear interpolation between strikes where sign changes"
    },
    {
        "Column": "Key",
        "Display Name": "Key",
        "Source": "DB flat column: key_strike",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Strike with highest proximity-weighted absolute GEX: max(abs(abs) * exp(-distance/25))",
        "DB Flat Column": "key_strike",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Proximity-weighted to favor strikes near uprice"
    },
    {
        "Column": "K-cGEX",
        "Display Name": "K-cGEX",
        "Source": "DB flat column: key_call_gex",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Call GEX (cg) at the key strike",
        "DB Flat Column": "key_call_gex",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "K-pGEX",
        "Display Name": "K-pGEX",
        "Source": "DB flat column: key_put_gex",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Put GEX (pg) at the key strike",
        "DB Flat Column": "key_put_gex",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "K-cOI",
        "Display Name": "K-cOI",
        "Source": "DB flat column: key_call_oi",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Call Open Interest (coi) at the key strike",
        "DB Flat Column": "key_call_oi",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "K-pOI",
        "Display Name": "K-pOI",
        "Source": "DB flat column: key_put_oi",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Put Open Interest (poi) at the key strike",
        "DB Flat Column": "key_put_oi",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "K-cVol",
        "Display Name": "K-cVol",
        "Source": "DB flat column: key_call_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Call Volume (cvol) at the key strike",
        "DB Flat Column": "key_call_vol",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "K-pVol",
        "Display Name": "K-pVol",
        "Source": "DB flat column: key_put_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Put Volume (pvol) at the key strike",
        "DB Flat Column": "key_put_vol",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key strike row in data array"
    },
    {
        "Column": "Key2",
        "Display Name": "Key2",
        "Source": "DB flat column: key2_strike",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Second-highest proximity-weighted absolute GEX (excluding key strike)",
        "DB Flat Column": "key2_strike",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Secondary wall strike"
    },
    {
        "Column": "K2-Abs",
        "Display Name": "K2-Abs",
        "Source": "DB flat column: key2_abs",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Absolute GEX (abs) at the key2 strike",
        "DB Flat Column": "key2_abs",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key2 strike row in data array"
    },
    {
        "Column": "K2-cVol",
        "Display Name": "K2-cVol",
        "Source": "DB flat column: key2_call_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Call Volume (cvol) at the key2 strike",
        "DB Flat Column": "key2_call_vol",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key2 strike row in data array"
    },
    {
        "Column": "K2-pVol",
        "Display Name": "K2-pVol",
        "Source": "DB flat column: key2_put_vol",
        "Raw JSON Field": "N/A - calculated from data array",
        "Calculation": "Put Volume (pvol) at the key2 strike",
        "DB Flat Column": "key2_put_vol",
        "Function": "_compute_key_strike_stats()",
        "Notes": "Direct field from key2 strike row in data array"
    },
]

# Write CSV report
with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Column', 'Display Name', 'Source', 'Raw JSON Field', 'Calculation', 'DB Flat Column', 'Function', 'Notes']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(columns)

print(f"Report generated: {OUTPUT_PATH}")
print(f"Total columns mapped: {len(columns)}")
