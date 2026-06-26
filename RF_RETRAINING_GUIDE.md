# Random Forest Model Retraining Guide

## Overview
The Random Forest (RF) model predicts trade outcomes (WIN/LOSS) based on GEX snapshot features. This guide explains when and how to retrain the model as new data arrives.

## Current Model Status
- **Features:** 31 (24 base + 6 derived + 1 hmm_state)
- **Training samples:** 1,049 labelled trade signals
- **Test accuracy:** 66.2%
- **Cross-validation:** 64.1% ± 3.7%
- **Model file:** `trade_rf_model.pkl`
- **Scaler file:** `trade_rf_scaler.pkl`

## When to Retrain

### Recommended Schedule: Weekly
Retrain **weekly** (e.g., every Friday after market close) for the following reasons:

1. **Sufficient new data:** Weekly adds ~20-30 new labelled samples (assuming 4-5 trading days with 4-6 signals/day)
2. **Balanced stability:** Frequent enough to adapt to changing market conditions, but not so frequent that it overfits to recent noise
3. **Practical workflow:** Allows time to evaluate performance before deploying

### Alternative Schedules

| Schedule | Pros | Cons |
|----------|------|------|
| **Daily** | Most adaptive | High computational cost, risk of overfitting to recent noise |
| **Weekly** (recommended) | Good balance, practical | May lag behind rapid regime changes |
| **Monthly** | Stable, low cost | May miss shorter-term regime shifts |
| **On-demand** | Only when needed | Requires manual monitoring of performance degradation |

### Trigger-Based Retraining
Consider retraining immediately if:
- Test accuracy drops below 60% for 3 consecutive days
- Feature importance distribution shifts significantly
- Market regime changes (e.g., high volatility period begins)

## How to Retrain

### Step 1: Ensure New Data is Labelled
New snapshots must have trade signals with outcomes assigned before retraining.

```bash
# Check for new unlabelled signals
python -c "import sqlite3; con = sqlite3.connect('gex.db'); print(con.execute('SELECT COUNT(*) FROM trade_signals WHERE outcome IS NULL').fetchone()[0])"
```

If there are unlabelled signals, run the backfill script to assign outcomes:
```bash
python backfill_trade_signals.py
```

### Step 2: Retrain the Model
```bash
python train_trade_classifier.py
```

This will:
1. Load all labelled trade signals from `trade_signals` table
2. Join with `gex_snapshots` to get features
3. Train RF classifier with 80/20 train/test split
4. Save model to `trade_rf_model.pkl`
5. Save scaler to `trade_rf_scaler.pkl`

### Step 3: Evaluate Performance
Review the output:
- **Training accuracy:** Should be >90% (indicates model can learn patterns)
- **Test accuracy:** Should be >60% (indicates generalization)
- **Cross-validation:** Should be >60% with low variance (<5%)
- **Classification report:** Check precision/recall balance

If performance degrades significantly (>5% drop), investigate:
- Data quality issues (missing labels, incorrect outcomes)
- Feature distribution shifts (market regime change)
- Overfitting (reduce max_depth or increase min_samples_split)

### Step 4: Deploy the New Model
The Flask app loads the model on startup. Restart the server:

```bash
# Stop existing server (Ctrl+C or kill process)
# Then restart
python gex_viewer.py --port 5050
```

## Data Requirements

### Minimum Sample Size
- **Absolute minimum:** 500 labelled samples (250 WIN, 250 LOSS)
- **Recommended:** 1,000+ labelled samples
- **Current:** 1,049 samples (544 LOSS, 505 WIN)

### Label Distribution
Aim for balanced classes (within 60/40 ratio):
- If WIN > 70% or LOSS > 70%, consider:
  - Collecting more data from underrepresented class
  - Adjusting `class_weight` parameter in training script
  - Using stratified sampling

### Feature Completeness
All 31 features must be present for each sample:
- Base features (24): uprice, net_gex, sentiment, gex_ratio, kcs, dominance, etc.
- Derived features (6): net_oi, net_vol, key_net_gex, key_net_oi, dist_to_key, dist_to_flip
- HMM state (1): hmm_state

## Performance Monitoring

### Daily Checks
After each trading day, check:
1. **RF prediction accuracy:** Compare RF predictions vs actual outcomes for that day
2. **Override rate:** What % of rule-based signals were overridden by RF?
3. **Override effectiveness:** Did RF overrides improve outcomes?

### Weekly Review
At retraining time, review:
1. **Feature importance drift:** Are top features changing?
2. **Accuracy trend:** Is test accuracy stable or declining?
3. **Class balance:** Are WIN/LOSS ratios staying balanced?

### Metrics to Track
```python
# Example: Calculate daily RF accuracy
import sqlite3
con = sqlite3.connect('gex.db')
# Query signals with RF predictions and outcomes
# Compare rf_prediction vs outcome
# Calculate accuracy
```

## Rollback Procedure

If a new model performs worse:

1. **Restore previous model:**
```bash
# Keep backups of previous models
cp trade_rf_model.pkl trade_rf_model_backup.pkl
cp trade_rf_scaler.pkl trade_rf_scaler_backup.pkl
```

2. **Investigate root cause:**
- Check for data quality issues
- Verify feature calculation logic
- Review market conditions during new data period

3. **Revert to previous model:**
```bash
cp trade_rf_model_backup.pkl trade_rf_model.pkl
cp trade_rf_scaler_backup.pkl trade_rf_scaler.pkl
# Restart server
```

## Automation (Optional)

### Scheduled Retraining (Windows Task Scheduler)
Create a scheduled task to run weekly:
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Weekly on Friday at 6:00 PM
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `train_trade_classifier.py`
   - Start in: `G:\My Drive\Colab Notebooks\optionalpha-monitor`

### Automated Performance Monitoring
Create a script to check daily accuracy and alert if degradation detected:
```python
# monitor_rf_performance.py
# - Calculate daily RF accuracy
# - Compare to threshold (e.g., 60%)
# - Send alert if below threshold
```

## Troubleshooting

### Issue: Test accuracy drops significantly
**Possible causes:**
- New data from different market regime
- Data quality issues (incorrect labels)
- Feature calculation bug

**Solutions:**
- Investigate market conditions during new data period
- Audit new labels for correctness
- Verify feature calculations match training

### Issue: Training accuracy high, test accuracy low
**Possible causes:**
- Overfitting to training data
- Training/test data not representative

**Solutions:**
- Reduce `max_depth` parameter (e.g., from 10 to 8)
- Increase `min_samples_split` (e.g., from 10 to 15)
- Ensure train/test split is stratified

### Issue: Feature importance changes dramatically
**Possible causes:**
- Market regime shift
- Data source changes
- Feature calculation error

**Solutions:**
- Compare feature distributions between old and new data
- Verify data source hasn't changed
- Check for bugs in feature calculation

## References

- **Training script:** `train_trade_classifier.py`
- **Model file:** `trade_rf_model.pkl`
- **Scaler file:** `trade_rf_scaler.pkl`
- **Progress log:** `PROGRESS_LOG.md`
