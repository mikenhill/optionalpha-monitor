#!/usr/bin/env python3
"""Generate trade signals performance report."""

import sqlite3

DB_PATH = r"G:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("TRADE SIGNALS PERFORMANCE REPORT")
print("=" * 60)
print()

# Overall stats
cursor.execute("SELECT COUNT(*) FROM trade_signals")
total = cursor.fetchone()[0]
print(f"Total Trade Signals: {total}")

cursor.execute("SELECT outcome, COUNT(*) FROM trade_signals GROUP BY outcome")
outcomes = dict(cursor.fetchall())
print(f"\nOutcome Distribution:")
for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
    if outcome:
        pct = count / total * 100
        print(f"  {outcome:10s}: {count:4d} ({pct:5.1f}%)")

# Performance by structure
print(f"\n{'='*60}")
print("PERFORMANCE BY TRADE STRUCTURE")
print(f"{'='*60}")

cursor.execute("""
    SELECT structure, outcome, COUNT(*) 
    FROM trade_signals 
    WHERE outcome IS NOT NULL 
    GROUP BY structure, outcome
    ORDER BY structure, outcome
""")
rows = cursor.fetchall()

structures = {}
for structure, outcome, count in rows:
    if structure not in structures:
        structures[structure] = {}
    structures[structure][outcome] = count

for structure in sorted(structures.keys()):
    print(f"\n{structure}:")
    total_for_structure = sum(structures[structure].values())
    for outcome in ['WIN', 'CORRECT', 'PARTIAL', 'NEUTRAL', 'MISSED', 'LOSS']:
        count = structures[structure].get(outcome, 0)
        if count > 0:
            pct = count / total_for_structure * 100
            print(f"  {outcome:10s}: {count:4d} ({pct:5.1f}%)")

# Financial performance
print(f"\n{'='*60}")
print("FINANCIAL PERFORMANCE (P&L Points)")
print(f"{'='*60}")

cursor.execute("""
    SELECT action, SUM(outcome_points), AVG(outcome_points), COUNT(*) 
    FROM trade_signals 
    WHERE outcome_points IS NOT NULL 
    GROUP BY action
""")
rows = cursor.fetchall()

for action, total_points, avg_points, count in rows:
    if action and count > 0:
        print(f"{action:8s}: Total {total_points:7.1f} | Avg {avg_points:6.2f} | Trades: {count:3d}")

# Win rate by action
print(f"\n{'='*60}")
print("WIN RATE BY ACTION")
print(f"{'='*60}")

cursor.execute("""
    SELECT action, 
           SUM(CASE WHEN outcome IN ('WIN', 'CORRECT', 'PARTIAL') THEN 1 ELSE 0 END) as wins,
           COUNT(*) as total
    FROM trade_signals 
    WHERE outcome IS NOT NULL 
    GROUP BY action
""")
rows = cursor.fetchall()

for action, wins, total in rows:
    if action and total > 0:
        win_rate = wins / total * 100
        print(f"{action:8s}: {wins:3d}/{total:3d} ({win_rate:5.1f}%)")

conn.close()
