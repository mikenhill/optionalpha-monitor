# Design Specification
**Project:** optionalpha-monitor  
**Purpose:** GEX (Gamma Exposure) data tracking, ML-based trade signal generation, and performance analysis  
**Database:** SQLite (gex.db)  
**Server:** Flask on port 5050  

---

## 1. Database Schema

### Primary Tables (Active)

#### `gex_strike_window` - Core GEX Data Storage
**Purpose:** Stores raw GEX strike window data for all historical and live snapshots  
**Schema:**
- `ndate` (INTEGER NOT NULL) - Date in YYYYMMDD format
- `ntime` (INTEGER NOT NULL) - Time in HHMM format
- `symbol` (TEXT NOT NULL) - Ticker symbol (typically 'SPX')
- `price` (REAL NOT NULL) - Underlying price
- `data` (TEXT NOT NULL) - Raw JSON string containing 40-strike GEX window data
- `source` (TEXT) - Data source: 'gex' (live), 'histgex' (historical)
- `hmm_state` (INTEGER) - HMM predicted state (0-3)
- `hmm_label` (TEXT) - HMM regime label: 'Positive', 'Negative', 'Volatile', 'Neutral'
- PRIMARY KEY: (ndate, ntime, symbol)

**IMPORTANT:** This table stores **only raw JSON data**. All derived metrics (net_gex, kcs, sentiment, etc.) are calculated on-the-fly from the `data` column. There are NO flat summary columns.

**Indexes:**
- `idx_gex_strike_window_ndate` on ndate
- `idx_gex_strike_window_symbol` on symbol

---

#### `ml_labels` - ML Training Labels
**Purpose:** Stores outcome labels for ML model training  
**Schema:**
- `ndate`, `ntime` - Snapshot identifier
- `range_regime` - TIGHT/NORMAL/WIDE (based on EOD range vs rolling median)
- `direction_1hr`, `direction_2hr`, `direction_eod` - UP/FLAT/DOWN at different horizons
- `pct_1hr`, `pct_2hr` - % SPX move from snapshot to horizon
- `range_1hr`, `range_2hr` - High-low range in points
- `trade_viable_ic`, `trade_viable_sps`, `trade_viable_scs`, `trade_viable_lcs`, `trade_viable_lps` - Binary flags for trade type viability
- `flip_held_1hr`, `flip_held_2hr` - Whether SPX stayed same side of GEX flip level

**Data Source:** Computed by joining `gex_strike_window` with `spx_ohlc_5min` (SPX 5-minute bars from yfinance)

---

#### `ml_predictions` - Live ML Predictions
**Purpose:** Stores real-time ML predictions with outcomes backfilled later  
**Schema:**
- `ndate`, `ntime` - Snapshot identifier
- `predicted_at` - Timestamp when prediction was made
- `vol_regime_pred`, `vol_regime_proba` - Predicted volatility regime and probability
- `direction_pred`, `direction_proba` - Predicted 2hr direction and probability
- `trade_pred`, `trade_code`, `confidence` - Trade recommendation
- `vol_regime_actual`, `direction_1hr_actual`, `direction_2hr_actual`, `direction_eod_actual` - Actual outcomes (filled later)
- `trade_viable_actual` - Actual trade viability (filled later)
- `vol_correct`, `direction_1hr_correct`, `direction_2hr_correct` - Binary correctness flags
- `outcome_filled_at` - When outcomes were backfilled
- PRIMARY KEY: (ndate, ntime)

**Workflow:** Populated during live "Fetch Live Data" operations; outcomes backfilled on server startup

---

#### `ml_models` - Trained ML Models
**Purpose:** Stores serialized trained models  
**Schema:**
- `model_name` - 'vol_regime' or 'direction' (PRIMARY KEY)
- `trained_at` - Training timestamp
- `n_samples` - Number of training samples
- `accuracy` - Cross-validated accuracy
- `features` - JSON array of feature names used
- `classes` - JSON array of class labels
- `model_blob` - Pickled model + scaler + label_encoder (BLOB)

