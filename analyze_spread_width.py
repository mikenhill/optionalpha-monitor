"""
Analyze SPX breakout bot performance with $5 vs $15 spread widths.

Breakout rules:
- Opening range: first 60 mins from 09:30 ET (09:30–10:30)
- Bullish breakout: high > OR_high AND low >= OR_low AND OR_width >= 0.2% of open AND ADX(14) > 15
- Bearish breakout: low < OR_low AND high <= OR_high AND OR_width >= 0.2% of open AND ADX(14) > 15

Trade structure:
- Short Put Spread (bullish): short leg = OR_low - $0.01, long leg = short_leg - $15 (or $5)
- Short Call Spread (bearish): short leg = OR_high + $0.01, long leg = short_leg + $15 (or $5)
"""

import pandas as pd
import numpy as np
from pathlib import Path


def calculate_adx(df, period=14):
    """Calculate ADX(14) from OHLC data."""
    df = df.copy()
    
    # True Range
    df['tr1'] = df['High'] - df['Low']
    df['tr2'] = abs(df['High'] - df['Close'].shift(1))
    df['tr3'] = abs(df['Low'] - df['Close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    
    # Directional Movement
    df['plus_dm'] = np.where(
        (df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
        np.maximum(df['High'] - df['High'].shift(1), 0),
        0
    )
    df['minus_dm'] = np.where(
        (df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
        np.maximum(df['Low'].shift(1) - df['Low'], 0),
        0
    )
    
    # Smoothed averages
    df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
    df['plus_di'] = 100 * (df['plus_dm'].ewm(span=period, adjust=False).mean() / df['atr'])
    df['minus_di'] = 100 * (df['minus_dm'].ewm(span=period, adjust=False).mean() / df['atr'])
    
    # DX and ADX
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].ewm(span=period, adjust=False).mean()
    
    return df


def analyze_breakouts(csv_path):
    """Main analysis function."""
    # Load data
    df = pd.read_csv(csv_path)
    df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%m/%d/%Y %H:%M')
    df = df.sort_values('DateTime').reset_index(drop=True)
    
    # Calculate ADX(14)
    df = calculate_adx(df)
    
    # Extract date and time components
    df['Date_only'] = df['DateTime'].dt.date
    df['Time_only'] = df['DateTime'].dt.time
    
    results = []
    
    for date in df['Date_only'].unique():
        day_data = df[df['Date_only'] == date].copy()
        
        # Find opening range (09:30–10:30 ET)
        or_data = day_data[(day_data['Time_only'] >= pd.to_datetime('09:30').time()) & 
                          (day_data['Time_only'] <= pd.to_datetime('10:30').time())]
        
        if len(or_data) == 0:
            continue
        
        or_high = or_data['High'].max()
        or_low = or_data['Low'].min()
        or_open = or_data.iloc[0]['Open']  # 09:30 open
        or_width = or_high - or_low
        or_width_pct = or_width / or_open
        
        # Skip if OR width < 0.2%
        if or_width_pct < 0.002:
            continue
        
        # Post-OR data (after 10:30)
        post_or = day_data[day_data['Time_only'] > pd.to_datetime('10:30').time()].copy()
        
        if len(post_or) == 0:
            continue
        
        # Track day high/low from start of OR through end of day
        day_high_from_or = day_data['High'].max()
        day_low_from_or = day_data['Low'].min()
        
        # Find first bullish breakout bar (after 10:30)
        bullish_breakout = None
        for idx, row in post_or.iterrows():
            # Bullish: current bar high > OR_high AND current bar low >= OR_low AND ADX > 15
            if row['High'] > or_high and row['Low'] >= or_low and row['adx'] > 15:
                bullish_breakout = {
                    'datetime': row['DateTime'],
                    'entry_high': row['High'],
                    'entry_low': row['Low'],
                    'entry_close': row['Close'],
                    'adx_at_entry': row['adx'],
                    'or_high': or_high,
                    'or_low': or_low,
                    'or_width': or_width,
                    'or_width_pct': or_width_pct
                }
                break
        
        # Find first bearish breakout bar (after 10:30)
        bearish_breakout = None
        for idx, row in post_or.iterrows():
            # Bearish: current bar low < OR_low AND current bar high <= OR_high AND ADX > 15
            if row['Low'] < or_low and row['High'] <= or_high and row['adx'] > 15:
                bearish_breakout = {
                    'datetime': row['DateTime'],
                    'entry_high': row['High'],
                    'entry_low': row['Low'],
                    'entry_close': row['Close'],
                    'adx_at_entry': row['adx'],
                    'or_high': or_high,
                    'or_low': or_low,
                    'or_width': or_width,
                    'or_width_pct': or_width_pct
                }
                break
        
        # Analyze outcomes
        if bullish_breakout:
            # Short Put Spread trade parameters
            short_leg = or_low - 0.01
            long_leg_5 = short_leg - 5
            long_leg_15 = short_leg - 15
            
            # Find max adverse excursion (how far did price go against the trade?)
            # For short put spread, adverse move is price dropping below short_leg
            post_entry = day_data[day_data['DateTime'] > bullish_breakout['datetime']]
            
            if len(post_entry) > 0:
                lowest_low_after_entry = post_entry['Low'].min()
                
                # Did price hit the long leg strikes?
                hit_5_width = lowest_low_after_entry <= long_leg_5
                hit_15_width = lowest_low_after_entry <= long_leg_15
                
                # Max loss scenarios
                max_loss_5 = min(5, max(0, short_leg - lowest_low_after_entry))
                max_loss_15 = min(15, max(0, short_leg - lowest_low_after_entry))
                
                # Did it reverse and become profitable?
                final_close = day_data.iloc[-1]['Close']
                profitable_exit = final_close >= short_leg  # Both legs expire worthless
                
                results.append({
                    'date': date,
                    'direction': 'bullish',
                    'or_high': or_high,
                    'or_low': or_low,
                    'or_width': or_width,
                    'or_width_pct': or_width_pct,
                    'entry_time': bullish_breakout['datetime'],
                    'entry_close': bullish_breakout['entry_close'],
                    'adx_at_entry': bullish_breakout['adx_at_entry'],
                    'short_leg': short_leg,
                    'long_leg_5': long_leg_5,
                    'long_leg_15': long_leg_15,
                    'lowest_low_after_entry': lowest_low_after_entry,
                    'max_excursion': short_leg - lowest_low_after_entry,
                    'hit_5_width': hit_5_width,
                    'hit_15_width': hit_15_width,
                    'final_close': final_close,
                    'profitable_exit': profitable_exit,
                    'max_loss_5': max_loss_5,
                    'max_loss_15': max_loss_15
                })
        
        if bearish_breakout:
            # Short Call Spread trade parameters
            short_leg = or_high + 0.01
            long_leg_5 = short_leg + 5
            long_leg_15 = short_leg + 15
            
            post_entry = day_data[day_data['DateTime'] > bearish_breakout['datetime']]
            
            if len(post_entry) > 0:
                highest_high_after_entry = post_entry['High'].max()
                
                hit_5_width = highest_high_after_entry >= long_leg_5
                hit_15_width = highest_high_after_entry >= long_leg_15
                
                max_loss_5 = min(5, max(0, highest_high_after_entry - short_leg))
                max_loss_15 = min(15, max(0, highest_high_after_entry - short_leg))
                
                final_close = day_data.iloc[-1]['Close']
                profitable_exit = final_close <= short_leg
                
                results.append({
                    'date': date,
                    'direction': 'bearish',
                    'or_high': or_high,
                    'or_low': or_low,
                    'or_width': or_width,
                    'or_width_pct': or_width_pct,
                    'entry_time': bearish_breakout['datetime'],
                    'entry_close': bearish_breakout['entry_close'],
                    'adx_at_entry': bearish_breakout['adx_at_entry'],
                    'short_leg': short_leg,
                    'long_leg_5': long_leg_5,
                    'long_leg_15': long_leg_15,
                    'highest_high_after_entry': highest_high_after_entry,
                    'max_excursion': highest_high_after_entry - short_leg,
                    'hit_5_width': hit_5_width,
                    'hit_15_width': hit_15_width,
                    'final_close': final_close,
                    'profitable_exit': profitable_exit,
                    'max_loss_5': max_loss_5,
                    'max_loss_15': max_loss_15
                })
    
    return pd.DataFrame(results)


def print_analysis(results_df):
    """Print comprehensive analysis."""
    if len(results_df) == 0:
        print("No breakouts found matching criteria.")
        return
    
    print("=" * 80)
    print("SPX BREAKOUT BOT ANALYSIS: $5 vs $15 SPREAD WIDTHS")
    print("=" * 80)
    print(f"\nTotal breakouts analyzed: {len(results_df)}")
    print(f"  Bullish: {len(results_df[results_df['direction'] == 'bullish'])}")
    print(f"  Bearish: {len(results_df[results_df['direction'] == 'bearish'])}")
    
    # Overall profitability
    win_rate = results_df['profitable_exit'].mean() * 100
    print(f"\nOverall win rate (full profit): {win_rate:.1f}%")
    
    # $5 Width Analysis
    print("\n" + "=" * 80)
    print("$5 SPREAD WIDTH ANALYSIS")
    print("=" * 80)
    
    hit_5 = results_df['hit_5_width'].sum()
    hit_15 = results_df['hit_15_width'].sum()
    
    print(f"\nTrades hitting $5 long leg (max loss): {hit_5} / {len(results_df)} ({hit_5/len(results_df)*100:.1f}%)")
    print(f"Trades hitting $15 long leg (max loss): {hit_15} / {len(results_df)} ({hit_15/len(results_df)*100:.1f}%)")
    
    # Trades that blow through $15 (where $15 was necessary)
    blow_through_15 = len(results_df[results_df['hit_15_width'] == True])
    print(f"\nTrades blowing through $15 (where $15 wings were load-bearing): {blow_through_15} ({blow_through_15/len(results_df)*100:.1f}%)")
    
    # Trades stopped at $5-$15 range (where $5 would have been hit but $15 saves you)
    saved_by_15 = len(results_df[(results_df['hit_5_width'] == True) & (results_df['hit_15_width'] == False)])
    print(f"Trades where $5 would have been hit but $15 saves: {saved_by_15} ({saved_by_15/len(results_df)*100:.1f}%)")
    
    # Median adverse excursion
    median_excursion = results_df['max_excursion'].median()
    mean_excursion = results_df['max_excursion'].mean()
    print(f"\nMedian adverse excursion: ${median_excursion:.2f}")
    print(f"Mean adverse excursion: ${mean_excursion:.2f}")
    
    # Distribution of max excursions
    print(f"\nDistribution of adverse excursions:")
    print(f"  0-$5: {len(results_df[results_df['max_excursion'] < 5])} trades ({len(results_df[results_df['max_excursion'] < 5])/len(results_df)*100:.1f}%)")
    print(f"  $5-$10: {len(results_df[(results_df['max_excursion'] >= 5) & (results_df['max_excursion'] < 10)])} trades")
    print(f"  $10-$15: {len(results_df[(results_df['max_excursion'] >= 10) & (results_df['max_excursion'] < 15)])} trades")
    print(f"  $15+: {len(results_df[results_df['max_excursion'] >= 15])} trades ({len(results_df[results_df['max_excursion'] >= 15])/len(results_df)*100:.1f}%)")
    
    # Risk-adjusted breakeven
    print("\n" + "=" * 80)
    print("RISK-ADJUSTED BREAKEVEN ANALYSIS")
    print("=" * 80)
    
    # Assume $15 spread collects ~3x the credit of $5 spread (conservative)
    # If $5 collects $1.00, $15 collects $3.00
    # Breakeven = max_loss_rate / (max_loss_rate + win_credit)
    
    for credit_ratio in [2.0, 2.5, 3.0, 3.5]:
        print(f"\nAssuming ${credit_ratio:.1f}x credit for $15 spread vs $5 spread:")
        
        # $5 spread
        loss_rate_5 = hit_5 / len(results_df)
        win_credit_5 = 1.0
        loss_amount_5 = 5.0 - win_credit_5  # Net loss
        breakeven_5 = (loss_amount_5 * loss_rate_5) / (win_credit_5 * (1 - loss_rate_5) + loss_amount_5 * loss_rate_5)
        required_win_rate_5 = breakeven_5 * 100
        
        # $15 spread
        loss_rate_15 = hit_15 / len(results_df)
        win_credit_15 = credit_ratio
        loss_amount_15 = 15.0 - win_credit_15
        breakeven_15 = (loss_amount_15 * loss_rate_15) / (win_credit_15 * (1 - loss_rate_15) + loss_amount_15 * loss_rate_15)
        required_win_rate_15 = breakeven_15 * 100
        
        print(f"  $5 spread: Need {required_win_rate_5:.1f}% win rate to breakeven")
        print(f"  $15 spread: Need {required_win_rate_15:.1f}% win rate to breakeven")
    
    # Detailed trade list
    print("\n" + "=" * 80)
    print("DETAILED TRADE LIST")
    print("=" * 80)
    
    for _, row in results_df.iterrows():
        print(f"\n{row['date']} - {row['direction'].upper()} breakout at {row['entry_time'].strftime('%H:%M')}")
        print(f"  OR: {row['or_low']:.2f} - {row['or_high']:.2f} (width: {row['or_width_pct']*100:.2f}%)")
        print(f"  Entry close: {row['entry_close']:.2f}, ADX: {row['adx_at_entry']:.1f}")
        print(f"  Short leg: {row['short_leg']:.2f}")
        
        if row['direction'] == 'bullish':
            print(f"  Lowest low after entry: {row['lowest_low_after_entry']:.2f}")
        else:
            print(f"  Highest high after entry: {row['highest_high_after_entry']:.2f}")
        
        print(f"  Max excursion: ${row['max_excursion']:.2f}")
        print(f"  Hit $5 width: {'YES' if row['hit_5_width'] else 'NO'}, Hit $15 width: {'YES' if row['hit_15_width'] else 'NO'}")
        print(f"  Final close: {row['final_close']:.2f}, Profitable: {'YES' if row['profitable_exit'] else 'NO'}")
    
    return results_df


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = "spx-5min.csv"
    
    print(f"Analyzing: {csv_path}")
    results = analyze_breakouts(csv_path)
    print_analysis(results)
    
    # Save results
    output_path = Path(csv_path).with_suffix('.analysis.csv')
    results.to_csv(output_path, index=False)
    print(f"\n\nDetailed results saved to: {output_path}")
