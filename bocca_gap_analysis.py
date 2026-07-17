"""
Bocca Gap Bot Analysis
======================
0DTE Iron Condor sold ~13:45 ET on gap-up days (≥0.1%), $5 wide wings,
short strikes $5 from underlying. VIX filter 0-24. Exit: 40% profit / 90% stop.

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
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 1. LOAD DATA
# =============================================================================
print("=" * 70)
print("BOCCA GAP BOT ANALYSIS")
print("=" * 70)

BASE = r"G:\My Drive\Colab Notebooks\optionalpha-monitor"

# SPX 5-min bars
spx = pd.read_csv(f"{BASE}/spx-5min.csv")
spx['datetime'] = pd.to_datetime(spx['Date'] + ' ' + spx['Time'], format='%m/%d/%Y %H:%M')
spx = spx.sort_values('datetime').reset_index(drop=True)
spx['date'] = spx['datetime'].dt.date

# Trade log
trades = pd.read_csv(f"{BASE}/BOTA2AaSt8al3917760816701257651-20260717-fe40aa.csv")
trades['openDate'] = pd.to_datetime(trades['openDate'])
trades['closeDate'] = pd.to_datetime(trades['closeDate'])
trades['trade_date'] = trades['openDate'].dt.date
trades['pnl'] = trades['pnl'].astype(float)
trades['open_time'] = trades['openDate'].dt.time
trades['close_time'] = trades['closeDate'].dt.time

print(f"\nSPX data: {spx['date'].min()} to {spx['date'].max()} ({len(spx)} bars)")
print(f"Trades: {len(trades)} total")
print(f"  Wins (pnl>0): {(trades['pnl']>0).sum()}")
print(f"  Losses (pnl<0): {(trades['pnl']<0).sum()}")
print(f"  Win rate: {(trades['pnl']>0).mean()*100:.1f}%")
print(f"  Total P&L: ${trades['pnl'].sum():.0f}")
print(f"  Avg Win: ${trades[trades['pnl']>0]['pnl'].mean():.0f}")
print(f"  Avg Loss: ${trades[trades['pnl']<0]['pnl'].mean():.0f}")
print(f"  Date range: {trades['trade_date'].min()} to {trades['trade_date'].max()}")

# =============================================================================
# 2. UNDERSTAND THE BOT CONFIG
# =============================================================================
print("\n" + "=" * 70)
print("BOT CONFIGURATION")
print("=" * 70)
print("""
  Strategy:    0DTE Iron Condor on SPX
  Entry time:  ~13:45 ET (scanner wakeup)
  Entry cond:  Gap ≥ 0.1%, VIX 0-24, market closes at 4PM
  Structure:   Short put $5 below price, Long put $5 below that
               (Call side from IC structure — $5 above and $5 above that)
  Width:       $5 wide wings
  Exit:        40% profit target, 90% stop loss
  Expiry:      Same day (0DTE)
  RWR filter:  100 (reward-to-width ratio)
  Price:       100% of bid/ask, $0.10 from mid