**Models:**
- `vol_regime` - Binary: TIGHT vs WIDE (NORMAL collapsed to TIGHT) - Uses RandomForest
- `direction` - Multi-class: UP/FLAT/DOWN at 2hr horizon - Uses XGBoost

---

#### `ml_model_history` - Model Version History
**Purpose:** Stores previous model versions before retraining (for comparison)  
**Schema:** Same as `ml_models` (archival table)

---

#### `ml_trade_performance` - Trade Signal Performance Metrics
**Purpose:** Tracks daily ML trade signal performance (paper trading)  
**Schema:**
- `id` - Auto-increment primary key
- `ndate` - Date being measured
- `model_version` - Model identifier (timestamp-based if force_retrain, else 'default')
- `training_date` - When the model was trained
- `force_retrain` - Whether forced retrain was used
- `total_predictions`, `high_conf_predictions`, `medium_conf_predictions`, `low_conf_predictions` - Confidence distribution
- `trade_correct`, `trade_incorrect`, `trade_neutral` - Trade outcome counts
- `ic_correct`, `ic_total`, `sps_correct`, `sps_total`, `scs_correct`, `scs_total`, `lcs_correct`, `lcs_total`, `lps_correct`, `lps_total` - Per-trade-type accuracy
- `high_conf_accuracy`, `medium_conf_accuracy` - Confidence-level accuracy
- `total_outcome_points`, `avg_outcome_points`, `max_drawdown` - Financial metrics
- `vol_regime_correct`, `vol_regime_total`, `vol_regime_accuracy` - Vol regime accuracy
- `direction_2hr_correct`, `direction_2hr_total`, `direction_2hr_accuracy` - Direction accuracy
- `computed_at` - When metrics were calculated
- UNIQUE: (ndate, model_version)

**Workflow:** Computed daily for previous day's predictions in daily workflow

---

#### `trade_signals` - Trade Signal Recommendations
**Purpose:** Stores generated trade signals with actual outcomes  
**Schema:**
- `id` - Auto-increment primary key
- `ndate`, `ntime` - Snapshot identifier
- `symbol` - Ticker (default 'SPX')
- `generated_ts` - When signal was generated
- `regime` - Volatility regime
- `setup_type` - Trade setup type
- `action` - LONG/SHORT/NEUTRAL
- `short_strike`, `wing_strike`, `short_strike2`, `wing_strike2` - Strike prices
- `structure` - Trade structure (IC, SPS, SCS, LCS, LPS, IB)
- `rationale`, `invalidation`, `caution` - Text notes
- `prev_outcome` - Previous signal outcome
- `next_spx`, `next_ntime` - Next snapshot for outcome calculation
- `outcome` - WIN/LOSS/NEUTRAL/CORRECT/MISSED
- `outcome_points` - Financial outcome (paper trading P&L)
- `is_llm_enhanced` - Whether LLM was used for enhancement
- UNIQUE: (ndate, ntime, symbol)

**Outcome Calculation:** Based on next snapshot price movement vs signal direction

---

#### `spx_ohlc_5min` - SPX 5-Minute OHLC Data
**Purpose:** Stores SPX 5-minute OHLC bars for label calculation  
**Schema:**
- `datetime` - Timestamp
- `open`, `high`, `low`, `close` - OHLC values
- PRIMARY KEY: (datetime)

**Data Source:** Fetched from yfinance

---

#### `hmm_model` - Trained HMM Model
**Purpose:** Stores trained GaussianHMM for regime prediction  
**Schema:**
- `model_blob` - Pickled HMM model (BLOB)
- `trained_at` - Training timestamp
- `n_samples` - Number of training samples

**Model:** GaussianHMM with 4 states, trained on RTH data only (ntime >= 930)

---

