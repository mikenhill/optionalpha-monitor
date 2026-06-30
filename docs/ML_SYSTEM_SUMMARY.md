# ML System Summary
**Date:** 2026-06-30  
**Branch merged to:** `master`  
**Primary file:** `gex_viewer.py` | **ML page:** `templates/ml.html` | **GEX badge:** `templates/gex.html`

---

## What Was Built

### 1. Feature Extraction (`_extract_gex_features`)
- Extracts **21 GEX features** from raw strike window data per snapshot
- Features span: net GEX, call/put GEX totals, key strike stats (GEX/OI/Vol at key and secondary key strikes), OI/Vol ratios, sentiment, GEX ratio, KCS, dominance, distance-to-key, distance-to-flip
- Used as input to all ML models and the anomaly detector
- Lives in `gex_viewer.py` as `_extract_gex_features(strikes, uprice) → dict`

### 2. Multi-Horizon Labels (`ml_labels` table)
- Every historical GEX snapshot is labelled with outcomes at multiple time horizons
- Labels are derived by joining `gex_strike_window` to `spx_ohlc_5min` (5-min SPX OHLC bars)
- **Columns added:**
  - `range_regime` — TIGHT / NORMAL / WIDE (EOD range vs rolling median × 0.7 / 1.4 thresholds)
  - `direction_1hr` / `direction_2hr` — UP / FLAT / DOWN (thresholds: ±0.15% at 1hr, ±0.20% at 2hr)
  - `pct_1hr` / `pct_2hr` — % SPX move from snapshot to horizon
  - `range_1hr` / `range_2hr` — high-low range in points over horizon window
  - `flip_held_1hr` / `flip_held_2hr` — 1 if SPX stayed same side of GEX flip level
  - `trade_viable_ic` — 1 if IC viable (range_2hr < 30pts AND flip_held_2hr)
  - `trade_viable_sps` — 1 if Short Put Spread viable (pct_2hr > 0.10%)
  - `trade_viable_scs` — 1 if Short Call Spread viable (pct_2hr < -0.10%)
  - `trade_viable_lcs` — 1 if Long Call Spread viable (pct_2hr > 0.35%)
  - `trade_viable_lps` — 1 if Long Put Spread viable (pct_2hr < -0.35%)
- Populated by `scripts/rebuild_ml_labels.py` for history; updated live in `_ensure_ml_labels_current()`
- SPX OHLC data fetched from `yfinance` via `/api/ml/update-ohlc`

### 3. Vol Regime Model (`vol_regime`)
- **Algorithm:** RandomForest (200 trees, max_depth=8, class_weight='balanced')
- **Target:** Binary — **WIDE** (dangerous, high-vol day) vs **TIGHT** (safe to sell premium)
  - NORMAL and TIGHT are collapsed to TIGHT during training — the model cannot reliably distinguish them and the trading decision is the same
- **Training data:** All `gex_strike_window` rows joined to `ml_labels` where `direction_2hr IS NOT NULL`
- **Key decision:** Use `direction_2hr` (not `direction_eod`) to match intraday trading style
- **Storage:** Serialised pickle blob in `ml_models` table (model + scaler + feature list)
- **Cross-validated accuracy:** ~92% (in-sample — expect ~70-80% out-of-sample)

### 4. Direction Model (`direction`)
- **Algorithm:** Same RandomForest config as above
- **Target:** UP / FLAT / DOWN at **2-hour horizon** (thresholds ±0.20%)
- **In-sample confusion matrix (after fixes):**
  - UP: ~99% correct
  - FLAT: ~88% correct
  - DOWN: ~93% correct
- **Caveat:** These are in-sample numbers; accumulate 2-4 weeks of live predictions before trusting

### 5. Trade Recommendation Matrix (`_TRADE_MATRIX`)
Maps `(vol_regime, direction)` → trade type:

| Vol Regime | Direction | Trade | Code |
|-----------|-----------|-------|------|
| TIGHT | NEUTRAL / FLAT | Iron Condor | IC |
| TIGHT | UP | Short Put Spread | SPS |
| TIGHT | DOWN | Short Call Spread | SCS |
| WIDE | NEUTRAL | Iron Butterfly | IB |
| WIDE | UP | Long Call Spread | LCS |
| WIDE | DOWN | Long Put Spread | LPS |