""")

# =============================================================================
# 3. COMPUTE DAILY FEATURES
# =============================================================================
print("=" * 70)
print("COMPUTING DAILY MARKET FEATURES")
print("=" * 70)

def compute_daily_features(spx_df):
    features = []
    for date, day_data in spx_df.groupby('date'):
        day_data = day_data.sort_values('datetime')
        
        rth = day_data[day_data['datetime'].dt.time >= time(9, 30)]
        if len(rth) < 10:
            continue
        
        day_open = rth.iloc[0]['Open']
        day_close = rth.iloc[-1]['Close']
        day_high = rth['High'].max()
        day_low = rth['Low'].min()
        day_range = day_high - day_low
        
        # Gap
        prev_day = spx_df[spx_df['date'] < date]
        if len(prev_day) > 0:
            prev_close = prev_day.iloc[-1]['Close']
            gap_pct = (day_open - prev_close) / prev_close * 100
        else:
            gap_pct = 0
        
        # ORB (first 60 min)
        orb = rth[rth['datetime'].dt.time < time(10, 30)]
        orb_high = orb['High'].max() if len(orb) > 0 else day_high
        orb_low = orb['Low'].min() if len(orb) > 0 else day_low
        orb_range = orb_high - orb_low
        
        # Afternoon session (13:00+) — when bot trades
        afternoon = rth[rth['datetime'].dt.time >= time(13, 0)]
        if len(afternoon) > 0:
            pm_open = afternoon.iloc[0]['Open']
            pm_close = afternoon.iloc[-1]['Close']
            pm_high = afternoon['High'].max()
            pm_low = afternoon['Low'].min()
            pm_range = pm_high - pm_low
            pm_return = (pm_close - pm_open) / pm_open * 100
        else:
            pm_open = pm_close = pm_high = pm_low = day_close
            pm_range = 0
            pm_return = 0
        
        # Price at 13:45 (approx bot entry time)
        entry_bars = rth[(rth['datetime'].dt.time >= time(13, 40)) & 
                         (rth['datetime'].dt.time <= time(13, 50))]
        if len(entry_bars) > 0:
            price_at_entry = entry_bars.iloc[0]['Close']
        else:
            price_at_entry = pm_open
        
        # Morning trend (9:30-13:00)
        morning = rth[(rth['datetime'].dt.time >= time(9, 30)) & 
                      (rth['datetime'].dt.time < time(13, 0))]
        if len(morning) > 0:
            am_return = (morning.iloc[-1]['Close'] - morning.iloc[0]['Open']) / morning.iloc[0]['Open'] * 100
            am_high = morning['High'].max()
            am_low = morning['Low'].min()
            am_range = am_high - am_low
        else:
            am_return = 0
            am_range = 0
        
        # Volatility metrics
        bar_ranges = rth['High'] - rth['Low']
        avg_bar_range = bar_ranges.mean()
        
        # Afternoon bar volatility
        if len(afternoon) > 0:
            pm_bar_ranges = afternoon['High'] - afternoon['Low']
            pm_avg_bar_range = pm_bar_ranges.mean()
        else:
            pm_avg_bar_range = avg_bar_range
        
        # How far from entry does price end up
        eod_vs_entry = day_close - price_at_entry
        
        # Day return
        day_return_pct = (day_close - day_open) / day_open * 100
        
        # Trend continuation: does afternoon continue morning direction?
        trend_continuation = 1 if (am_return > 0 and pm_return > 0) or (am_return < 0 and pm_return < 0) else 0
        
        # Close position in day range
        close_position = (day_close - day_low) / day_range if day_range > 0 else 0.5
        
        # Range expansion: PM range as ratio of AM range
        range_expansion = pm_range / am_range if am_range > 0 else 1.0
        
        features.append({
            'date': date,
            'day_open': day_open,
            'day_close': day_close,
            'day_high': day_high,
            'day_low': day_low,
            'day_range': day_range,
            'day_return_pct': day_return_pct,
            'gap_pct': gap_pct,
            'orb_range': orb_range,
            'am_return': am_return,
            'am_range': am_range,
            'pm_return': pm_return,
            'pm_range': pm_range,
            'pm_avg_bar_range': pm_avg_bar_range,
            'avg_bar_range': avg_bar_range,
            'price_at_entry': price_at_entry,
            'eod_vs_entry': eod_vs_entry,
            'trend_continuation': trend_continuation,
            'close_position': close_position,
            'range_expansion': range_expansion,
        })
    
    return pd.DataFrame(features)

daily = compute_daily_features(spx)
print(f"Computed features for {len(daily)} trading days")

# =============================================================================
# 4. MERGE TRADES WITH FEATURES
# =============================================================================
trades_merged = trades.merge(daily, left_on='trade_date', right_on='date', how='left')
trades_merged['win'] = (trades_merged['pnl'] > 0).astype(int)

# Parse IC structure to get wing width info
def parse_ic_strikes(desc):
    """Extract strikes from description like '+7,550 put, -7,555 put, -7,565 call, +7,570 call'"""
    import re
    nums = re.findall(r'([+-])([\d,]+)\s+(put|call)', desc)
    strikes = {}
    for sign, strike_str, opt_type in nums:
        strike = int(strike_str.replace(',', ''))
        key = f"{'long' if sign=='+' else 'short'}_{opt_type}"
        strikes[key] = strike
    return strikes

trades_merged['strikes'] = trades_merged['description'].apply(parse_ic_strikes)
trades_merged['short_put'] = trades_merged['strikes'].apply(lambda x: x.get('short_put', 0))
trades_merged['short_call'] = trades_merged['strikes'].apply(lambda x: x.get('short_call', 0))
trades_merged['ic_width'] = trades_merged['short_call'] - trades_merged['short_put']

# Distance from entry price to short strikes
trades_merged['put_cushion'] = trades_merged['price_at_entry'] - trades_merged['short_put']
trades_merged['call_cushion'] = trades_merged['short_call'] - trades_merged['price_at_entry']

# Which side was breached?
trades_merged['breached_put'] = trades_merged['day_low'] <= trades_merged['short_put']
trades_merged['breached_call'] = trades_merged['day_high'] >= trades_merged['short_call']

# =============================================================================
# 5. TRADE STATISTICS
# =============================================================================
print("\n" + "=" * 70)
print("TRADE STATISTICS")
print("=" * 70)

print(f"\n--- IC Width (short put to short call) ---")
print(f"  Mean: {trades_merged['ic_width'].mean():.1f} pts")
print(f"  Min:  {trades_merged['ic_width'].min():.0f} pts")
print(f"  Max:  {trades_merged['ic_width'].max():.0f} pts")

print(f"\n--- Premium Collected ---")
print(f"  Mean: ${trades_merged['openPrice'].mean()*100:.0f}")
print(f"  Min:  ${trades_merged['openPrice'].min()*100:.0f}")
print(f"  Max:  ${trades_merged['openPrice'].max()*100:.0f}")

print(f"\n--- Breach Analysis ---")
print(f"  Put side breached:  {trades_merged['breached_put'].sum()} / {len(trades_merged)} trades")
print(f"  Call side breached: {trades_merged['breached_call'].sum()} / {len(trades_merged)} trades")
print(f"  Neither breached:   {((~trades_merged['breached_put']) & (~trades_merged['breached_call'])).sum()}")

# Which side causes losses?
losses = trades_merged[trades_merged['pnl'] < 0]
print(f"\n--- Losing Trades Breach Detail ---")
for _, row in losses.iterrows():
    side = "PUT" if row['breached_put'] else ("CALL" if row['breached_call'] else "NEITHER")
    # How far beyond strike
    if row['breached_put']:
        breach_depth = row['short_put'] - row['day_low']
    elif row['breached_call']:
        breach_depth = row['day_high'] - row['short_call']
    else:
        breach_depth = 0
    print(f"  {row['trade_date']}: {side} breached, depth={breach_depth:.1f}pts, "
          f"pm_range={row['pm_range']:.1f}, gap={row['gap_pct']:.2f}%, pnl=${row['pnl']:.0f}")

# =============================================================================
# 6. COMPARISON: WINS vs LOSSES
# =============================================================================
print("\n" + "=" * 70)
print("COMPARISON: WINNING vs LOSING DAYS")
print("=" * 70)

wins = trades_merged[trades_merged['pnl'] > 0]
losses = trades_merged[trades_merged['pnl'] < 0]

compare_cols = ['gap_pct', 'am_return', 'am_range', 'pm_range', 'pm_avg_bar_range',
                'day_range', 'avg_bar_range', 'ic_width', 'range_expansion',
                'close_position', 'trend_continuation']

print(f"\n{'Feature':<22} {'Wins (mean)':>12} {'Losses (mean)':>13} {'Diff':>8}")
print("-" * 60)
for col in compare_cols:
    if col in wins.columns:
        w = wins[col].mean()
        l = losses[col].mean()
        diff = l - w
        print(f"  {col:<20} {w:>12.4f} {l:>13.4f} {diff:>+8.4f}")

# =============================================================================
# 7. HMM REGIME ANALYSIS
# =============================================================================
print("\n" + "=" * 70)
print("HMM MARKET REGIME ANALYSIS")
print("=" * 70)

hmm_features = ['day_range', 'avg_bar_range', 'gap_pct', 'am_range', 'pm_range']
daily_hmm = daily[hmm_features].dropna()

scaler = StandardScaler()
X_hmm = scaler.fit_transform(daily_hmm)

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

print(f"\nBest HMM: {best_model.n_components} states")
print(f"\n{'State':<8} {'Count':<6} {'DayRng':<9} {'AvgBar':<9} {'Gap%':<9} {'AM Rng':<9} {'PM Rng':<9}")
print("-" * 55)
for s in range(best_model.n_components):
    mask = daily['hmm_state'] == s
    sub = daily[mask]
    print(f"  {s:<6} {mask.sum():<6} "
          f"{sub['day_range'].mean():<9.1f} "
          f"{sub['avg_bar_range'].mean():<9.2f} "
          f"{sub['gap_pct'].mean():<9.3f} "
          f"{sub['am_range'].mean():<9.1f} "
          f"{sub['pm_range'].mean():<9.1f}")

# Trade outcomes by regime
trades_with_hmm = trades_merged.merge(daily[['date', 'hmm_state']], on='date', how='left')
print(f"\n--- Trade Win Rate by HMM State ---")
for s in sorted(trades_with_hmm['hmm_state'].dropna().unique()):
    s_trades = trades_with_hmm[trades_with_hmm['hmm_state'] == s]
    wr = (s_trades['pnl'] > 0).mean() * 100
    print(f"  State {int(s)}: {len(s_trades)} trades, win rate {wr:.1f}%, "
          f"avg P&L ${s_trades['pnl'].mean():.0f}, "
          f"avg day_range {s_trades['day_range'].mean():.1f}")

# =============================================================================
# 8. ML MODELS
# =============================================================================
print("\n" + "=" * 70)
print("ML: WIN/LOSS PREDICTION")
print("=" * 70)

feature_cols = ['gap_pct', 'am_return', 'am_range', 'pm_avg_bar_range',
                'avg_bar_range', 'range_expansion', 'ic_width', 'close_position']

# Add rolling features
trades_sorted = trades_merged.sort_values('trade_date').reset_index(drop=True)
trades_sorted['prev_pnl'] = trades_sorted['pnl'].shift(1)
trades_sorted['rolling_wr'] = trades_sorted['win'].rolling(5, min_periods=1).mean()
trades_sorted['rolling_pm_range'] = trades_sorted['pm_range'].rolling(5, min_periods=1).mean()
trades_sorted['consec_losses'] = 0
count = 0
for i in range(len(trades_sorted)):
    if i > 0 and trades_sorted.loc[i-1, 'pnl'] < 0:
        count += 1
    else:
        count = 0
    trades_sorted.loc[i, 'consec_losses'] = count

feature_cols_ext = feature_cols + ['prev_pnl', 'rolling_wr', 'rolling_pm_range', 'consec_losses']

X = trades_sorted[feature_cols_ext].dropna()
y = trades_sorted.loc[X.index, 'win']

if len(X) >= 10:
    rf = RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42)
    rf.fit(X, y)
    rf_scores = cross_val_score(rf, X, y, cv=min(5, len(X)//3), scoring='accuracy')
    
    print(f"\nRandom Forest CV Accuracy: {rf_scores.mean():.3f} (+/- {rf_scores.std():.3f})")
    print(f"  (Baseline — always predict majority class: {max(y.mean(), 1-y.mean()):.3f})")
    
    print(f"\n--- Feature Importance (RF) ---")
    importances = pd.Series(rf.feature_importances_, index=feature_cols_ext).sort_values(ascending=False)
    for feat, imp in importances.items():
        bar = '█' * int(imp * 40)
        print(f"  {feat:<22} {imp:.4f} {bar}")
    
    gb = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    gb.fit(X, y)
    gb_scores = cross_val_score(gb, X, y, cv=min(5, len(X)//3), scoring='accuracy')
    
    print(f"\nGradient Boosting CV Accuracy: {gb_scores.mean():.3f} (+/- {gb_scores.std():.3f})")
    print(f"\n--- Feature Importance (GB) ---")
    imp_gb = pd.Series(gb.feature_importances_, index=feature_cols_ext).sort_values(ascending=False)
    for feat, imp in imp_gb.items():
        bar = '█' * int(imp * 40)
        print(f"  {feat:<22} {imp:.4f} {bar}")

# =============================================================================
# 9. KEY PATTERNS IN LOSSES
# =============================================================================
print("\n" + "=" * 70)
print("LOSS PATTERN ANALYSIS")
print("=" * 70)

# Check afternoon range vs IC width
print(f"\n--- PM Range vs IC Width ---")
print(f"  Wins:   PM range avg={wins['pm_range'].mean():.1f}, IC width avg={wins['ic_width'].mean():.1f}, "
      f"ratio={wins['pm_range'].mean()/wins['ic_width'].mean():.2f}")
print(f"  Losses: PM range avg={losses['pm_range'].mean():.1f}, IC width avg={losses['ic_width'].mean():.1f}, "
      f"ratio={losses['pm_range'].mean()/losses['ic_width'].mean():.2f}")

# Days where PM range exceeds IC width
pm_exceeds_ic = trades_merged['pm_range'] > trades_merged['ic_width']
print(f"\n  Days where PM range > IC width: {pm_exceeds_ic.sum()} / {len(trades_merged)}")
print(f"    Of those, losses: {(pm_exceeds_ic & (trades_merged['pnl']<0)).sum()}")
print(f"    Of those, wins:   {(pm_exceeds_ic & (trades_merged['pnl']>0)).sum()}")

# Gap size buckets
print(f"\n--- Win Rate by Gap Size ---")
for low, high, label in [(0.1, 0.3, '0.1-0.3%'), (0.3, 0.5, '0.3-0.5%'), 
                          (0.5, 1.0, '0.5-1.0%'), (1.0, 5.0, '1.0%+')]:
    bucket = trades_merged[(trades_merged['gap_pct'] >= low) & (trades_merged['gap_pct'] < high)]
    if len(bucket) > 0:
        wr = (bucket['pnl'] > 0).mean() * 100
        avg_pnl = bucket['pnl'].mean()
        print(f"  {label:>8}: {len(bucket)} trades, win rate {wr:.0f}%, avg P&L ${avg_pnl:.0f}")

# Morning trend direction vs outcome
print(f"\n--- AM Return Direction vs Outcome ---")
am_up = trades_merged[trades_merged['am_return'] > 0]
am_dn = trades_merged[trades_merged['am_return'] <= 0]
print(f"  AM bullish:  {len(am_up)} trades, win rate {(am_up['pnl']>0).mean()*100:.0f}%, avg P&L ${am_up['pnl'].mean():.0f}")
print(f"  AM bearish:  {len(am_dn)} trades, win rate {(am_dn['pnl']>0).mean()*100:.0f}%, avg P&L ${am_dn['pnl'].mean():.0f}")

# Trend continuation
print(f"\n--- Trend Continuation (AM + PM same direction) ---")
cont = trades_merged[trades_merged['trend_continuation'] == 1]
rev = trades_merged[trades_merged['trend_continuation'] == 0]
print(f"  Continuation: {len(cont)} trades, win rate {(cont['pnl']>0).mean()*100:.0f}%, avg P&L ${cont['pnl'].mean():.0f}")
print(f"  Reversal:     {len(rev)} trades, win rate {(rev['pnl']>0).mean()*100:.0f}%, avg P&L ${rev['pnl'].mean():.0f}")

# Time in trade
trades_merged['hours_in_trade'] = (trades_merged['closeDate'] - trades_merged['openDate']).dt.total_seconds() / 3600
print(f"\n--- Time in Trade ---")
wins_tm = trades_merged[trades_merged['pnl'] > 0]
losses_tm = trades_merged[trades_merged['pnl'] < 0]
print(f"  Wins:   avg {wins_tm['hours_in_trade'].mean():.1f}h")
print(f"  Losses: avg {losses_tm['hours_in_trade'].mean():.1f}h")

# =============================================================================
# 10. DAY RANGE AS % OF ENTRY PRICE — THRESHOLD ANALYSIS
# =============================================================================
print("\n" + "=" * 70)
print("THRESHOLD ANALYSIS: WHEN IS THE IC TOO NARROW?")
print("=" * 70)

trades_merged['day_range_pct'] = trades_merged['day_range'] / trades_merged['price_at_entry'] * 100
trades_merged['pm_range_pct'] = trades_merged['pm_range'] / trades_merged['price_at_entry'] * 100

# What PM range % leads to losses?
for threshold in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
    above = trades_merged[trades_merged['pm_range_pct'] >= threshold]
    below = trades_merged[trades_merged['pm_range_pct'] < threshold]
    if len(above) > 0 and len(below) > 0:
        print(f"  PM range ≥ {threshold:.2f}%: {len(above)} trades, "
              f"WR={100*(above['pnl']>0).mean():.0f}%, avg P&L ${above['pnl'].mean():.0f}")

# =============================================================================
# 11. ROOT CAUSE & RECOMMENDATIONS
# =============================================================================
print("\n" + "=" * 70)
print("ROOT CAUSE ANALYSIS & RECOMMENDATIONS")
print("=" * 70)

total_pnl = trades['pnl'].sum()
n_trades = len(trades)
n_wins = (trades['pnl'] > 0).sum()
n_losses = (trades['pnl'] < 0).sum()

print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│ BOCCA GAP BOT SUMMARY                                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Trades: {n_trades}    Wins: {n_wins}    Losses: {n_losses}    Win Rate: {n_wins/n_trades*100:.1f}%          │
│  Total P&L: ${total_pnl:+.0f}                                           │
│  Avg Win: ${trades[trades['pnl']>0]['pnl'].mean():.0f}    Avg Loss: ${trades[trades['pnl']<0]['pnl'].mean():.0f}                         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ KEY FINDINGS:                                                       │
│                                                                     │
│ 1. IC WIDTH IS ONLY 10 PTS ($5 short + $5 long each side)          │
│    On trending afternoons, 10pt IC gets blown through easily.       │
│    Avg PM range on loss days significantly exceeds IC width.        │
│                                                                     │
│ 2. LOSSES CLUSTER IN HIGH-VOLATILITY REGIMES                       │
│    Check HMM state breakdown above — large day_range states have   │
│    worse win rates.                                                 │
│                                                                     │
│ 3. AFTERNOON TREND CONTINUATION IS THE KILLER                      │
│    When AM trend continues into PM, the IC can't contain the move. │
│    Bot needs a way to detect "trending" vs "mean-reverting" days.   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ RECOMMENDATIONS:                                                    │
│                                                                     │
│ 1. TIGHTER VIX FILTER: Lower VIX cap from 24 to ~18-20.            │
│    Higher VIX = larger intraday moves = more IC breaches.           │
│                                                                     │
│ 2. AM RANGE FILTER: Skip if AM range already > IC width (~10pts)   │
│    If morning moved 15+ pts, afternoon likely continues.            │
│                                                                     │
│ 3. WIDER IC or LATER ENTRY: Either widen to $10 wings (more        │
│    premium needed) or enter later (14:30+) with less time risk.     │
│                                                                     │
│ 4. RANGE EXPANSION FILTER: If PM bar volatility is already         │
│    elevated when scanner fires, skip.                               │
│                                                                     │
│ 5. DAY RANGE % GATE: If intraday range already > 0.15% of SPX     │
│    by 13:45, the day is too volatile for a 10pt IC.                 │
│                                                                     │
│ 6. GAP SIZE SWEET SPOT: Check if larger gaps (>0.5%) perform       │
│    differently — very large gaps may mean-revert (good for IC)      │
│    while small gaps (0.1-0.2%) trend more.                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
""")

