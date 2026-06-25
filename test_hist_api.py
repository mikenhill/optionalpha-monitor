import urllib.request, json
r = urllib.request.urlopen('http://localhost:5050/api/metric/history?metric=net_gex')
d = json.loads(r.read())
print(f"Values: {len(d.get('values',[]))}, Current: {d.get('current_value')}, Percentile: {d.get('percentile')}")
