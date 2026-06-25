import sys
from collections import defaultdict
sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
from gex_viewer import predict_hmm_sequence, _db

# Group all live_captures by ndate, predict as sequence per day
with _db() as con:
    rows = con.execute(
        'SELECT id, ndate, ntime, spx_last, net_gex, kcs, sentiment, key_strike, total_put_vol '
        'FROM live_captures ORDER BY ndate, ntime'
    ).fetchall()

by_date = defaultdict(list)
for row in rows:
    by_date[row[1]].append(row)

total = 0
with _db() as con:
    for ndate, day_rows in sorted(by_date.items()):
        # Separate RTH (ntime >= 930) from pre-market
        rth_rows = [r for r in day_rows if r[2] >= 930]
        pre_rows = [r for r in day_rows if r[2] < 930]
        # Predict only on RTH sequence
        if rth_rows:
            snaps = [
                {'uprice': r[3], 'net_gex': r[4], 'kcs': r[5],
                 'sentiment_pct': r[6], 'key_strike': r[7], 'total_put_vol': r[8]}
                for r in rth_rows
            ]
            results = predict_hmm_sequence(snaps)
            for row, hmm in zip(rth_rows, results):
                id_, ntime = row[0], row[2]
                con.execute(
                    'UPDATE live_captures SET hmm_state=?, hmm_label=? WHERE id=?',
                    (hmm['state'], hmm['label'], id_)
                )
                print(f'  {ndate} {ntime:04d} -> {hmm["label"]}')
                total += 1
        # Clear pre-market labels (set to None)
        for row in pre_rows:
            id_, ntime = row[0], row[2]
            con.execute(
                'UPDATE live_captures SET hmm_state=?, hmm_label=? WHERE id=?',
                (None, None, id_)
            )
            print(f'  {ndate} {ntime:04d} -> (pre-market, skipped)')
            total += 1

print(f'Done — updated {total} rows')