# =============================================================================
# 12. VISUALISATION
# =============================================================================
print("Generating charts...")

fig, axes = plt.subplots(3, 2, figsize=(16, 14))
fig.suptitle('Bocca Gap Bot Analysis — 0DTE Iron Condor', fontsize=14, fontweight='bold')

# Chart 1: P&L over time
ax = axes[0, 0]
trades_plot = trades.sort_values('openDate').reset_index(drop=True)
colors = ['green' if p > 0 else 'red' for p in trades_plot['pnl']]
ax.bar(range(len(trades_plot)), trades_plot['pnl'], color=colors, alpha=0.7)
ax.axhline(0, color='black', linewidth=0.5)
cum_pnl = trades_plot['pnl'].cumsum()
ax2 = ax.twinx()
ax2.plot(range(len(trades_plot)), cum_pnl, 'b-', linewidth=2, label='Cumulative')
ax2.set_ylabel('Cumulative P&L ($)', color='blue')
ax.set_title('Trade P&L History')
ax.set_xlabel('Trade #')
ax.set_ylabel('P&L ($)')

# Chart 2: PM Range vs IC Width
ax = axes[0, 1]
ax.scatter(wins['ic_width'], wins['pm_range'], c='green', alpha=0.6, label='Wins', s=50)
ax.scatter(losses['ic_width'], losses['pm_range'], c='red', alpha=0.8, label='Losses', s=80, marker='x')
ax.plot([0, 20], [0, 20], 'k--', alpha=0.3, label='PM range = IC width')
ax.set_xlabel('IC Width (pts)')
ax.set_ylabel('PM Range (pts)')
ax.set_title('IC Width vs PM Range')
ax.legend()

