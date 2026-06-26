# Progress Log

## 2026-06-25

### Random Forest Model Training (Round 2)
Added missing snapshot metrics (`key2_call_vol`, `key2_put_vol`) to the RF model.

**Updated RF Model (32 features):**
- Test accuracy: 65.2%
- Cross-validation: 64.4% ± 4.0%
- **key2_call_vol** now ranks #8 in feature importance (3.94%)

**Top 10 Features:**
1. key_put_vol (6.55%)
2. key_call_gex (5.15%)
3. total_call_vol (4.64%)
4. key_net_oi (4.55%)
5. kcs (4.16%)
6. key_call_oi (4.14%)
7. key_call_vol (4.03%)
8. **key2_call_vol (3.94%)** ← new
9. dominance (3.92%)
10. total_put_vol (3.85%)

---

## Methodology

### Data Source
- **Database:** SQLite (`gex.db`)
- **Tables joined:** `trade_signals` (labels) + `gex_snapshots` (features)
- **Sample size:** 1,068 labelled trade signals (after filtering: 1,049 for binary classification)
- **Label distribution:**
  - MISSED: 344
  - CORRECT: 270
  - WIN: 235
  - LOSS: 200
  - PARTIAL: 19 (excluded from binary classification)

### Feature Engineering
**Base features (24 columns from gex_snapshots):**
- Price/GEX: `uprice`, `net_gex`, `sentiment`, `gex_ratio`, `kcs`, `dominance`
- Totals: `total_call_gex`, `total_put_gex`, `total_call_oi`, `total_put_oi`, `total_call_vol`, `total_put_vol`
- Key strike: `key_strike`, `key_call_gex`, `key_put_gex`, `key_call_oi`, `key_put_oi`, `key_call_vol`, `key_put_vol`
- Key2 strike: `key2_strike`, `key2_abs`, `key2_call_vol`, `key2_put_vol`
- Other: `flip`, `hmm_state`

**Derived features (6 calculated metrics):**
- `net_oi` = total_call_oi - total_put_oi
- `net_vol` = total_call_vol - total_put_vol
- `key_net_gex` = key_call_gex - key_put_gex
- `key_net_oi` = key_call_oi - key_put_oi
- `dist_to_key` = |uprice - key_strike|
- `dist_to_flip` = |uprice - flip|

**Total features:** 30 (24 base + 6 derived)

### Target Variable
Binary classification task:
- **Class 1 (WIN):** `outcome` = 'WIN' or 'CORRECT'
- **Class 0 (LOSS):** `outcome` = 'LOSS' or 'MISSED'
- **Excluded:** 'PARTIAL' outcomes (19 samples)
- **Final distribution:** 544 LOSS, 505 WIN

### Train/Test Split
- **Split ratio:** 80% train / 20% test
- **Stratification:** Yes (preserves class balance)
- **Random state:** 42 (reproducible)
- **Train samples:** 839
- **Test samples:** 210

### Preprocessing
- **Scaler:** StandardScaler (zero mean, unit variance)
- **NaN handling:** Fill with 0
- **Feature scaling:** Fit on training data, transform test data

### Model Configuration
**Random Forest Classifier (sklearn):**
- `n_estimators`: 100 trees
- `max_depth`: 10 (limits overfitting)
- `min_samples_split`: 10
- `min_samples_leaf`: 5
- `random_state`: 42
- `class_weight`: 'balanced' (handles class imbalance)

### Evaluation Metrics
- **Training accuracy:** 92.7%
- **Test accuracy:** 65.2%
- **Cross-validation:** 5-fold CV, mean 64.4% ± 4.0%
- **Classification report:**
  - LOSS precision: 0.65, recall: 0.71, f1: 0.68
  - WIN precision: 0.65, recall: 0.59, f1: 0.62

### Components Used
**Python libraries:**
- `sqlite3` - Database access
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `sklearn.ensemble.RandomForestClassifier` - ML model
- `sklearn.model_selection.train_test_split` - Data splitting
- `sklearn.model_selection.cross_val_score` - CV evaluation
- `sklearn.preprocessing.StandardScaler` - Feature scaling
- `sklearn.metrics.classification_report` - Performance metrics
- `joblib` - Model persistence

**Files:**
- `train_trade_classifier.py` - Training script
- `gex.db` - SQLite database
- `trade_rf_model.pkl` - Saved model
- `trade_rf_scaler.pkl` - Saved scaler

**Files updated (Round 2):**
- `train_trade_classifier.py` - Added `key2_call_vol`, `key2_put_vol` to query and feature columns
- `gex_viewer.py` - Added `key2_call_vol`, `key2_put_vol` to `_prepare_rf_features()`

---

**Next:** LLM narrative enhancement with OpenAI API (pending)

## 2026-06-26

### Hybrid Decision Implementation
Implemented Option 2 (Hybrid Decision) to combine rule-based classification with RF predictions.

**Logic:**
- Rule-based classification determines initial trade action (IRON_BUTTERFLY, SHORT_PUT_SPREAD, etc.)
- RF prediction provides WIN/LOSS probability
- If RF predicts LOSS and rule-based action is not STAY_OUT → override to STAY_OUT
- If RF predicts WIN → keep rule-based action
- If rule-based action is STAY_OUT → always STAY_OUT

**New fields in signal output:**
- `rf_override`: Boolean flag indicating when RF overrode rule-based decision
- `rule_based_action`: Original rule-based action before RF override
- Updated `rationale`: Explains RF override when it occurs
- Updated `structure`: Shows "No Trade (RF Override)" when overridden