### 6. Confidence Filtering
- `min_conf = min(vol_regime_proba, direction_proba)`
- **HIGH:** ≥ 0.65 — trade recommended, shown in green
- **MEDIUM:** ≥ 0.45 — trade recommended, shown in amber
- **LOW:** < 0.45 — **trade suppressed**, badge shows "Low confidence — no trade" in grey
- Only HIGH/MEDIUM signals include the historical viable rate

### 7. Historical Viable Rate on Badge
- Each trade code maps to a `trade_viable_*` column in `ml_labels`
- The badge shows e.g. `Iron Condor ●●●  35.8% hist viable`
- Computed live from `AVG(trade_viable_ic)` across all non-null rows in `ml_labels`
- Gives immediate context: "this trade type worked X% of the time historically under these conditions"

### 8. Live Prediction Saving (`ml_predictions` table)
- Every `Fetch Live Data` call saves a prediction row: `(ndate, ntime, vol_regime, direction, trade_code, confidence, vol_proba, dir_proba)`
- On server startup, `_backfill_prediction_outcomes()` runs and fills in actuals for any predictions from prior days where `outcome_filled_at IS NULL`
- Outcome columns: `vol_correct`, `direction_1hr_correct`, `direction_2hr_correct`, `trade_viable`

### 9. GEX Page Badge
- Appears in the toolbar after every `Fetch Live Data`
- **HIGH/MEDIUM:** coloured signal text + historical viable rate pill + detail bar (vol %, dir %, trade, confidence, link to `/ml`)
- **LOW:** dimmed grey text, no trade, no detail bar
- Session status shown next to Capture Session button (green = fresh <12h, amber = stale, red = missing)

---

## ML Page (`/ml`) — Tabs

### Feature Analysis Tab (default)
- PCA across all 27 GEX features
- Variance explained by PC chart
- Feature importance ranking (weighted loading across PCs capturing 90% variance)
- Correlation heatmap + high-correlation pairs table (|r| > 0.70)
- HMM current features panel

### Outcome Tracking Tab
**How to read it:**
- **Model Status card** — trained date, sample count, cross-validated accuracy, classes. Use **↻ Retrain Models** after adding new data or changing label logic. Retraining takes ~10s and auto-reloads the tab.
- **Headline stats** — labelled snapshots, vol regime accuracy %, direction accuracy %, trade viable %
- **Vol Regime Accuracy Over Time** — daily % correct for WIDE/TIGHT prediction. Dotted line = 33% random baseline.
- **Direction Accuracy Over Time** — daily % correct for UP/FLAT/DOWN at 2hr. Dotted line = 33% baseline.
- **Vol Regime Confusion Matrix** — rows = actual, cols = predicted. Diagonal = correct. After the binary collapse fix, only TIGHT and WIDE rows appear.
- **Direction Confusion Matrix** — same layout for direction. Watch for off-diagonal errors (e.g. UP predicted as DOWN = dangerous).
- **Trade Viability Bar Chart** — for HIGH/MEDIUM confidence signals only, what % of the time did the recommended trade actually work? Green ≥ 50%, amber ≥ 35%, red < 35%.
- **Predictions Log** — last 200 labelled snapshots with ✓/✗ per model and 2hr SPX move %. Most recent at top.

### Anomaly Detection Tab
**How to read it:**
- **Headline stats** — snapshots scanned, PCA components used (retaining 95% variance), how many snapshots scored UNUSUAL or EXTREME
- **Today's Score** — large coloured number (z-score relative to historical mean). Green = NORMAL, amber = UNUSUAL (z ≥ 2), red = EXTREME (z ≥ 3). Includes plain-English interpretation:
  - NORMAL: "Today's GEX structure is within historical norms. No structural anomaly."
  - UNUSUAL: "Today's GEX structure is unusual vs history. Exercise caution with high-conviction trades."
  - EXTREME: "Extreme structural anomaly. Today's GEX is highly unusual — avoid complex positions."
