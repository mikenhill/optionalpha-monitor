import sys
sys.path.insert(0, '.')
from gex_viewer import load_gex_snapshot, summarise_snapshot

# Simulate what the API does
date_iso = "2026-06-25"
ntime = 1000

# Load
data = load_gex_snapshot(date_iso, ntime, "SPX")
print(f"Loaded data keys: {list(data.keys())[:10]}...")

# Summarise
snap = summarise_snapshot(data)
print(f"\nSummary keys: {list(snap.keys())}")
print(f"\nSummary values:")
for key in ['uprice', 'net_gex', 'kcs', 'sentiment_pct', 'gex_ratio']:
    print(f"  {key}: {snap.get(key)}")

# Check what the API would return in the snapshot field
api_response = {
    "snapshot": snap
}
print(f"\nAPI response snapshot keys: {list(api_response['snapshot'].keys())}")