#### `percentile_history` - Pre-computed GEX Percentiles
**Purpose:** Stores historical percentile values for GEX metrics  
**Schema:** Multiple columns for different GEX metrics at different percentiles

**Usage:** Quick percentile lookups without real-time calculation

---

#### `metric_history` - Historical Metric Values
**Purpose:** Stores historical EOD values for metrics  
**Schema:**
- `metric_name` - Metric identifier
- `date` - Date
- `value` - Metric value
- PRIMARY KEY: (metric_name, date)

---

#### `live_analysis` - Per-Snapshot Analysis
**Purpose:** Stores analysis results for live snapshots  
**Schema:**
- `ndate`, `ntime` - Snapshot identifier
- `analysis_json` - Analysis results as JSON
- PRIMARY KEY: (ndate, ntime)

---

#### `daily_narratives` - AI-Generated Trading Narratives
**Purpose:** Stores daily trading narratives generated by AI  
**Schema:**
- `date` - Date
- `narrative` - Narrative text
- PRIMARY KEY: (date)

---

#### `rf_model` - RandomForest Trade Classifier
**Purpose:** Stores trained RandomForest model for trade signal quality prediction  
**Schema:**
- `id` - Auto-increment primary key
- `trained_at` - Training timestamp
- `n_samples` - Number of training samples
- `meta_json` - Metadata as JSON
- `model_blob` - Pickled model (BLOB)

**Usage:** Predicts trade signal quality (good vs bad)

---

### Obsolete/Legacy Tables

#### `snapshot` - OBSOLETE
**Status:** Legacy table, no longer used  
**Reason:** Replaced by `gex_strike_window` with simplified schema (raw JSON only)

#### `snapshots` - OBSOLETE
**Status:** Legacy table, no longer used

#### `gex_snapshots` - OBSOLETE
**Status:** Legacy table, no longer used

---

## 2. Data Architecture

### Raw Data (Persisted)

**In `gex_strike_window`:**
- `ndate`, `ntime`, `symbol`, `price` - Basic snapshot metadata
- `data` - Raw JSON string containing 40-strike GEX window:
  - Strike prices
  - Call/Put GEX at each strike
  - Call/Put OI at each strike
  - Call/Put Volume at each strike
  - Key strike information
- `source` - Data source identifier
- `hmm_state`, `hmm_label` - HMM predictions (computed but stored)

### Derived Data (Calculated On-The-Fly)

**Centralized Calculation Functions (`controllers/gex_calculations.py`):**
All GEX metrics use centralized calculation functions to ensure consistency:
- `calculate_net_gex(strikes)` - Uses 'total' field from raw JSON
- `calculate_gex_ratio(strikes)` - Corrected ratio formula (no ×100)
- `calculate_sentiment(strikes)` - % of positive net GEX bars
- `calculate_kcs(strikes, uprice)` - Key Call Support score
- `calculate_dominance(strikes, uprice)` - Key strike dominance %
- `calculate_key_strike_stats(strikes, uprice)` - Key strike details
- `calculate_total_oi_and_vol(strikes)` - Total OI and volume
- `calculate_flip_level(strikes)` - GEX flip level calculation

**All GEX metrics are derived from raw JSON in `data` column:**
- `net_gex` - Sum of 'total' field from raw JSON data (NOT calculated as cg+pg)
- `total_call_gex`, `total_put_gex` - Sum across all strikes
- `sentiment_pct` - % of strikes with positive net GEX (0-100%)
- `gex_ratio` - Ratio of call GEX to put GEX with sign flip:
  - Positive when call GEX dominates: `call_gex / abs(put_gex)`
  - Negative when put GEX dominates: `put_gex / abs(call_gex)`
  - No ×100 multiplier (returns values like 2.2, not 218.4)