- **Daily Anomaly Bar Chart** — colour-coded bars (blue/amber/red) with UNUSUAL and EXTREME threshold lines. Shows which historical days had unusual GEX structure.
- **Distribution Histogram** — how spread z-scores are across all history. Healthy distribution is centred near 0 with a long right tail.
- **Top 10 Most Anomalous Snapshots** — specific date/time of the worst anomalies. Cross-reference with what actually happened those days (e.g. FOMC, CPI, flash crashes) to validate the detector.
- **Pre-market use:** After each morning's first `Fetch Live Data`, check this tab. If today scores UNUSUAL or EXTREME, the model is saying today's GEX has no close historical parallel — treat any trade signal with extra caution regardless of confidence level.

---

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/gex/capture-session` | Launch Playwright browser for manual OA login → saves `session.json` |
| `GET /api/gex/session-status` | Check `session.json` age and freshness |
| `GET /api/gex/fetch-live` | Capture live GEX snapshot → saves to `gex_strike_window`, runs ML prediction, saves to `ml_predictions` |
| `GET /api/ml/update-ohlc` | Fetch SPX 5-min OHLC from yfinance + refresh `ml_labels` |
| `GET /api/ml/retrain` | Manually retrain Vol Regime + Direction models |
| `GET /api/ml/models-status` | Model metadata (trained date, samples, CV accuracy, classes) |
| `GET /api/ml/backtest-accuracy` | Run trained models over all labelled history → confusion matrices, daily accuracy, trade viability |
| `GET /api/ml/anomaly` | PCA reconstruction error for all snapshots → anomaly scores, daily chart, today's score |
| `GET /api/ml/predictions` | Live prediction log with outcome fill stats |
| `GET /api/ml/labels-summary` | `ml_labels` row counts and date range |

---

## Key DB Tables

| Table | Contents |
|-------|---------|
| `gex_strike_window` | Raw 40-strike GEX window per snapshot (source='gex') |
| `ml_labels` | Snapshot-level outcome labels (range_regime, direction_2hr, trade_viable_*, etc.) |
| `ml_models` | Trained model blobs (RandomForest + StandardScaler pickled) |
| `ml_predictions` | Live predictions with outcomes backfilled on startup |
| `spx_ohlc_5min` | 5-min SPX OHLC bars used for label calculation |

---

## Daily Workflow (Pre-Market)

1. Start server: `python gex_viewer.py --port 5050`
2. Go to `/gex` → click **🔒 Capture Session** → log into OptionAlpha → wait 20s for browser to close
3. Session status indicator goes green (✓ fresh)
4. Click **↻ Fetch Live Data** → ML signal badge appears in toolbar
5. Open `/ml` → **Anomaly Detection** tab — check today's z-score
6. If NORMAL: proceed with the trade signal from the badge
7. If UNUSUAL/EXTREME: treat all signals with extra caution
8. Repeat Fetch Live Data every 30 mins through the session
9. Next morning: startup auto-backfills yesterday's prediction outcomes

---

## How to Rebuild From Scratch

1. **Install dependencies:** `pip install flask scikit-learn numpy pandas yfinance playwright`
2. **Install Playwright browsers:** `playwright install chromium`
3. **Import SPX OHLC:** `python scripts/import_spx_ohlc.py`
4. **Rebuild ML labels:** `python scripts/rebuild_ml_labels.py`
5. **Start server:** `python gex_viewer.py --port 5050`
6. **Fetch OHLC + refresh labels:** `/ml` → Data Status → **↻ Update from yfinance**
7. **Train models:** `/ml` → Outcome Tracking → **↻ Retrain Models**
8. **Verify:** Outcome Tracking tab should show >85% vol regime accuracy and >60% direction accuracy in-sample

---

## Known Caveats

- In-sample accuracy (87-99%) will be lower out-of-sample — expect ~70-80% after 2-4 weeks of live data
- NORMAL days are collapsed to TIGHT for training — the model cannot distinguish moderate-range days from tight-range days
- `ml_predictions` table populates only from live `Fetch Live Data` clicks, not from historical backfill
- Anomaly detection is unsupervised — high z-score means structurally unusual, not necessarily dangerous; validate top anomalies against known market events
- Session expires after ~12h — re-run Capture Session each morning before market open
