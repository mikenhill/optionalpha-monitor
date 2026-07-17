# Bocca Gap Bot Analysis

**Date:** 2026-07-17  
**Analysis script:** `bocca_gap_analysis.py`  
**Chart:** `bocca_gap_analysis.png`

---

## Bot Configuration (v13)

| Setting | Value |
|---|---|
| **Strategy** | 0DTE Iron Condor on SPX |
| **Entry time** | ~13:45 ET (scanner wakeup) |
| **Entry criteria** | Gap >= 0.1%, VIX 0-24, market closes at 4PM |
| **Short put** | $5 below underlying price |
| **Long put** | $5 below short put |
| **Short call** | (implied from IC) $5 above underlying |
| **Long call** | $5 above short call |
| **Wing width** | $5 each side |
| **IC width** | 10 pts (short put to short call) |
| **RWR filter** | 100 |
| **Price** | 100% of bid/ask, $0.10 from mid |
| **Exit** | 40% profit target, 90% stop loss |
| **Expiry** | Same day (0DTE) |

**Logic:** On gap-up days with low VIX, sell a tight iron condor centered around SPX price at 13:45 ET, betting the afternoon stays range-bound within ~5 pts of entry.

---

## Performance Summary

| Metric | Value |
|---|---|
| **Total Trades** | 48 |
| **Wins** | 25 |
| **Losses** | 23 |
| **Win Rate** | 52.1% |
| **Total P&L** | +$1,405 |
| **Avg Win** | +$204 |
| **Avg Loss** | -$161 |
| **Avg Premium** | $322 |
| **Date Range** | 2026-04-13 to 2026-07-15 |

---

## Breach Analysis

- **Put side breached on loss days:** 21 of 23 losses
- **Call side breached on loss days:** 2 of 23 losses
- **Primary loss side: PUT** — the market sells off through the short put

### Losing Trade Detail

| Date | Side | Breach Depth | PM Range | Gap % | P&L |
|---|---|---|---|---|---|
| 2026-07-10 | PUT | 51.8 pts | 14.0 | +0.10% | -$240 |
| 2026-06-26 | PUT | 29.3 pts | 37.7 | +0.06% | -$120 |
| 2026-06-15 | PUT | 24.1 pts | 20.5 | +1.48% | -$205 |
| 2026-06-11 | PUT | 112.7 pts | 74.3 | +0.51% | -$125 |
| 2026-05-26 | CALL | 29.1 pts | 20.8 | +0.80% | -$175 |
| 2026-05-22 | PUT | 28.1 pts | 26.4 | +0.29% | -$160 |
| 2026-05-21 | PUT | 60.5 pts | 45.9 | -0.50% | -$63 |
| 2026-05-20 | PUT | 30.4 pts | 21.2 | +0.46% | -$170 |
| 2026-05-19 | PUT | 51.3 pts | 47.6 | -0.78% | -$135 |
| 2026-05-18 | PUT | 26.8 pts | 52.9 | +0.14% | -$145 |
| 2026-05-15 | PUT | 35.3 pts | 50.2 | -0.83% | -$145 |
| 2026-05-12 | PUT | 26.5 pts | 41.4 | -0.48% | -$170 |
| 2026-05-11 | PUT | 22.4 pts | 25.6 | +0.23% | -$235 |
| 2026-05-06 | PUT | 12.5 pts | 26.0 | +0.91% | -$225 |
| 2026-05-01 | PUT | 15.7 pts | 24.7 | +0.84% | -$225 |
| 2026-04-30 | PUT | 45.8 pts | 30.1 | +0.07% | -$150 |
| 2026-04-29 | PUT | 12.1 pts | 30.7 | -0.02% | -$120 |
| 2026-04-28 | PUT | 9.8 pts | 14.1 | -0.52% | -$70 |
| 2026-04-23 | PUT | 8.4 pts | 39.4 | -0.08% | -$40 |
| 2026-04-22 | PUT | 7.6 pts | 22.4 | +0.89% | -$205 |
| 2026-04-21 | PUT | 34.8 pts | 52.2 | +0.25% | -$135 |
| 2026-04-15 | PUT | 15.0 pts | 30.5 | +0.33% | -$225 |
| 2026-04-13 | PUT | 25.9 pts | 41.9 | +0.01% | -$220 |

