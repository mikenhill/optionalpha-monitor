# Architecture Summary

## Tech Stack
- **Backend**: Flask (gex_viewer.py, ~6700 lines)
- **Database**: SQLite (gex.db)
- **Frontend**: HTML templates (historical.html, live.html, etc.) with Plotly charts
- **Server**: Runs on port 5050

## Database Schema

### Primary Table: `snapshot`
Unified table for all GEX data (historical + live). Key columns:
- `ndate`, `ntime`, `symbol`, `uprice`, `raw_json`, `capture_ts`, `source`
- Summary columns: `sentiment`, `gex_ratio`, `net_gex`, `kcs`, `dominance`
- GEX breakdown: `total_call_gex`, `total_put_gex`, `key_strike`, `key_call_gex`, `key_put_gex`
- OI/Vol: `total_call_oi`, `total_put_oi`, `key_call_oi`, `key_put_oi`, `total_call_vol`, `total_put_vol`, `key_call_vol`, `key_put_vol`
- Secondary key: `key2_strike`, `key2_abs`, `key2_call_vol`, `key2_put_vol`, `flip`
- HMM: `is_premarket`, `hmm_state`, `hmm_label`

### Obsolete Tables (renamed)
- `obsolete_live_captures` (old live data)
- `obsolete_gex_snapshots` (old historical data)

### Other Tables
- `percentile_history`: Pre-computed percentiles (34K+ rows)
- `hmm_model`: Trained GaussianHMM (4 states, 5 features)
- `daily_narratives`: AI-generated trading narratives
- `live_analysis`: Per-snapshot analysis

## Key Endpoints

### Live Data
- `/api/live/fetch`: Fetches live data via optionalpha_daily.py, saves to `snapshot` with `source='gex'`
- `/api/live/captures`: Returns today's snapshots from `snapshot WHERE source='gex'`
- `/api/live/snapshot`: Returns single snapshot by time

### Historical Data
- `/api/snapshots-summary`: Paginated historical snapshots (filters by regime/time range)
- `/api/snapshot`: Returns single historical snapshot by date/time
- `/api/sync-historical`: Imports historical GEX JSON files into `snapshot` with `source='histgex'`

### Other
- `/api/trade-signals`: Returns trade signals for a date

## Data Flow

### Live Data Pipeline
1. User clicks "Fetch Live Data"
2. Runs `optionalpha_daily.py` to fetch data
3. Runs `optionalpha_daily-summary.py` to generate summary
4. Calls `save_live_snapshot()` to insert into `snapshot` table
5. HMM prediction runs on historical data to label regime
6. Data persisted with `source='gex'`

### Historical Data Pipeline
1. User clicks "Load Missing Historical"
2. Calls `_migrate_histgex_to_db()` to import JSON files
3. Data inserted into `snapshot` with `source='histgex'`
4. Summary columns computed and stored

## Key Functions

### Database Operations
- `_db()`: Context manager for SQLite connections
- `_ensure_snapshot_table()`: Creates/updates `snapshot` table schema, handles duplicates via `rowid`

### Data Processing
- `save_live_snapshot()`: Saves live data to `snapshot` table
- `load_gex_snapshot()`: Loads single snapshot from `snapshot`
- `_compute_flat_summary()`: Computes summary fields from raw JSON

### HMM
- `predict_hmm_sequence()`: Predicts regime states using GaussianHMM
- Trained on RTH data only (ntime >= 930)

## Current Issue

**File**: `gex_viewer.py`, lines 5625-5651 (`_api_live_fetch_inner`)

**Problem**: INSERT statement has mismatched question marks vs values
- Line 5633: 5 question marks
- Line 5634: 28 question marks (should be 26)
- Total: 33 question marks, but only 31 values in tuple
- Expected: 31 question marks (33 columns - 2 hardcoded: symbol='SPX', source='gex')

**Fix Required**: Line 5634 needs 26 question marks instead of 28.
