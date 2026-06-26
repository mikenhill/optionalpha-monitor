import sqlite3
import json

def _compute_flat_summary(data):
    """Compute flat summary columns from raw JSON data."""
    if isinstance(data, str):
        data = json.loads(data)
    
    # Handle both dict with 'data' key and direct list
    if isinstance(data, dict):
        rows = data.get("data") or []
        uprice = data.get("uprice", 0)
    elif isinstance(data, list):
        rows = data
        uprice = 0
    else:
        return {}
    
    print(f"  uprice from data: {uprice}")
    print(f"  rows count: {len(rows)}")
    
    if not rows:
        return {}
    
    valid = [r for r in rows if r.get("strike") is not None]
    print(f"  valid rows: {len(valid)}")
    
    # 40-strike window
    below = [r for r in valid if r["strike"] < uprice]
    above = [r for r in valid if r["strike"] >= uprice]
    window_rows = below[-20:] + above[:20]
    print(f"  below: {len(below)}, above: {len(above)}, window: {len(window_rows)}")
    
    if not window_rows:
        return {}
    
    # Calculate all flat columns
    net = sum(r.get("net", 0) or 0 for r in window_rows)
    cg = sum(r.get("cg", 0) or 0 for r in window_rows)
    pg = sum(r.get("pg", 0) or 0 for r in window_rows)
    
    print(f"  net: {net}, cg: {cg}, pg: {pg}")
    
    return {"net_gex": net, "total_call_gex": cg, "total_put_gex": pg}

con = sqlite3.connect('gex.db')

# Test on 10:00 snapshot
cursor = con.execute(
    'SELECT ndate, ntime, data FROM gex_snapshots WHERE ndate=20260625 AND ntime=1000 AND symbol="SPX"'
)
row = cursor.fetchone()

if row:
    ndate, ntime, data_json = row
    print(f"Testing on {ndate}-{ntime}")
    result = _compute_flat_summary(data_json)
    print(f"Result: {result}")
else:
    print("Snapshot not found")

con.close()
