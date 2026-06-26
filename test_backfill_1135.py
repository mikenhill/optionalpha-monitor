import sqlite3
import json
from gex_viewer import _compute_flat_summary

con = sqlite3.connect('gex.db')
cursor = con.execute('''
    SELECT ndate, ntime, data, uprice 
    FROM gex_snapshots 
    WHERE ndate=20260625 AND ntime=1135 AND symbol='SPX'
''')
row = cursor.fetchone()
if row:
    ndate, ntime, data_json, uprice = row
    print(f'Processing {ndate} {ntime}: uprice={uprice}')
    data_list = json.loads(data_json)
    print(f'Data type: {type(data_list)}, length: {len(data_list)}')
    
    # Re-calculate summary
    summary = _compute_flat_summary({'uprice': uprice, 'data': data_list})
    
    print(f'Summary results:')
    print(f'  total_put_gex: {summary.get("put_gex", 0):,.2f}')
    print(f'  total_call_gex: {summary.get("call_gex", 0):,.2f}')
    print(f'  net_gex: {summary.get("net_gex", 0):,.2f}')
else:
    print('No row found')
con.close()
