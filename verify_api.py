"""Verify API output for 2026-06-17 11:00 matches OptionAlpha."""
import requests
r = requests.get("http://localhost:5051/api/snapshot", params={"date": "2026-06-17", "time": 1100})
d = r.json()
s = d["summary"]
print(f"Sentiment: {s['sentiment_pct']}%  (OA: 40%)")
print(f"Ratio: {s['gex_ratio']}x  (OA: -1.2x)")
print(f"Net: {s['net_gex']/1e9:.2f}B  (OA: -1.7B)")
print(f"OI  Calls: {s['total_call_oi']/1000:.1f}K (OA: 46K)  Puts: {s['total_put_oi']/1000:.1f}K (OA: 47.1K)")
print(f"Vol Calls: {s['total_call_vol']/1000:.1f}K (OA: 268.1K)  Puts: {s['total_put_vol']/1000:.1f}K (OA: 312.9K)")
print(f"Strikes: {len(d['strikes'])} ({d['strikes'][0]} - {d['strikes'][-1]})")
print(f"Day type: {d['day_type']['label']}")
