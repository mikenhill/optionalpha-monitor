import sys
sys.path.insert(0, '.')
from gex_viewer import load_gex_snapshot

# Test loading 10:00 snapshot
data = load_gex_snapshot("2026-06-25", 1000, "SPX")

if data:
    print("Keys in loaded data:")
    for key in sorted(data.keys()):
        value = data[key]
        if isinstance(value, (int, float)):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {type(value).__name__}")
    
    print(f"\nnet_gex in data: {'net_gex' in data}")
    print(f"net_gex value: {data.get('net_gex')}")
    print(f"net_gex is None: {data.get('net_gex') is None}")
else:
    print("Failed to load snapshot")
