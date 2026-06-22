import json
from pathlib import Path
from process_gex_window import load_result, find_api_response, select_strike_window, value

result = load_result(r'results\20260608_143440_SPX_SPX_20260608.json')
gex = find_api_response(result, 'market.gex')
gex_data = gex.get('data') or {}
rows_all = gex_data.get('data') or []
last = gex_data.get('last')
rows, nearest = select_strike_window(rows_all, last)

total_cg = sum(value(r, 'cg') for r in rows)
total_pg = sum(value(r, 'pg') for r in rows)
net_window = total_cg + total_pg

callsum = gex_data.get('callsum', 0)
putsum = gex_data.get('putsum', 0)
net_full = callsum + putsum

print(f"Window strikes : {len(rows)}")
print(f"Strike range   : {rows[0]['strike']} - {rows[-1]['strike']}")
print(f"Sum cg (window): {total_cg/1e9:.3f}B")
print(f"Sum pg (window): {total_pg/1e9:.3f}B")
print(f"Net GEX (window cg+pg)  : {net_window/1e9:.3f}B")
print(f"callsum (full chain)    : {callsum/1e9:.3f}B")
print(f"putsum  (full chain)    : {putsum/1e9:.3f}B")
print(f"Net GEX (callsum+putsum): {net_full/1e9:.3f}B")

# Also check 'total' field sum
net_total_field = sum(value(r, 'total') for r in rows)
print(f"Sum 'total' field (window): {net_total_field/1e9:.3f}B")
