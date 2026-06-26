import requests

base_url = 'http://localhost:5050'

print('=== 2026-06-25 Pre-market snapshots from API ===')
times = [528, 751]
for ntime in times:
    url = f'{base_url}/api/snapshot?date=2026-06-25&time={ntime}'
    try:
        r = requests.get(url)
        data = r.json()
        snap = data.get('snapshot', {})
        print(f'  ntime={ntime:04d}: sentiment={snap.get("sentiment", 0):.0f}%, uprice={snap.get("uprice", 0):.2f}, net_gex={snap.get("net_gex", 0):,.0f}, kcs={snap.get("kcs", 0):.1f}')
    except Exception as e:
        print(f'  ntime={ntime:04d}: ERROR - {e}')

print('\n=== 2026-06-25 RTH snapshots (10:00, 10:01, 10:32, 10:58, 11:35) from API ===')
times = [1000, 1001, 1032, 1058, 1135]
for ntime in times:
    url = f'{base_url}/api/snapshot?date=2026-06-25&time={ntime}'
    try:
        r = requests.get(url)
        data = r.json()
        snap = data.get('snapshot', {})
        print(f'  ntime={ntime:04d}: sentiment={snap.get("sentiment", 0):.0f}%, uprice={snap.get("uprice", 0):.2f}, net_gex={snap.get("net_gex", 0):,.0f}, kcs={snap.get("kcs", 0):.1f}')
    except Exception as e:
        print(f'  ntime={ntime:04d}: ERROR - {e}')