**Note:** Several losses occurred on days with gap < 0.1% (negative gaps). These were pre-v13 config — the gap >= 0.1% filter was added later and should eliminate these.

---

## Winning vs Losing Days Comparison

| Feature | Wins (mean) | Losses (mean) | Delta |
|---|---|---|---|
| **PM range** | 18.8 pts | 34.4 pts | +15.6 |
| **Day range** | 45.9 pts | 59.9 pts | +14.0 |
| **AM range** | 42.9 pts | 49.0 pts | +6.1 |
| **Range expansion** | 0.48 | 0.77 | +0.30 |
| **PM avg bar range** | 4.24 | 5.53 | +1.29 |
| **Avg bar range** | 5.16 | 6.17 | +1.01 |
| **Gap %** | 0.29% | 0.18% | -0.11 |
| **Trend continuation** | 0.56 | 0.39 | -0.17 |
| **IC width** | 10.0 | 10.0 | 0.0 |

**The IC width is always 10 pts. Losses occur when PM range far exceeds this.**

---

## PM Range vs IC Width

| Metric | Wins | Losses |
|---|---|---|
| **Avg PM range** | 18.8 pts | 34.4 pts |
| **IC width** | 10.0 pts | 10.0 pts |
| **PM range / IC width** | 1.88x | **3.44x** |

Days where PM range > IC width: **47 of 48 trades** (essentially always). The PM range almost always exceeds 10 pts. What saves winning trades is that the price stays near the entry point — the range occurs around the IC, not through it directionally.

---

## HMM Regime Analysis (4 States)

| State | Days | Avg Day Range | Avg Bar Range | Avg Gap% | Avg PM Range |
|---|---|---|---|---|---|
| 0 (Calm) | 163 | 34.3 pts | 3.81 | +0.15% | 19.0 pts |
| 3 (Normal) | 151 | 57.4 pts | 6.83 | +0.05% | 32.3 pts |
| 1 (Volatile) | 67 | 106.9 pts | 9.80 | -0.22% | 59.4 pts |
| 2 (Crisis) | 3 | 375.2 pts | 23.62 | +2.00% | 138.0 pts |

### Win Rate by HMM State

| State | Trades | Win Rate | Avg P&L | Avg Day Range |
|---|---|---|---|---|
| **0 (Calm)** | 19 | **57.9%** | +$46 | 40 pts |
| **3 (Normal)** | 25 | 52.0% | +$32 | 55 pts |
| **1 (Volatile)** | 4 | **25.0%** | -$69 | **96 pts** |

**Key finding:** HMM State 1 (high-vol days with avg day range 97 pts) has only 25% win rate. The 10pt IC cannot survive these days.

---

## ML Feature Importance

### Random Forest (CV Accuracy: 60.0% vs 53.2% baseline)

| Feature | Importance |
|---|---|
| **range_expansion** | 0.2251 |
| rolling_wr | 0.1254 |
| rolling_pm_range | 0.1159 |
| pm_avg_bar_range | 0.0985 |
| close_position | 0.0774 |
| avg_bar_range | 0.0768 |
| am_return | 0.0716 |
| prev_pnl | 0.0678 |
| am_range | 0.0664 |
| gap_pct | 0.0571 |
| consec_losses | 0.0179 |
| ic_width | 0.0000 |

### Gradient Boosting (CV Accuracy: 66.2% vs 53.2% baseline)

| Feature | Importance |
|---|---|
| **range_expansion** | **0.4144** |
| prev_pnl | 0.2108 |
| rolling_wr | 0.1112 |
| rolling_pm_range | 0.0917 |
| consec_losses | 0.0594 |
| pm_avg_bar_range | 0.0578 |

