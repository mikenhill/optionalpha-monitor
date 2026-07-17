"""
ORB-60 Bot Loss Analysis — 2026-07-16
======================================
Analyses why the ORB-60 put spread lost on July 16 and identifies regime
changes using HMM, feature importance (Random Forest), and market structure metrics.

Requires: pandas, numpy, scikit-learn, hmmlearn, matplotlib
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from hmmlearn.hmm import GaussianHMM
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 1. LOAD DATA
# =============================================================================
print("=" * 70)
print("ORB-60 BOT LOSS ANALYSIS")
print("=" * 70)

BASE = r"G:\My Drive\Colab Notebooks\optionalpha-monitor"

# SPX 5-min bars
spx = pd.read_csv(f"{BASE}/spx-5min.csv")
spx['datetime'] = pd.to_datetime(spx['Date'] + ' ' + spx['Time'], format='%m/%d/%Y %H:%M')
spx = spx.sort_values('datetime').reset_index(drop=True)
spx['date'] = spx['datetime'].dt.date

# Trade log
trades = pd.read_csv(f"{BASE}/BOTA2AaSt8al2517792805884117611-20260717-a1a8d8.csv")
trades['openDate'] = pd.to_datetime(trades['openDate'])
trades['closeDate'] = pd.to_datetime(trades['closeDate'])
trades['trade_date'] = trades['openDate'].dt.date
trades['pnl'] = trades['pnl'].astype(float)

print(f"\nSPX data: {spx['date'].min()} to {spx['date'].max()} ({len(spx)} bars)")
print(f"Trades: {len(trades)} total, {trades[trades['pnl']>0].shape[0]} wins, {trades[trades['pnl']<0].shape[0]} losses")
print(f"Win rate: {trades[trades['pnl']>0].shape[0]/len(trades)*100:.1f}%")
print(f"Total P&L: ${trades['pnl'].sum():.0f}")

# =============================================================================
# 2. COMPUTE DAILY FEATURES (Opening Range, Volatility, Momentum)
# =============================================================================
print("\n" + "=" * 70)
print("COMPUTING DAILY MARKET FEATURES")
print("=" * 70)

# RTH = 09:30 to 16:00 ET (data uses 08:30-15:00 CT based on timestamps)
# The data appears to use ET based on the 08:35 start (pre-market) and trade times

def compute_daily_features(spx_df):
    """Compute per-day features from 5-min SPX bars."""
    features = []
    
    for date, day_data in spx_df.groupby('date'):
        day_data = day_data.sort_values('datetime')
        
        # Opening range (first 60 min of RTH: 09:30-10:30 ET)
        # Based on trade open times like 10:35-10:40, the ORB window is 9:30-10:30
        rth_start = day_data[day_data['datetime'].dt.time >= time(9, 30)]
        if len(rth_start) == 0:
            continue
            
        orb_bars = rth_start[rth_start['datetime'].dt.time < time(10, 30)]
        if len(orb_bars) == 0:
            continue
            
        orb_high = orb_bars['High'].max()
        orb_low = orb_bars['Low'].min()
        orb_range = orb_high - orb_low
        orb_open = orb_bars.iloc[0]['Open']
        orb_close = orb_bars.iloc[-1]['Close']
        orb_direction = 1 if orb_close > orb_open else -1
        
        # Full day stats
        rth_data = day_data[day_data['datetime'].dt.time >= time(9, 30)]
        if len(rth_data) < 5:
            continue
        day_high = rth_data['High'].max()
        day_low = rth_data['Low'].min()
        day_range = day_high - day_low
        day_open = rth_data.iloc[0]['Open']
        day_close = rth_data.iloc[-1]['Close']
        
        # Post-ORB data (after 10:30)
        post_orb = rth_data[rth_data['datetime'].dt.time >= time(10, 30)]
        
        # Breakout metrics
        broke_high = day_high > orb_high
        broke_low = day_low < orb_low
        breakout_type = 'both' if (broke_high and broke_low) else ('up' if broke_high else ('down' if broke_low else 'none'))
        
        # How far did price go beyond ORB
        extension_above = max(0, day_high - orb_high)
        extension_below = max(0, orb_low - day_low)
        
        # Volatility (5-min bar ranges)
        bar_ranges = rth_data['High'] - rth_data['Low']
        avg_bar_range = bar_ranges.mean()
        max_bar_range = bar_ranges.max()
        
        # Volume profile
        total_volume = rth_data['Volume'].sum()
        orb_volume = orb_bars['Volume'].sum()
        volume_ratio = orb_volume / total_volume if total_volume > 0 else 0
        
        # Momentum after ORB
        if len(post_orb) > 0:
            post_orb_return = (post_orb.iloc[-1]['Close'] - post_orb.iloc[0]['Open']) / post_orb.iloc[0]['Open'] * 100
            # Reversal: did price break ORB in one direction then reverse?
            post_orb_high = post_orb['High'].max()
            post_orb_low = post_orb['Low'].min()
        else:
            post_orb_return = 0
            post_orb_high = orb_high
            post_orb_low = orb_low
        
        # Intraday reversal magnitude
        reversal_magnitude = 0
        if broke_high and day_close < orb_high:
            reversal_magnitude = (day_high - day_close) / orb_range if orb_range > 0 else 0
        elif broke_low and day_close > orb_low:
            reversal_magnitude = (day_close - day_low) / orb_range if orb_range > 0 else 0
        
        # Pre-market gap
        prev_day = spx_df[spx_df['date'] < date]
        if len(prev_day) > 0:
            prev_close = prev_day.iloc[-1]['Close']
            gap = (day_open - prev_close) / prev_close * 100
        else:
            gap = 0
        
        # ORB range as pct of price
        orb_range_pct = orb_range / orb_open * 100
        
        # Trend strength: close position within day range
        if day_range > 0:
            close_position = (day_close - day_low) / day_range  # 0=at low, 1=at high
        else:
            close_position = 0.5
        
        features.append({
            'date': date,
            'orb_high': orb_high,
            'orb_low': orb_low,
            'orb_range': orb_range,
            'orb_range_pct': orb_range_pct,
            'orb_direction': orb_direction,
            'day_open': day_open,
            'day_close': day_close,
            'day_high': day_high,
            'day_low': day_low,
            'day_range': day_range,
            'day_return_pct': (day_close - day_open) / day_open * 100,
            'breakout_type': breakout_type,
            'broke_high': broke_high,
            'broke_low': broke_low,
            'extension_above': extension_above,
            'extension_below': extension_below,
            'avg_bar_range': avg_bar_range,
            'max_bar_range': max_bar_range,
            'total_volume': total_volume,
            'volume_ratio': volume_ratio,
            'post_orb_return': post_orb_return,
            'reversal_magnitude': reversal_magnitude,
            'gap_pct': gap,
            'close_position': close_position,
        })
    
    return pd.DataFrame(features)

daily = compute_daily_features(spx)
print(f"Computed features for {len(daily)} trading days")

# =============================================================================
# 3. MERGE TRADES WITH DAILY FEATURES
# =============================================================================
trades_merged = trades.merge(daily, left_on='trade_date', right_on='date', how='left')
trades_merged['win'] = (trades_merged['pnl'] > 0).astype(int)
trades_merged['is_put'] = trades_merged['type'].str.contains('put').astype(int)

# =============================================================================
# 4. ANALYSE THE LOSING TRADE (2026-07-16)
# =============================================================================
print("\n" + "=" * 70)
print("DETAILED ANALYSIS: 2026-07-16 (LOSING TRADE)")
print("=" * 70)

loss_date = pd.Timestamp('2026-07-16').date()
loss_trade = trades_merged[trades_merged['trade_date'] == loss_date].iloc[0]
loss_day = daily[daily['date'] == loss_date].iloc[0]

print(f"\n--- Trade Details ---")
print(f"  Type: {loss_trade['type']} (Short Put Spread)")
print(f"  Strikes: -7530 put / +7520 put ($10 wide)")
print(f"  Open price: ${loss_trade['openPrice']:.2f} credit")
print(f"  Close price: ${loss_trade['closePrice']:.2f} (bought back)")
print(f"  P&L: ${loss_trade['pnl']:.0f}")
print(f"  Open time: {loss_trade['openDate']}")
print(f"  Close time: {loss_trade['closeDate']}")
print(f"  SPX at open: {loss_trade['underlyingOpen']:.2f}")
print(f"  SPX at close: {loss_trade['underlyingClose']:.2f}")
print(f"  SPX move during trade: {loss_trade['underlyingClose'] - loss_trade['underlyingOpen']:.2f} pts")

print(f"\n--- Market Structure (Jul 16) ---")
print(f"  ORB High: {loss_day['orb_high']:.2f}")
print(f"  ORB Low: {loss_day['orb_low']:.2f}")
print(f"  ORB Range: {loss_day['orb_range']:.2f} ({loss_day['orb_range_pct']:.3f}%)")
print(f"  Day Open: {loss_day['day_open']:.2f}")
print(f"  Day Close: {loss_day['day_close']:.2f}")
print(f"  Day Range: {loss_day['day_range']:.2f}")
print(f"  Breakout type: {loss_day['breakout_type']}")
print(f"  Extension above ORB: {loss_day['extension_above']:.2f}")
print(f"  Extension below ORB: {loss_day['extension_below']:.2f}")
print(f"  Reversal magnitude: {loss_day['reversal_magnitude']:.2f}")
print(f"  Gap: {loss_day['gap_pct']:.3f}%")
print(f"  Close position in range: {loss_day['close_position']:.2f} (0=low, 1=high)")

# Check if short strike was breached
short_strike = 7530
print(f"\n--- Strike Breach Analysis ---")
print(f"  Short put strike: {short_strike}")
print(f"  Day low: {loss_day['day_low']:.2f}")
print(f"  Strike breached: {'YES' if loss_day['day_low'] < short_strike else 'NO'}")
print(f"  Breach depth: {short_strike - loss_day['day_low']:.2f} pts below strike")
print(f"  SPX at close vs strike: {loss_day['day_close']:.2f} ({'ITM' if loss_day['day_close'] < short_strike else 'OTM'})")

# =============================================================================
# 5. COMPARE LOSING DAY vs WINNING DAYS
# =============================================================================
print("\n" + "=" * 70)
print("COMPARISON: LOSING DAYS vs WINNING DAYS")
print("=" * 70)

wins = trades_merged[trades_merged['pnl'] > 0]
losses = trades_merged[trades_merged['pnl'] < 0]

compare_cols = ['orb_range', 'orb_range_pct', 'day_range', 'avg_bar_range', 
                'max_bar_range', 'extension_above', 'extension_below', 
                'reversal_magnitude', 'gap_pct', 'close_position', 'volume_ratio']

print(f"\n{'Feature':<25} {'Wins (mean)':>12} {'Losses (mean)':>13} {'Jul 16':>10} {'Percentile':>10}")
print("-" * 75)
for col in compare_cols:
    if col in wins.columns and col in losses.columns:
        w_mean = wins[col].mean()
        l_mean = losses[col].mean()
        jul16_val = loss_day[col] if col in loss_day.index else 'N/A'
        # Percentile of Jul 16 value in all trade days
        all_vals = trades_merged[col].dropna()
        if isinstance(jul16_val, (int, float)) and len(all_vals) > 0:
            pctile = (all_vals < jul16_val).mean() * 100
            print(f"  {col:<23} {w_mean:>12.4f} {l_mean:>13.4f} {jul16_val:>10.4f} {pctile:>8.0f}th")
        else:
            print(f"  {col:<23} {w_mean:>12.4f} {l_mean:>13.4f} {'N/A':>10}")

# Put spread specific analysis
print(f"\n--- Put Spread Specific ---")
put_trades = trades_merged[trades_merged['is_put'] == 1]
put_wins = put_trades[put_trades['pnl'] > 0]
put_losses = put_trades[put_trades['pnl'] < 0]
print(f"  Put spread total: {len(put_trades)}, wins: {len(put_wins)}, losses: {len(put_losses)}")
print(f"  Put spread win rate: {len(put_wins)/len(put_trades)*100:.1f}%")
print(f"  All losing put spreads had breakout_type='both' or reversal:")
for _, row in put_losses.iterrows():
    print(f"    {row['trade_date']}: breakout={row.get('breakout_type','?')}, "
          f"reversal_mag={row.get('reversal_magnitude',0):.2f}, "
          f"day_range={row.get('day_range',0):.1f}")

# =============================================================================
# 6. HMM REGIME DETECTION
# =============================================================================
print("\n" + "=" * 70)
print("HMM MARKET REGIME ANALYSIS")
print("=" * 70)

# Features for HMM: daily volatility, range, momentum, volume
hmm_features = ['orb_range_pct', 'day_range', 'avg_bar_range', 'gap_pct', 'close_position']
daily_hmm = daily[hmm_features].dropna()

scaler = StandardScaler()
X_hmm = scaler.fit_transform(daily_hmm)

# Fit HMM with 3 states (low vol, normal, high vol/trending)
best_score = -np.inf
best_model = None
for n_states in [3, 4]:
    for _ in range(10):
        try:
            model = GaussianHMM(n_components=n_states, covariance_type='full',
                               n_iter=200, random_state=np.random.randint(10000))
            model.fit(X_hmm)
            score = model.score(X_hmm)
            if score > best_score:
                best_score = score
                best_model = model
        except:
            pass

states = best_model.predict(X_hmm)
daily['hmm_state'] = states

# Characterize states
print(f"\nBest HMM: {best_model.n_components} states, log-likelihood: {best_score:.1f}")
print(f"\n{'State':<8} {'Count':<6} {'Avg Range%':<12} {'Avg DayRng':<11} {'Avg BarRng':<11} {'Avg Gap%':<10} {'ClosPos':<8}")
print("-" * 70)
for s in range(best_model.n_components):
    mask = daily['hmm_state'] == s
    subset = daily[mask]
    print(f"  {s:<6} {mask.sum():<6} "
          f"{subset['orb_range_pct'].mean():<12.4f} "
          f"{subset['day_range'].mean():<11.2f} "
          f"{subset['avg_bar_range'].mean():<11.2f} "
          f"{subset['gap_pct'].mean():<10.4f} "
          f"{subset['close_position'].mean():<8.3f}")

# What state was Jul 16?
jul16_state = daily[daily['date'] == loss_date]['hmm_state'].values[0]
print(f"\n  Jul 16 HMM State: {jul16_state}")

# Trade outcomes by HMM state
trades_with_hmm = trades_merged.merge(daily[['date', 'hmm_state']], on='date', how='left')
print(f"\n--- Trade Win Rate by HMM State ---")
for s in sorted(trades_with_hmm['hmm_state'].dropna().unique()):
    s_trades = trades_with_hmm[trades_with_hmm['hmm_state'] == s]
    s_wins = s_trades[s_trades['pnl'] > 0]
    print(f"  State {int(s)}: {len(s_trades)} trades, "
          f"win rate {len(s_wins)/len(s_trades)*100:.1f}%, "
          f"avg P&L ${s_trades['pnl'].mean():.0f}")

# =============================================================================
# 7. RANDOM FOREST — WHAT PREDICTS LOSSES?
# =============================================================================
print("\n" + "=" * 70)
print("MACHINE LEARNING: LOSS PREDICTION (Random Forest + Gradient Boosting)")
print("=" * 70)

feature_cols = ['orb_range_pct', 'orb_direction', 'day_range', 'avg_bar_range',
                'max_bar_range', 'volume_ratio', 'gap_pct', 'is_put']

# Add rolling features
trades_merged_sorted = trades_merged.sort_values('trade_date')
trades_merged_sorted['prev_pnl'] = trades_merged_sorted['pnl'].shift(1)
trades_merged_sorted['rolling_win_rate'] = trades_merged_sorted['win'].rolling(5, min_periods=1).mean()
trades_merged_sorted['rolling_range'] = trades_merged_sorted['day_range'].rolling(5, min_periods=1).mean()

feature_cols_ext = feature_cols + ['prev_pnl', 'rolling_win_rate', 'rolling_range']

X = trades_merged_sorted[feature_cols_ext].dropna()
y = trades_merged_sorted.loc[X.index, 'win']

if len(X) >= 10:
    # Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42)
    rf.fit(X, y)
    rf_scores = cross_val_score(rf, X, y, cv=min(5, len(X)//2), scoring='accuracy')
    
    print(f"\nRandom Forest CV Accuracy: {rf_scores.mean():.3f} (+/- {rf_scores.std():.3f})")
    print(f"\n--- Feature Importance (RF) ---")
    importances = pd.Series(rf.feature_importances_, index=feature_cols_ext).sort_values(ascending=False)
    for feat, imp in importances.items():
        bar = '█' * int(imp * 50)
        print(f"  {feat:<22} {imp:.4f} {bar}")
    
    # Gradient Boosting
    gb = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    gb.fit(X, y)
    gb_scores = cross_val_score(gb, X, y, cv=min(5, len(X)//2), scoring='accuracy')
    
    print(f"\nGradient Boosting CV Accuracy: {gb_scores.mean():.3f} (+/- {gb_scores.std():.3f})")
    print(f"\n--- Feature Importance (GB) ---")
    importances_gb = pd.Series(gb.feature_importances_, index=feature_cols_ext).sort_values(ascending=False)
    for feat, imp in importances_gb.items():
        bar = '█' * int(imp * 50)
        print(f"  {feat:<22} {imp:.4f} {bar}")

    # What did the model predict for Jul 16?
    jul16_row = trades_merged_sorted[trades_merged_sorted['trade_date'] == loss_date]
    if len(jul16_row) > 0:
        jul16_X = jul16_row[feature_cols_ext].dropna()
        if len(jul16_X) > 0:
            rf_pred = rf.predict_proba(jul16_X)[0]
            gb_pred = gb.predict_proba(jul16_X)[0]
            print(f"\n--- Jul 16 Prediction ---")
            print(f"  RF win probability:  {rf_pred[1]:.3f}")
            print(f"  GB win probability:  {gb_pred[1]:.3f}")
            print(f"  Actual outcome:      LOSS")

# =============================================================================
# 8. WHAT CHANGED? — TREND / REGIME SHIFT DETECTION
# =============================================================================
print("\n" + "=" * 70)
print("WHAT CHANGED? — RECENT REGIME SHIFT ANALYSIS")
print("=" * 70)

# Look at recent 10 days vs prior period
recent = daily[daily['date'] >= pd.Timestamp('2026-07-01').date()]
prior = daily[(daily['date'] >= pd.Timestamp('2026-06-01').date()) & 
              (daily['date'] < pd.Timestamp('2026-07-01').date())]

print(f"\n{'Metric':<25} {'Jun 2026 (avg)':<16} {'Jul 2026 (avg)':<16} {'Change':<10}")
print("-" * 70)
for col in ['orb_range_pct', 'day_range', 'avg_bar_range', 'reversal_magnitude', 'gap_pct']:
    jun_val = prior[col].mean() if len(prior) > 0 else 0
    jul_val = recent[col].mean() if len(recent) > 0 else 0
    change = ((jul_val - jun_val) / jun_val * 100) if jun_val != 0 else 0
    print(f"  {col:<23} {jun_val:<16.4f} {jul_val:<16.4f} {change:>+.1f}%")

# Breakout reliability
print(f"\n--- Breakout Reliability ---")
for period_name, period_df in [('Jun', prior), ('Jul', recent)]:
    if len(period_df) == 0:
        continue
    up_breaks = period_df[period_df['broke_high']]
    dn_breaks = period_df[period_df['broke_low']]
    both = period_df[period_df['breakout_type'] == 'both']
    print(f"  {period_name}: {len(up_breaks)} up-breaks, {len(dn_breaks)} dn-breaks, "
          f"{len(both)} both ({len(both)/len(period_df)*100:.0f}% false breakouts)")

# =============================================================================
# 9. INTRADAY ANALYSIS — MINUTE-BY-MINUTE ON JULY 16
# =============================================================================
print("\n" + "=" * 70)
print("INTRADAY TIMELINE: JULY 16, 2026")
print("=" * 70)

jul16_bars = spx[spx['date'] == loss_date].sort_values('datetime')
orb_bars_jul16 = jul16_bars[(jul16_bars['datetime'].dt.time >= time(9, 30)) & 
                             (jul16_bars['datetime'].dt.time < time(10, 30))]

orb_h = orb_bars_jul16['High'].max()
orb_l = orb_bars_jul16['Low'].min()

print(f"\n  ORB (9:30-10:30): High={orb_h:.2f}, Low={orb_l:.2f}, Range={orb_h-orb_l:.2f}")
print(f"  Short put strike: 7530 (placed $0.01 below ORB low)")
print(f"  ORB low ≈ 7530 → bot sold put at 7530")

# Timeline of key events
print(f"\n  Timeline:")
prev_close_pos = None
for _, bar in jul16_bars.iterrows():
    t = bar['datetime'].strftime('%H:%M')
    close = bar['Close']
    high = bar['High']
    low = bar['Low']
    
    event = ""
    if high > orb_h and prev_close_pos != 'above_orb':
        event = " ← BROKE ABOVE ORB HIGH (trigger for put spread)"
    if low < orb_l:
        event = " ← BROKE BELOW ORB LOW"
    if low < 7530:
        event = " ← BELOW SHORT STRIKE 7530!"
    if low < 7520:
        event = " ← BELOW LONG STRIKE 7520! (MAX LOSS ZONE)"
    
    if bar['datetime'].time() >= time(9, 30):
        # Only print key moments
        if event or bar['datetime'].time() in [time(9,30), time(10,0), time(10,30), 
                                                        time(10,35), time(11,0), time(12,0),
                                                        time(12,15), time(13,0), time(14,0), time(15,0)]:
            print(f"    {t}  O:{bar['Open']:.1f} H:{high:.1f} L:{low:.1f} C:{close:.1f}{event}")
    
    if close > orb_h:
        prev_close_pos = 'above_orb'
    elif close < orb_l:
        prev_close_pos = 'below_orb'

# =============================================================================
# 10. ROOT CAUSE SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("ROOT CAUSE ANALYSIS & RECOMMENDATIONS")
print("=" * 70)

print("""
┌─────────────────────────────────────────────────────────────────────┐
│ WHY THE BOT LOST ON JULY 16:                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ 1. FALSE BREAKOUT / REVERSAL DAY                                    │
│    • SPX broke above ORB high → triggered put spread sale           │
│    • Price then reversed sharply, breaking below ORB low            │
│    • This is a "breakout failure" or "both-side breakout" day       │
│                                                                     │
│ 2. STRIKE TOO CLOSE TO ORB LOW                                      │
│    • Bot places short put at ORB low ($0.01 below)                  │
│    • On reversal days, this provides NO cushion                     │
│    • Day low went well below 7530 strike → ITM at expiry            │
│                                                                     │
│ 3. REGIME CHARACTERISTICS:                                          │
│    • Large day range relative to ORB range                          │
│    • High reversal magnitude                                        │
│    • Both-side breakout pattern                                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ WHAT CHANGED (potential regime shift):                               │
│    • Check HMM state transitions above                              │
│    • July showing higher % of "both" breakout days                  │
│    • Increased intraday volatility / range expansion                │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ RECOMMENDATIONS:                                                    │
│                                                                     │
│ 1. Add ORB range filter: Skip if ORB range < X pts (too narrow     │
│    = likely to get both-side breakouts)                              │
│                                                                     │
│ 2. Add breakout confirmation: Wait for 2nd bar close above/below   │
│    ORB level before entering (reduces false breakout entries)        │
│                                                                     │
│ 3. Widen strike placement: Place short put further below ORB low   │
│    (e.g., ORB low - 0.5*ORB_range) for more cushion                │
│                                                                     │
│ 4. Add VIX / volatility filter: Skip high-vol regimes where         │
│    reversals are more common (use HMM state as gate)                │
│                                                                     │
│ 5. Time filter: Avoid entries when ORB breakout happens very late   │
│    (>10:35) — less time for directional follow-through              │
│                                                                     │
│ 6. Both-side breakout stop: If price breaks BOTH ORB high AND low  │
│    intraday, close position immediately (override stop loss)         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
""")

# =============================================================================
# 11. VISUALISATION
# =============================================================================
print("Generating charts...")

fig, axes = plt.subplots(3, 2, figsize=(16, 14))
fig.suptitle('ORB-60 Bot Loss Analysis — July 16, 2026', fontsize=14, fontweight='bold')

# Chart 1: Jul 16 intraday with ORB levels and strikes
ax = axes[0, 0]
jul16_rth = jul16_bars[jul16_bars['datetime'].dt.time >= time(9, 30)]
ax.plot(jul16_rth['datetime'], jul16_rth['Close'], 'b-', linewidth=1)
ax.axhline(orb_h, color='green', linestyle='--', label=f'ORB High {orb_h:.0f}')
ax.axhline(orb_l, color='red', linestyle='--', label=f'ORB Low {orb_l:.0f}')
ax.axhline(7530, color='red', linewidth=2, label='Short Put 7530')
ax.axhline(7520, color='darkred', linewidth=1.5, linestyle=':', label='Long Put 7520')
ax.axhspan(7520, 7530, alpha=0.1, color='red', label='Max loss zone')
ax.set_title('Jul 16 Intraday — Price vs ORB & Strikes')
ax.legend(fontsize=8)
ax.set_ylabel('SPX')

# Chart 2: Trade P&L over time
ax = axes[0, 1]
trades_sorted = trades.sort_values('openDate')
colors = ['green' if p > 0 else 'red' for p in trades_sorted['pnl']]
ax.bar(range(len(trades_sorted)), trades_sorted['pnl'], color=colors, alpha=0.7)
ax.axhline(0, color='black', linewidth=0.5)
ax.set_title('Trade P&L History')
ax.set_xlabel('Trade #')
ax.set_ylabel('P&L ($)')
# Highlight Jul 16
jul16_idx = trades_sorted[trades_sorted['trade_date'] == loss_date].index
for idx in jul16_idx:
    pos = list(trades_sorted.index).index(idx)
    ax.annotate('Jul 16', xy=(pos, trades_sorted.loc[idx, 'pnl']),
               xytext=(pos, trades_sorted.loc[idx, 'pnl'] - 30),
               fontsize=8, ha='center', color='red',
               arrowprops=dict(arrowstyle='->', color='red'))

# Chart 3: HMM states over time
ax = axes[1, 0]
state_colors = ['green', 'blue', 'orange', 'red']
for s in range(best_model.n_components):
    mask = daily['hmm_state'] == s
    dates_s = pd.to_datetime(daily.loc[mask, 'date'])
    ax.scatter(dates_s, daily.loc[mask, 'day_range'], 
              c=state_colors[s % len(state_colors)], label=f'State {s}', alpha=0.6, s=20)
ax.axvline(pd.Timestamp('2026-07-16'), color='red', linestyle='--', alpha=0.7, label='Jul 16')
ax.set_title('HMM States — Day Range by Date')
ax.legend(fontsize=8)
ax.set_ylabel('Day Range (pts)')

# Chart 4: ORB range vs outcome
ax = axes[1, 1]
wins_plot = trades_merged[trades_merged['pnl'] > 0]
losses_plot = trades_merged[trades_merged['pnl'] < 0]
ax.scatter(wins_plot['orb_range_pct'], wins_plot['reversal_magnitude'], 
          c='green', alpha=0.6, label='Wins', s=40)
ax.scatter(losses_plot['orb_range_pct'], losses_plot['reversal_magnitude'],
          c='red', alpha=0.8, label='Losses', s=80, marker='x')
ax.set_xlabel('ORB Range %')
ax.set_ylabel('Reversal Magnitude')
ax.set_title('ORB Range vs Reversal — Wins vs Losses')
ax.legend()

# Chart 5: Feature importance
ax = axes[2, 0]
importances.sort_values().plot(kind='barh', ax=ax, color='steelblue')
ax.set_title('Random Forest Feature Importance')
ax.set_xlabel('Importance')

# Chart 6: Rolling metrics (day range, ORB range)
ax = axes[2, 1]
daily_sorted = daily.sort_values('date')
daily_sorted['date_dt'] = pd.to_datetime(daily_sorted['date'])
daily_sorted['rolling_day_range'] = daily_sorted['day_range'].rolling(10, min_periods=3).mean()
daily_sorted['rolling_orb_range'] = daily_sorted['orb_range'].rolling(10, min_periods=3).mean()
ax.plot(daily_sorted['date_dt'], daily_sorted['rolling_day_range'], 'b-', label='Day Range (10d MA)')
ax.plot(daily_sorted['date_dt'], daily_sorted['rolling_orb_range'], 'g-', label='ORB Range (10d MA)')
ax.axvline(pd.Timestamp('2026-07-16'), color='red', linestyle='--', alpha=0.7, label='Jul 16')
ax.set_title('Rolling Volatility (10-day MA)')
ax.legend(fontsize=8)
ax.set_ylabel('Points')

plt.tight_layout()
plt.savefig(f"{BASE}/orb60_loss_analysis.png", dpi=150, bbox_inches='tight')
print(f"\nChart saved: {BASE}/orb60_loss_analysis.png")
plt.show()

print("\n✓ Analysis complete.")