- `kcs` - Key Call Strike (highest call GEX)
- `dominance` - Key strike GEX as % of total
- `key_call_gex`, `key_put_gex` - GEX at key strike
- `key_call_oi`, `key_put_oi` - OI at key strike
- `key_call_vol`, `key_put_vol` - Volume at key strike
- `total_call_oi`, `total_put_oi` - Sum OI across all strikes
- `total_call_vol`, `total_put_vol` - Sum volume across all strikes
- `oi_ratio`, `vol_ratio` - OI/volume ratios
- `dist_to_key`, `dist_to_flip` - Distance from price to key/flip levels

**Key Architectural Decision:** No flat summary columns in `gex_strike_window`. All metrics computed on-demand from raw JSON.

---

### ML Features

**ML_FEATURES array (28 features total):**

**Original GEX features (21):**
- `net_gex`, `total_call_gex`, `total_put_gex` - Gamma exposure metrics
- `sentiment`, `gex_ratio`, `kcs`, `dominance` - Sentiment and key strike metrics
- `key_call_gex`, `key_put_gex`, `key_call_oi`, `key_put_oi`, `key_call_vol`, `key_put_vol` - Key strike data
- `total_call_oi`, `total_put_oi`, `total_call_vol`, `total_put_vol` - Total OI/volume
- `oi_ratio`, `vol_ratio` - OI/volume ratios
- `dist_to_key`, `dist_to_flip` - Distance metrics

**Price momentum features (2):**
- `price_change` - Absolute price change from previous snapshot
- `price_change_pct` - Percentage price change from previous snapshot

**Lagged GEX features (3):**
- `net_gex_change` - Change in net_gex from previous snapshot
- `sentiment_change` - Change in sentiment from previous snapshot
- `gex_ratio_change` - Change in gex_ratio from previous snapshot

**Time-of-day features (2):**
- `hour_sin` - Cyclical encoding of hour (sine)
- `hour_cos` - Cyclical encoding of hour (cosine)

**Feature Engineering:**
- Previous snapshot data is tracked during training to calculate momentum and lagged features
- Previous snapshot resets on new trading day
- For real-time predictions, momentum/lagged features default to 0 (no previous data)

---

## 3. API Endpoints

### GEX Data APIs

#### `GET /api/gex/dates`
**Purpose:** Get list of available dates with GEX data  
**Returns:** Array of date strings (YYYY-MM-DD)

#### `GET /api/gex/snapshots?date=YYYY-MM-DD`
**Purpose:** Get all snapshots for a specific date  
**Returns:** Array of snapshot objects with derived metrics

#### `GET /api/gex/session-status`
**Purpose:** Check if OptionAlpha session is fresh (<12 hours)  
**Returns:** Session status (fresh/stale/missing)

#### `GET /api/gex/capture-session`
**Purpose:** Launch Playwright browser for manual OptionAlpha login  
**Returns:** Status message (browser opens for 60 seconds)

#### `GET /api/gex/fetch-live`
**Purpose:** Fetch live GEX snapshot from OptionAlpha  
**Returns:** Live snapshot data + ML prediction

#### `POST /api/sync-historical`
**Purpose:** Sync historical GEX JSON files to database  
**Query params:** `mode` (date/datetime/timeslot/max_days), `max_days` (default 30)  
**Returns:** Sync results (added, skipped counts)

---

### ML APIs

#### `GET /ml`
**Purpose:** ML analysis page  
**Returns:** HTML page

#### `GET /api/ml/labels-summary`
**Purpose:** Get summary of ml_labels table  
**Returns:** Row counts, date range, null counts

#### `GET /api/ml/models-status`
**Purpose:** Get current ML model metadata  
**Returns:** Trained date, samples, CV accuracy, classes, features

#### `POST /api/ml/retrain`
**Purpose:** Manually retrain ML models  
**Returns:** Training results (accuracy, samples)

#### `GET /api/ml/backtest-accuracy`
**Purpose:** Run trained models over all labelled history  
**Returns:** Confusion matrices, daily accuracy, trade viability

