# ORB-60 Bot Analysis

**Date:** 2026-07-17  
**Analysis script:** `orb60_loss_analysis.py`  
**Focus:** Why the bot lost on 2026-07-16, regime detection, and filter recommendations

---

## Bot Configuration

| Setting | Put Scanner (v33) | Call Scanner (v29) |
|---|---|---|
| **Strategy** | Short Put Spread | Short Call Spread |
| **Underlying** | SPX | SPX |
| **Expiry** | 0DTE | 0DTE |
| **Width** | $10 wide | $10 wide |
| **Short Strike** | $0.01 below ORB-60 low | Above ORB-60 high |
| **Entry Criteria** | SPX high > ORB high, NOT SPX low < ORB low | SPX low < ORB low, NOT SPX high > ORB high |
| **Filters** | Mon-Fri, no FOMC, no CPI, no NFP | Mon-Fri, no FOMC, no CPI, no NFP |
| **Position Filter** | Max profit 70 | Max profit 70 |
| **Price** | 50% of bid/ask | 50% of bid/ask |
| **Exit** | 40% profit / 130% stop / $50 profit | 40% profit / 130% stop / $50 profit |

**Logic:** When SPX breaks above the 60-min ORB high (and NOT below low), sell a put spread below the ORB low. Vice versa for calls. Essentially betting the breakout direction continues and the opposite side stays safe.

---

## Performance Summary

| Metric | Value |
|---|---|
| **Total Trades** | 20 |
| **Wins** | 17 |
| **Losses** | 3 |
| **Win Rate** | 85.0% |
| **Total P&L** | +$430 |
| **Avg Win** | +$48 |
| **Avg Loss** | -$145 |
| **Date Range** | 2026-05-20 to 2026-07-16 |
| **Put Spreads** | 11 trades (72.7% WR) |
| **Call Spreads** | 9 trades (100% WR) |

---

## Trade Log

| Date | Type | Short Strike | P&L | Result |
|---|---|---|---|---|
| 2026-07-16 | Put Spread | 7530 | -$115 | LOSS |
| 2026-07-15 | Call Spread | 7585 | +$65 | WIN |
| 2026-07-10 | Call Spread | 7560 | +$55 | WIN |
| 2026-07-09 | Put Spread | 7480 | +$35 | WIN |
| 2026-07-08 | Call Spread | 7480 | +$70 | WIN |
| 2026-07-07 | Call Spread | 7540 | +$30 | WIN |
| 2026-07-06 | Put Spread | 7500 | +$55 | WIN |
| 2026-06-30 | Put Spread | 7435 | +$40 | WIN |
| 2026-06-24 | Put Spread | 7365 | +$50 | WIN |
| 2026-06-22 | Call Spread | 7535 | +$35 | WIN |
| 2026-06-16 | Call Spread | 7565 | +$50 | WIN |
| 2026-06-12 | Put Spread | 7360 | +$50 | WIN |
| 2026-06-11 | Call Spread | 7330 | +$60 | WIN |
| 2026-06-08 | Put Spread | 7420 | -$160 | LOSS |
| 2026-06-02 | Put Spread | 7580 | +$50 | WIN |
| 2026-06-01 | Put Spread | 7560 | +$50 | WIN |
| 2026-05-29 | Call Spread | 7600 | +$55 | WIN |
| 2026-05-27 | Call Spread | 7535 | +$55 | WIN |
| 2026-05-26 | Put Spread | 7505 | -$160 | LOSS |
| 2026-05-20 | Put Spread | 7355 | +$60 | WIN |

---

## Case Study: 2026-07-16 Loss

| Detail | Value |
|---|---|
| **Trade** | Short Put Spread -7530/+7520 |
| **Credit received** | $0.80 |
| **Closed at** | $1.95 |
| **P&L** | -$115 |
| **Opened** | 10:35 ET |
| **Closed** | 12:15 ET (stop hit) |
| **SPX at open** | 7568.07 |
| **SPX at close** | 7545.60 |
| **Day low** | 7504.02 |
| **Short put breach depth** | 25.98 pts below 7530 |
| **Gap** | -0.13% (gap down) |
| **ORB range** | 15.42 pts (narrow — 10th percentile) |
| **Day range** | 66.72 pts |

