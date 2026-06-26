---
description: Data Cleaning and Model Retraining Workflow
---

# Data Cleaning and Model Retraining Workflow

This workflow describes the correct order of operations when data is cleaned or corrected in the GEX database.

## When to Use This Workflow

Use this workflow when:
- Flat summary columns are corrected (e.g., fixing `total_put_gex`, `total_call_gex`, `gex_ratio`)
- Raw JSON data is backfilled
- Source field values are corrected
- Any data integrity issues are fixed that affect calculated metrics

## Workflow Steps

### Step 1: Fix Data Issues
- Correct the underlying data in `gex_snapshots` table
- Run backfill scripts to fix flat summary columns if needed
- Example: `python backfill_flat_summary.py`

### Step 2: Verify Data Integrity
- Use the "Verify Data Integrity" button in the Admin tab
- This checks:
  - Source field validity ('gex' or 'histgex')
  - Raw JSON presence (excludes known-missing gex snapshots)
  - Deep verification: recalculates from raw data and compares to persisted values

### Step 3: Regenerate Trade Signals
- Use the "Regenerate Trade Signals" button in the Admin tab
- This runs `backfill_trade_signals.py`
- Trade signals depend on corrected metrics (gex_ratio, net_gex, etc.)
- Old signals must be replaced with signals based on corrected data

### Step 4: Retrain Random Forest Model
- Use the "Retrain RF Model" button in the Admin tab
- RF model is trained on trade signals
- Must be retrained after signals are regenerated with corrected data

### Step 5: Retrain HMM Model
- Use the "Retrain HMM Model" button in the Admin tab
- HMM model is trained on RTH snapshots
- Must be retrained if flat summary columns were corrected

### Step 6: Hard Restart Server
- Stop the server: `Stop-Process -Name python -Force`
- Start the server: `python gex_viewer.py --port 5050`
- This ensures all cached data is cleared and models are reloaded

## Why This Order Matters

1. **Data first**: All downstream components depend on the raw data
2. **Verification second**: Confirm data is correct before regenerating signals
3. **Signals third**: Signals depend on corrected metrics
4. **RF fourth**: RF model depends on corrected signals
5. **HMM fifth**: HMM model depends on corrected snapshot data
6. **Restart last**: Ensures all changes are loaded into memory

## Dependencies

- Trade signals → depend on: gex_ratio, net_gex, kcs, sentiment_pct
- RF model → depends on: trade_signals (training labels)
- HMM model → depends on: gex_snapshots flat columns (net_gex, kcs, sentiment_pct, dist_to_key, total_put_vol)

## Example Scenario

**Problem**: `total_put_gex` and `total_call_gex` are 0 for some snapshots

**Solution**:
1. Run `backfill_flat_summary.py` to fix the columns
2. Verify data integrity with Admin tab button
3. Regenerate trade signals (gex_ratio changed)
4. Retrain RF model (training labels changed)
5. Retrain HMM model (if RTH snapshots affected)
6. Hard restart server