#### `GET /api/ml/anomaly`
**Purpose:** PCA reconstruction error for anomaly detection  
**Returns:** Anomaly scores, daily chart, today's score, top anomalies

#### `GET /api/ml/predictions`
**Purpose:** Get live prediction log with outcome fill stats  
**Returns:** Last 200 predictions with ✓/✗ per model

#### `POST /api/ml/update-ohlc`
**Purpose:** Fetch SPX 5-min OHLC from yfinance + refresh ml_labels  
**Returns:** Update results

#### `POST /api/ml/rebuild-labels`
**Purpose:** Rebuild ml_labels from scratch  
**Returns:** Rebuild results

#### `GET /api/ml/trade-performance?days=N`
**Purpose:** Get historical trade performance metrics  
**Returns:** Performance records by date

#### `GET /api/ml/trade-performance-summary`
**Purpose:** Get summary of trade performance metrics  
**Returns:** Latest record + aggregated stats

#### `GET /api/ml/model-versions`
**Purpose:** Get list of model versions with performance comparison  
**Returns:** Model versions with accuracy, points, date range

#### `GET /api/ml/session-range`
**Purpose:** Session range forecast (historical distribution)  
**Query params:** `date`, `time`  
**Returns:** Range distributions, trade viability, strike selection guide

---

### Admin APIs

#### `POST /api/admin/daily-workflow`
**Purpose:** Run daily ML workflow steps  
**Request body:** `{"steps": "all|comma-separated", "force_retrain": boolean}`  
**Steps:** purge, verify, ohlc, labels, hmm, ml, signals, outcomes, performance  
**Returns:** Results for each step

#### `POST /api/admin/verify-data`
**Purpose:** Verify data integrity  
**Returns:** Verification results (currently just table count)

#### `POST /api/admin/regenerate-signals`
**Purpose:** Regenerate trade signals from corrected data  
**Returns:** Script execution results

---

### PCA API

#### `GET /api/pca`
**Purpose:** Run PCA analysis on GEX features  
**Returns:** Variance explained, feature importance, correlation heatmap

---

### HMM API

#### `POST /api/hmm/train`
**Purpose:** Retrain HMM model  
**Returns:** Training results

---

### RF Model API

#### `POST /api/rf/train`
**Purpose:** Train RandomForest trade classifier  
**Returns:** Training results

---

### Metric API

#### `GET /api/metric/history?metric=NAME`
**Purpose:** Get historical values for a metric  
**Returns:** Historical values with current context

---

### SPX API

#### `GET /api/spx/populate-open-prices`
**Purpose:** Populate SPX open prices  
**Returns:** Population results

---

## 4. Pages/Routes

### `/` - Root
**Redirects to:** `/gex`

### `/gex` - GEX Historical/Live Page
**Purpose:** View historical GEX data and live snapshots  
**Features:**
- Date picker for historical data
- Snapshot table with 22 columns
- GEX/OI/Volume charts with SPX overlay
- Capture Session button
- Fetch Live Data button
- Load Missing Historical button
- ML signal badge (after fetch)

### `/gex-admin` - GEX Admin Page
**Purpose:** Administrative functions  
**Features:** Various admin tools (legacy)

### `/gex-distribution` - GEX Distribution Page
**Purpose:** GEX distribution analysis  
**Features:** Distribution charts

### `/ml` - ML Analysis Page
**Purpose:** ML model analysis and trade signal performance  
**Tabs:**
- **Feature Analysis** (default) - PCA, feature importance, correlation heatmap
- **Outcome Tracking** - Model accuracy, confusion matrices, trade viability
- **Anomaly Detection** - PCA anomaly scores, daily charts
- **Session Range Forecast** - Historical range distributions
- **Trade Signal Performance** - Daily trade accuracy, by-trade-type accuracy, confidence calibration

**Daily Workflow Section:**
- "↻ Load Missing Historical" button
- "▶ Run Full Workflow" button
- "Force ML Retrain" checkbox

### `/analysis` - Analysis Page
**Purpose:** Analysis tools

