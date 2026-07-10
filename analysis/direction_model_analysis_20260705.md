# Direction Model Analysis - 2026-07-05

## Current Performance
- **Direction Model Accuracy**: 45.05% (poor, close to random for 3-class)
- **Vol Regime Model Accuracy**: 74.95% (good)

## Root Cause Analysis

### Feature Mismatch
GEX features work well for vol_regime (74.95%) but not direction (45.05%).
- Gamma exposure predicts volatility/squeeze risk, not directional price movement
- Current features are options-flow based, not price/momentum based

### Label Distribution (Highly Imbalanced)
```
direction_1hr: FLAT 57.9%, DOWN 21.7%, UP 20.4% (total 1236)
direction_2hr: FLAT 57.7%, DOWN 21.9%, UP 20.4% (total 990)
direction_eod: FLAT 51.0%, DOWN 25.1%, UP 23.9% (total 1360)
```

### Feature Importance (All Low)
All 18 GEX features have similar low importance (0.02-0.06):
- net_gex: 0.0616
- total_call_oi: 0.0609
- total_call_gex: 0.0574
- ... (all similar, none stand out)

This indicates none of the current GEX features are predictive of direction.

## Recommended Improvements

### 1. Add Price/Momentum Features (Highest Priority)
Direction requires price action features:
- Recent price changes (5min, 15min, 30min, 1hr)
- RSI or MACD momentum indicators
- Distance from key levels as percentage
- Time-of-day features (market microstructure)
- SPX price vs key strike ratio

### 2. Change Time Horizon
- `direction_eod` has better class balance (51% FLAT vs 58% for 2hr)
- EOD may be more predictable due to trend persistence

### 3. Binary Classification
- Convert to UP vs DOWN (exclude FLAT cases)
- Simpler 2-class problem, removes noise from sideways movement

### 4. Model Architecture Changes
- Try XGBoost or LightGBM (better for tabular data)
- Increase model complexity (current max_depth=8 may be too shallow)
- Add feature interaction terms

### 5. Feature Engineering
- Create rolling averages of GEX metrics
- Add lagged features (previous snapshot values)
- Combine GEX with price momentum

## Next Steps
Recommend starting with #1 (adding price features) as this addresses the fundamental issue.
