import sys
sys.path.insert(0, '.')
from gex_viewer import load_gex_snapshot, summarise_snapshot

# Load snapshot
data = load_gex_snapshot("2026-06-25", 1000, "SPX")

print("Before summarise_snapshot:")
print(f"  net_gex in data: {'net_gex' in data}")
print(f"  net_gex value: {data.get('net_gex')}")
print(f"  net_gex is None: {data.get('net_gex') is None}")

# Summarise
summary = summarise_snapshot(data)

print("\nAfter summarise_snapshot:")
print(f"  net_gex: {summary.get('net_gex')}")
print(f"  kcs: {summary.get('kcs')}")
print(f"  sentiment_pct: {summary.get('sentiment_pct')}")