### `/csv` - CSV Export Page
**Purpose:** Export data to CSV

### `/hscatter` - H-Scatter Page
**Purpose:** H-scatter analysis

### `/spx` - SPX Page
**Purpose:** SPX data visualization

---

## 5. Key Architectural Decisions

### 1. Raw JSON Storage (On-The-Fly Derivation)
**Decision:** `gex_strike_window` stores only raw JSON; all metrics derived on-demand  
**Rationale:** 
- Simplifies schema
- Single source of truth
- Easier to backfill/reprocess
- Trade-off: CPU vs storage (computation at query time)

### 2. HMM Trained on RTH Only
**Decision:** HMM trained only on ntime >= 935 (regular trading hours)  
**Rationale:** Pre-market data has different characteristics

### 3. Vol Regime Binary Classification
**Decision:** Collapse NORMAL and TIGHT to TIGHT during training  
**Rationale:** Model cannot reliably distinguish them; trading decision is the same

### 4. Direction at 2-Hour Horizon
**Decision:** Use 2-hour direction (not EOD) for training  
**Rationale:** Matches intraday trading style

### 5. Confidence Filtering
**Decision:** Three confidence levels: HIGH (≥0.65), MEDIUM (≥0.45), LOW (<0.45)  
**Rationale:** LOW confidence signals suppressed

### 6. Model Versioning on Force Retrain
**Decision:** Generate timestamp-based model_version when force_retrain=True  
**Rationale:** Track performance across model iterations

### 7. Paper Trading Performance
**Decision:** Assume all HIGH/MEDIUM confidence signals are "traded" for performance measurement  
**Rationale:** Measures signal quality, not actual execution

---

## 6. External Dependencies

### Python Packages
- **Flask** - Web framework
- **scikit-learn** - ML models (RandomForest, StandardScaler, PCA)
- **xgboost** - Gradient boosting for direction model (improves accuracy)
- **numpy**, **pandas** - Data manipulation
- **yfinance** - SPX OHLC data
- **Playwright** - Browser automation for OptionAlpha login
- **sqlite3** - Database (built-in)

### External Services
- **OptionAlpha** - GEX data source (via Playwright automation)
- **yfinance** - SPX OHLC data
- **OpenAI** (optional) - LLM enhancement for trade signals

---

## 7. Daily Workflow

### Pre-Market (Daily)
1. Start server: `python gex_viewer.py --port 5050`
2. Go to `/gex` → click "🔒 Capture Session" → log into OptionAlpha (60-second timeout)
3. Session status indicator goes green (✓ fresh)
4. Click "↻ Fetch Live Data" → ML signal badge appears
5. Optional: Open `/ml` → "Anomaly Detection" tab to check today's z-score
6. Repeat Fetch Live Data every 30 mins through session

### End-of-Day (Daily)
1. Next morning: Server startup auto-backfills yesterday's prediction outcomes
2. Run daily workflow: `/ml` → "▶ Run Full Workflow" with "Force ML Retrain" if needed
3. Workflow steps: verify, ohlc, labels, hmm, ml, outcomes, performance
4. Review results in Outcome Tracking and Trade Signal Performance tabs

---

## 8. Common Pitfalls & Troubleshooting

### Session Expiration
**Issue:** Session expires after ~12 hours  
**Solution:** Re-run Capture Session each morning before market open

### Browser Timeout Too Short
**Issue:** 20-second timeout insufficient for 2FA  
**Solution:** Increased to 60 seconds in `optionalpha_capture.py` and `gex_viewer.py`

### Verify Function Errors
**Issue:** Verify function queries wrong table or non-existent columns  
**Solution:** Current implementation uses simple table count check (gex_strike_window has no flat columns)

### Missing Historical Data
**Issue:** Load Historical Data fails or missing dates  
**Solution:** Run "Load Missing Historical" separately before daily workflow

