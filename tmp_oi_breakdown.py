import pathlib
from datetime import date
from process_gex_window import load_result, find_api_response, select_strike_window

today = date.today().strftime('%Y%m%d')
files = [f for f in sorted(pathlib.Path('results').glob(today + '_*_SPX_SPX_*.json')) if 'gex_summary' not in f.name]
print(f"Files found: {files}")
if not files:
    print("No files found")
    exit(1)

result = load_result(files[-1])
gex = find_api_response(result, 'market.gex')
gex_data = gex.get('data') or {}
rows = gex_data.get('data') or []
last = gex_data.get('last')
rows, _ = select_strike_window(rows, last)

def v(r, k):
    return r.get(k) or 0

sorted_rows = sorted(rows, key=lambda r: v(r, 'coi') + v(r, 'poi'), reverse=True)
print('Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX')
for r in sorted_rows[:10]:
    s = r.get('strike')
    c = v(r, 'coi')
    p = v(r, 'poi')
    a = round(v(r, 'abs') / 1e9, 3)
    print(f"{s} | {c} | {p} | {c + p} | {c - p} | {a} B")

print('\n--- KEY2 (7550) ---')
for r in rows:
    if r.get('strike') == 7550:
        print(f"key2 {r.get('strike')} | coi={v(r, 'coi')} | poi={v(r, 'poi')} | net_oi={v(r, 'coi') - v(r, 'poi')} | abs={round(v(r, 'abs') / 1e9, 3)} B")
