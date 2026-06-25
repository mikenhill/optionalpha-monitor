import sys, sqlite3
sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
from gex_viewer import _load_hmm, _snap_to_hmm_row, _db

model, scaler, labels = _load_hmm()

with _db() as con:
    rows = con.execute(
        'SELECT ntime, spx_last, net_gex, kcs, sentiment, key_strike, total_put_vol '
        'FROM live_captures WHERE ndate=20260624 ORDER BY ntime'
    ).fetchall()

print('Pre-market snapshots (ntime, net_gex, kcs, sentiment, dist_to_key, put_vol):')
for row in rows:
    ntime, spx_last, net_gex, kcs, sentiment, key_strike, total_put_vol = row
    dist = abs((spx_last or 0) - (key_strike or 0))
    print(f'  {ntime:04d}  net_gex={net_gex:>12.0f}  kcs={kcs:>6.1f}  sentiment={sentiment:>6.0f}  dist={dist:>6.0f}  put_vol={total_put_vol:>8.0f}')

print()
print('State means (inverse-transformed to original scale):')
print(f'  {"State":<20}  {"net_gex_B":>12}  {"kcs":>6}  {"sentiment":>8}  {"dist":>6}  {"put_vol_K":>10}')
import numpy as np
means_raw = scaler.inverse_transform(model.means_)
for i, lbl in enumerate(labels):
    print(f'  {lbl:<20}  {means_raw[i,0]:>12.3f}  {means_raw[i,1]:>6.1f}  {means_raw[i,2]:>8.1f}  {means_raw[i,3]:>6.1f}  {means_raw[i,4]:>10.1f}')
