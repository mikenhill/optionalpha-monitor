import sys, json
import numpy as np
sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
from gex_viewer import _load_hmm, _db, predict_hmm_state, summarise_snapshot, load_gex_snapshot

model, scaler, labels = _load_hmm()
print("State labels:", labels)
print()

# Show what each state's mean looks like in original feature space
means_raw = scaler.inverse_transform(model.means_)
feature_names = ["net_gex(B)", "kcs", "sentiment_pct", "dist_to_key", "put_vol(K)"]
print("State means (inverse-transformed to original scale):")
print(f"  {'Feature':<18}", end="")
for i, lbl in enumerate(labels):
    print(f"  {lbl[:16]:>16}", end="")
print()
for j, fn in enumerate(feature_names):
    print(f"  {fn:<18}", end="")
    for i in range(len(labels)):
        print(f"  {means_raw[i, j]:>16.3f}", end="")
    print()
print()

# Show the state distribution across all historical snapshots
with _db() as con:
    rows = con.execute(
        "SELECT ndate, ntime FROM gex_snapshots WHERE symbol='SPX' AND ntime>=930 ORDER BY ndate, ntime"
    ).fetchall()

records = []
for ndate, ntime in rows:
    date_iso = f"{str(ndate)[:4]}-{str(ndate)[4:6]}-{str(ndate)[6:]}"
    data = load_gex_snapshot(date_iso, ntime)
    if not data:
        continue
    snap = summarise_snapshot(data)
    if not snap.get("uprice"):
        continue
    uprice = snap["uprice"]
    key = snap.get("key_strike") or uprice
    records.append([
        (snap.get("net_gex") or 0) / 1e9,
        snap.get("kcs") or 0,
        snap.get("sentiment_pct") or 50,
        abs(uprice - key),
        (snap.get("total_put_vol") or 0) / 1e3,
    ])

X = np.array(records)
X_scaled = scaler.transform(X)

# Predict on the full sequence (this is correct HMM usage)
states = model.predict(X_scaled)
from collections import Counter
dist = Counter(states)
print("State distribution across all historical RTH snapshots:")
for state, count in sorted(dist.items()):
    print(f"  State {state} ({labels[state]}): {count} ({count/len(states)*100:.1f}%)")
print()

# Now show what today's live captures look like as a sequence
with _db() as con:
    live = con.execute(
        "SELECT ntime, spx_last, net_gex, kcs, sentiment, key_strike, total_put_vol "
        "FROM live_captures WHERE ndate=(SELECT MAX(ndate) FROM live_captures) ORDER BY ntime"
    ).fetchall()

print(f"Today's live captures ({len(live)} rows):")
live_X = []
for row in live:
    ntime, spx_last, net_gex, kcs, sentiment, key_strike, total_put_vol = row
    key = key_strike or spx_last or 0
    live_X.append([
        (net_gex or 0) / 1e9,
        kcs or 0,
        sentiment or 50,
        abs((spx_last or 0) - key),
        (total_put_vol or 0) / 1e3,
    ])

if live_X:
    lX = np.array(live_X)
    lX_scaled = scaler.transform(lX)
    # Score individual points vs sequence prediction
    seq_states = model.predict(lX_scaled)
    posteriors = model.predict_proba(lX_scaled)
    print(f"  {'ntime':>6}  {'Seq state':>12}  {'Label':<22}  {'Probs (0..3)'}")
    for i, row in enumerate(live):
        ntime = row[0]
        probs = [f"{p:.2f}" for p in posteriors[i]]
        print(f"  {ntime:>6}  {seq_states[i]:>12}  {labels[seq_states[i]]:<22}  {probs}")