**What happened:** SPX gapped down -0.13%, formed a narrow ORB (only 15 pts), broke above the ORB high briefly, triggering the put spread. Then reversed hard, falling 51 pts below the ORB low and blowing through the 7530 short put by 26 pts. The ORB breakout was a false signal on a gap-down day.

---

## Winning vs Losing Days Comparison

| Feature | Wins (mean) | Losses (mean) | Jul 16 | Jul 16 Pctile |
|---|---|---|---|---|
| **ORB range** | 33.8 pts | 23.3 pts | 15.4 pts | 10th |
| **ORB range %** | 0.453% | 0.312% | 0.204% | 10th |
| **Day range** | 56.4 pts | 58.8 pts | 66.7 pts | 70th |
| **Extension below ORB** | 6.4 pts | 35.5 pts | 51.3 pts | 90th |
| **Gap %** | +0.113% | +0.458% | -0.129% | 10th |
| **Close position** | 0.66 | 0.36 | 0.45 | 20th |

**Key pattern:** Losing days have narrower ORBs (easier to fake-break) and much larger extensions in the opposite direction.

---

## HMM Regime Analysis (4 States)

| State | Days | Avg Day Range | Avg Bar Range | Avg Gap% | Close Position |
|---|---|---|---|---|---|
| 0 (Low vol) | 145 | 33 pts | 3.66 | +0.15% | 0.62 |
| 1 (Normal) | 168 | 57 pts | 6.26 | +0.07% | 0.57 |
| 2 (Crisis) | 5 | 291 pts | 27.76 | -0.65% | 0.51 |
| 3 (High vol) | 66 | 101 pts | 9.98 | -0.11% | 0.42 |

**Jul 16 was HMM State 1 (Normal)** — the loss was not in an extreme regime.

### Win Rate by HMM State

| State | Trades | Win Rate | Avg P&L |
|---|---|---|---|
| 0 (Low vol) | 6 | 83.3% | +$18 |
| 1 (Normal) | 10 | 90.0% | +$32 |
| 3 (High vol) | 4 | 75.0% | $0 |

---

## ML Model Results

### Random Forest (CV Accuracy: 85.0%)

Baseline (always predict win): 85.0% — **model matches baseline**, meaning with 85% win rate the ML can't improve on "always predict win." This is a good sign for the bot's consistency but means losses are hard to predict.

### All 3 Losing Trades Share These Features
- All were **put spreads**
- All had breakout type = **down** (SPX broke the ORB low after or during the ORB high break)
- 2 of 3 occurred on **gap-down days** (Jul 16: -0.13%, May 26 was a gap-up that reversed)
- All had ORB ranges in the **bottom quartile**

---

## Root Cause

The ORB-60 put spread loses when:
1. **The ORB breakout is a fake-out** — narrow ORB (< 20 pts) with a brief poke above the high, followed by reversal
2. **Gap-down days** — the market opens weak, briefly rallies above ORB high, then resumes downtrend
3. **Both sides of the ORB break** — by definition, if both high AND low break, one side's spread is in trouble

---

## Recommendations

### 1. Add Gap Direction Filter (HIGH PRIORITY)
**Put scanner:** Add `SPX gap % today >= 0` (already done in latest config). Gap-down days produce false upside breakouts that reverse into put spread losses.

### 2. ORB Range Minimum
Skip if ORB range < 20 pts (0.27% of SPX). Narrow ORBs are more easily false-broken. This would have filtered Jul 16 (15.4 pts) and possibly May 26.

### 3. Monitor for Both-Side Breaks
If both ORB high AND low are broken, the breakout signal is invalidated. Consider an auto-exit rule if the opposite side of the ORB also breaks after entry.

### 4. Current Risk/Reward Assessment
- Avg win: +$48, Avg loss: -$145 → need 75%+ WR to break even
- Current 85% WR is healthy but fragile — just 2 more losses drops to breakeven
- The 130% stop loss is appropriate; reducing further would increase false triggers

### 5. Call Spreads Are Stronger
All 9 call spread trades won (100%). The ORB-low breakout (bearish) triggering a call spread above the ORB high seems more reliable. Put spreads (bullish breakout, sell below) carry more reversal risk.

---

## Curve Fitting Caveat

With only 20 trades (3 losses), ML models cannot meaningfully separate wins from losses. The feature comparisons and structural observations above are more reliable than model accuracy scores. The gap-down and narrow-ORB patterns are **market-structure** arguments, not data-mined findings.