**Files updated:**
- `gex_viewer.py` - Modified `_generate_trade_signal()` to implement hybrid decision logic

### Distribution Tab Fix
Fixed two issues with the distribution tab (pre-market snapshots):

**Issue 1: Duplicate rows for 2026-06-26 03:42**
- `live_captures` table had 2 identical rows for timestamp 342
- **Fix:** Added UNIQUE constraint on `(ndate, ntime)` and changed INSERT to `INSERT OR REPLACE`
- Migration added to remove existing duplicates and create unique index

**Issue 2: Missing data for 2026-06-25 pre-market (07:51, 05:28)**
- Pre-market snapshots had `net_gex=0.0`, `kcs=0.0` because GEX data isn't available pre-market
- This is expected behavior — pre-market data has limited/no GEX information
- No fix needed; this is data limitation, not a bug

**Files updated:**
- `gex_viewer.py` - Added UNIQUE constraint migration to `_ensure_live_captures_table()`
- `gex_viewer.py` - Changed INSERT to INSERT OR REPLACE in two locations

### Flat Summary Calculation Fix
Fixed missing data for RTH snapshots (10:00, 10:01, 10:32, 10:58, 11:35 on 2026-06-25).

**Root cause:**
- `_compute_flat_summary()` expected `data` to be a dict with a "data" key
- Historical snapshots stored data as a direct list in the `data` column
- When `data.get("data")` was called on a list, it returned `None`, causing summary calculation to fail
- Result: `net_gex=0.0, kcs=0.0` for affected snapshots

**Fix:**
- Updated `_compute_flat_summary()` to handle both dict with "data" key and direct list
- Created backfill script to re-calculate flat columns for affected RTH snapshots
- Backfilled 5 snapshots with correct values

**Files updated:**
- `gex_viewer.py` - Modified `_compute_flat_summary()` to handle list input
- `backfill_flat_summary.py` - Created backfill script for affected snapshots

**Backfill results:**
- 10:00: net_gex=-8,730,480,645, kcs=5.5
- 10:01: net_gex=-8,744,543,917, kcs=4.8
- 10:32: net_gex=-1,209,937,949, kcs=3.2
- 10:58: net_gex=-691,207,536, kcs=2.8
- 11:35: net_gex=-3,108,350,870, kcs=4.2

### HMM Regime Integration
Added HMM regime (hmm_label) as a feature to the RF model to integrate ML components.

**Implementation:**
- Added `hmm_label` from `trade_signals.regime` to training query
- One-hot encoded 5 regime categories: Positive Stable, Positive Weakening, Negative Trending, Negative Volatile, Unknown
- Updated `_prepare_rf_features()` in `gex_viewer.py` to match training feature order
- Retrained RF model with 36 features (30 original + 5 HMM one-hot + 1 derived)

**Results:**
- Test accuracy: 61.4% (down from 65.2%)
- Cross-validation: 64.5% ± 3.0% (similar to previous 64.4% ± 4.0%)
- HMM regime features did not appear in top 10 feature importances

**Top 10 Features (with HMM):**
1. key_put_vol (7.33%)
2. key_net_oi (4.91%)
3. key_call_oi (4.44%)
4. key_call_vol (4.34%)
5. total_call_vol (4.27%)
6. key2_call_vol (4.22%)
7. key_call_gex (4.16%)
8. kcs (3.86%)
9. net_vol (3.74%)
10. key_put_gex (3.68%)

**Analysis:**
HMM regime features did not significantly improve prediction accuracy. The regime information may already be captured by the existing GEX features (net_gex, kcs, sentiment, etc.). The slight decrease in test accuracy could be due to the added complexity without predictive value.

**Decision:** Reverted to 30-feature model (without HMM regime).

**Files updated:**
- `train_trade_classifier.py` - Added hmm_label to query and one-hot encoding
- `gex_viewer.py` - Updated `_prepare_rf_features()` to handle HMM regime features
- `trade_rf_model.pkl` - Retrained model saved
- `trade_rf_scaler.pkl` - Retrained scaler saved

### HMM Regime Revert
Reverted RF model to 30-feature version after HMM regime features showed no improvement.

**Results after revert:**
- Test accuracy: 66.2% (restored to original level)
- Cross-validation: 64.1% ± 3.7%
- Total features: 31 (24 base + 6 derived + 1 hmm_state)

**Files updated:**
- `train_trade_classifier.py` - Removed hmm_label from query and one-hot encoding
- `gex_viewer.py` - Removed HMM regime one-hot encoding from `_prepare_rf_features()`
- `trade_rf_model.pkl` - Retrained with 30 features
- `trade_rf_scaler.pkl` - Retrained with 30 features

### RF Retraining Strategy
Created comprehensive guide for retraining the RF model as new snapshots arrive.

**Key recommendations:**
- **Retrain weekly** (every Friday after market close)
- Minimum 500 labelled samples (currently 1,049)
- Monitor test accuracy (>60% target) and CV variance (<5%)
- Keep model backups for rollback

**Document created:**
- `RF_RETRAINING_GUIDE.md` - Complete guide covering:
  - When to retrain (weekly schedule, trigger-based)
  - How to retrain (step-by-step process)
  - Data requirements (sample size, label distribution)
  - Performance monitoring (daily/weekly metrics)
  - Rollback procedure
  - Troubleshooting common issues

---

**Next:** LLM narrative enhancement with OpenAI API (pending)