### ML Direction Accuracy Poor
**Issue:** Direction accuracy ~45% (close to random)  
**Solution:** Expected behavior; rely on vol regime (74% accuracy) for trade type selection

### No Performance Data
**Issue:** Trade Signal Performance tab shows no data  
**Solution:** Requires predictions with outcomes; data accumulates over time

---

## 9. File Structure

```
optionalpha-monitor/
├── gex_viewer.py              # Main Flask application (~9600 lines)
├── gex.db                     # SQLite database
├── optionalpha_capture.py     # Playwright session capture
├── optionalpha_daily.py       # Daily data fetching
├── train_trade_classifier.py  # RandomForest training
├── requirements.txt           # Python dependencies
├── templates/
│   ├── gex.html              # GEX historical/live page
│   ├── ml.html               # ML analysis page
│   ├── analysis.html         # Analysis page
│   ├── csv.html              # CSV export
│   ├── hscatter.html         # H-scatter
│   ├── spx.html              # SPX page
│   └── ...
├── create_gex_strike_window_table.py
├── migrate_gex_strike_window_add_source.py
├── migrate_gex_strike_window_add_hmm_columns.py
├── migrate_add_ml_trade_performance.py
└── docs/
    ├── ML_SYSTEM_SUMMARY.md
    └── DESIGN_SPECIFICATION.md (this file)
```

---

## 10. Important Notes for New Sessions

### Database Queries
- **Always use `gex_strike_window`** as the primary GEX data table
- **Do NOT query flat columns** (net_gex, kcs, etc.) - they don't exist
- **Derive metrics from `data` column** using JSON parsing
- **Use `symbol='SPX'`** in queries unless working with other tickers

### GEX Calculations (Updated 2026-07-06)
- **Always use centralized functions** in `controllers/gex_calculations.py`
- **NEVER hardcode calculations** - all logic centralized to prevent inconsistencies
- **Net GEX**: Use 'total' field from raw JSON, NOT cg+pg calculation
- **GEX Ratio**: No ×100 multiplier, returns values like 2.2 not 218.4
- **API endpoints**: Must use centralized functions, no local calculations

### ML Model Training
- **Vol regime model** is reliable (70-80% accuracy expected) - Uses RandomForest
- **Direction model** improved with XGBoost + new features (2026-07-05)
- **New features:** Price momentum, lagged GEX changes, time-of-day encoding
- **Force retrain** after loading new historical data
- **Model versioning** happens automatically on force retrain

### Session Management
- **Session file:** `session.json` (Playwright cookies)
- **Session expires:** ~12 hours
- **Timeout:** 60 seconds for manual login (2FA support)

### Data Loading
- **Load Missing Historical** is separate from daily workflow
- **Run before** daily workflow when new data is needed
- **Max 30 days** by default (adjustable)

### Performance Tracking
- **Paper trading only** - assumes all signals are executed
- **Populates over time** - needs predictions with outcomes
- **Previous day** only - computes performance for yesterday's predictions

---

## 11. Version History

**2026-07-05:**
- Added help popup dialogs for PCA variance explained chart (explains PC1-PC27 with concrete GEX interpretations)
- Added help popup dialog for Feature Importance Ranking table
- Added Trade Signals Report tab to ML page with API endpoint `/api/trade-signals/performance`
- Trade Signals Report shows: outcome distribution, performance by structure, financial P&L, win rate by action
- Added help popup dialogs for all 4 Trade Signals Report sections
- Renamed "ML Trade Performance" tab to "ML Model Performance" to avoid confusion with Trade Signals Report
- Added descriptive subtitles to both tabs to clarify distinction (ML predictions vs trade signals performance)

**2026-07-04:**
- Separated "Load Missing Historical" from daily workflow
- Increased browser timeout from 20 to 60 seconds
- Added `ml_trade_performance` table for trade signal performance tracking
- Added Trade Signal Performance tab to ML page
- Fixed verify function for gex_strike_window architecture