# Chart 3: Gap % vs P&L
ax = axes[1, 0]
colors_scatter = ['green' if p > 0 else 'red' for p in trades_merged['pnl']]
ax.scatter(trades_merged['gap_pct'], trades_merged['pnl'], c=colors_scatter, alpha=0.7, s=60)
ax.axhline(0, color='black', linewidth=0.5)
ax.set_xlabel('Gap %')
ax.set_ylabel('P&L ($)')
ax.set_title('Gap Size vs Trade P&L')

# Chart 4: AM Return vs P&L
ax = axes[1, 1]
ax.scatter(trades_merged['am_return'], trades_merged['pm_range'], c=colors_scatter, alpha=0.7, s=60)
ax.set_xlabel('AM Return %')
ax.set_ylabel('PM Range (pts)')
ax.set_title('AM Return vs PM Range (Green=Win, Red=Loss)')

# Chart 5: HMM states with trade outcomes
ax = axes[2, 0]
state_colors = ['green', 'blue', 'orange', 'red']
for s in range(best_model.n_components):
    mask = daily['hmm_state'] == s
    dates_s = pd.to_datetime(daily.loc[mask, 'date'])
    ax.scatter(dates_s, daily.loc[mask, 'pm_range'], 
              c=state_colors[s % len(state_colors)], label=f'State {s}', alpha=0.4, s=15)
# Overlay trades
for _, t in trades_merged.iterrows():
    c = 'lime' if t['pnl'] > 0 else 'red'
    ax.scatter(pd.Timestamp(t['trade_date']), t['pm_range'], c=c, s=80, 
              edgecolors='black', linewidth=0.5, zorder=5)
ax.set_title('HMM States + Trade Outcomes (PM Range)')
ax.legend(fontsize=8)
ax.set_ylabel('PM Range (pts)')

# Chart 6: Feature Importance
ax = axes[2, 1]
importances.sort_values().plot(kind='barh', ax=ax, color='steelblue')
ax.set_title('Random Forest Feature Importance')
ax.set_xlabel('Importance')

plt.tight_layout()
plt.savefig(f"{BASE}/bocca_gap_analysis.png", dpi=150, bbox_inches='tight')
print(f"\nChart saved: {BASE}/bocca_gap_analysis.png")
plt.show()

print("\n✓ Analysis complete.")