**Dominant feature: `range_expansion`** (PM range / AM range). Both models agree this is the single most important predictor. When the afternoon range expands relative to morning, the IC fails.

---

## Pattern Analysis

### Win Rate by Gap Size

| Gap Bucket | Trades | Win Rate | Avg P&L |
|---|---|---|---|
| 0.1 - 0.3% | 13 | **62%** | +$31 |
| 0.3 - 0.5% | 4 | 50% | +$19 |
| 0.5 - 1.0% | 10 | 50% | +$5 |
| 1.0%+ | 2 | 50% | +$75 |

Small gaps (0.1-0.3%) perform best. Larger gaps have more mixed results.

### AM Return Direction

| AM Direction | Trades | Win Rate | Avg P&L |
|---|---|---|---|
| **AM bullish** | 34 | **59%** | +$46 |
| **AM bearish** | 14 | **36%** | -$10 |

When the morning gives back the gap (AM bearish), the IC is much more likely to lose. The gap-up signal was effectively false.

### Trend Continuation

| Pattern | Trades | Win Rate | Avg P&L |
|---|---|---|---|
| AM & PM same direction | 23 | **61%** | +$61 |
| AM & PM reverse | 25 | 44% | $0 |

### PM Range Threshold

| Threshold | Trades Above | Win Rate | Avg P&L |
|---|---|---|---|
| PM range >= 0.15% | 44 | 48% | +$17 |
| PM range >= 0.20% | 38 | 45% | +$10 |
| PM range >= 0.25% | 32 | **34%** | -$32 |
| PM range >= 0.30% | 26 | **31%** | -$43 |

### Time in Trade

| | Avg Hours |
|---|---|
| Wins | 2.1h |
| Losses | 2.5h |

---

## Root Cause Analysis

### Why losses happen:

1. **10pt IC is structurally too narrow.** The average PM range is 18.8 pts on wins and 34.4 pts on losses — both exceed the 10pt IC width. Wins occur when price oscillates *around* the entry; losses occur when it trends *through* one side.

2. **Put side dominates losses** (21 of 23). The bot enters on gap-up days, but many gap-ups get faded in the afternoon. The short put ($5 below entry) has almost no cushion.

3. **High-volatility regimes are killers.** HMM State 1 (avg day range 97 pts) produces only 25% win rate.

4. **Pre-filter losses inflated the count.** Many early losses occurred on negative-gap days before the >= 0.1% filter was added in v13.

---

## Recommendations (Priority Order)

### 1. Tighten VIX filter: cap at 18 (was 24)
Higher VIX = larger intraday moves = more IC breaches. Previous Bocca analysis found VIX < 18 => 88% win rate.

### 2. Add AM return filter
If by 13:45 the morning has given back the gap (AM return < 0), skip. AM bearish days have only 36% WR. This alone would eliminate 14 poor trades.

### 3. AM range filter
If AM range > 30 pts (approx 0.4% of SPX) by entry time, skip. Large morning ranges predict volatile afternoons.

### 4. Gap filter already good
The v13 gap >= 0.1% filter is correct and would have eliminated several early losses on negative-gap days.

### 5. Consider wider wings ($10 instead of $5)
$5 wings give only 5 pts of cushion per side. $10 wings would double the cushion and still collect meaningful premium on 0DTE. Alternatively, enter later (14:30+) to reduce time at risk.

### 6. Reduce stop loss from 90% to 60-70%
Currently losing up to 90% of risk before exiting. A tighter stop reduces average loss size, improving risk/reward even if it triggers slightly more often.

### 7. Consider call-side bias
The put side accounts for 91% of losses. A call-only version or asymmetric IC (wider put wing) might perform better.

---

## Curve Fitting Caveat

With 48 trades, ML feature importances are directionally useful but not statistically robust. The strongest signals here are **structural ones**: a 10pt IC can't survive a trending afternoon, and AM bearish + gap-up = trapped longs unwinding. These are market-structure arguments, not data-mined findings. The range_expansion feature being dominant in both RF and GB lends credibility — it's measuring a real physical constraint (IC width vs realized range).
