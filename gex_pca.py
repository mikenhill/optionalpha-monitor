import sqlite3, json, sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, r'g:\My Drive\Colab Notebooks\optionalpha-monitor')
from gex_viewer import summarise_snapshot, load_gex_snapshot

DB = Path(r'g:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')

# ── 1. Collect all RTH snapshots from gex_snapshots ─────────────────────────
con = sqlite3.connect(str(DB))
rows = con.execute(
    "SELECT ndate, ntime FROM gex_snapshots WHERE symbol='SPX' AND ntime>=935 ORDER BY ndate, ntime"
).fetchall()
con.close()

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
    key    = snap.get("key_strike") or uprice
    flip   = snap.get("flip")
    wall   = snap.get("wall")

    records.append({
        "date":             ndate,
        "ntime":            ntime,
        "net_gex":          snap.get("net_gex", 0) / 1e9,
        "call_gex":         snap.get("call_gex", 0) / 1e9,
        "put_gex":          snap.get("put_gex", 0) / 1e9,
        "sentiment_pct":    snap.get("sentiment_pct", 50),
        "gex_ratio":        snap.get("gex_ratio") or 0,
        "kcs":              snap.get("kcs") or 0,
        "key_dominance_pct":snap.get("key_dominance_pct") or 0,
        "total_call_oi":    snap.get("total_call_oi", 0) / 1e3,
        "total_put_oi":     snap.get("total_put_oi", 0) / 1e3,
        "total_call_vol":   snap.get("total_call_vol", 0) / 1e3,
        "total_put_vol":    snap.get("total_put_vol", 0) / 1e3,
        "key_call_gex":     snap.get("key_call_gex", 0) / 1e9,
        "key_put_gex":      snap.get("key_put_gex", 0) / 1e9,
        "key_call_oi":      snap.get("key_call_oi", 0),
        "key_put_oi":       snap.get("key_put_oi", 0),
        "key_call_vol":     snap.get("key_call_vol", 0),
        "key_put_vol":      snap.get("key_put_vol", 0),
        "key_dominance_pct":snap.get("key_dominance_pct") or 0,
        "dist_to_key":      abs(uprice - key),
        "dist_to_flip":     abs(uprice - flip) if flip else 0,
        "dist_to_wall":     abs(uprice - (wall or uprice)),
        "key2_abs":         (snap.get("key2_abs") or 0) / 1e9,
    })

# Also pull live_captures
con = sqlite3.connect(str(DB))
live = con.execute(
    "SELECT ndate, ntime, net_gex, sentiment, gex_ratio, kcs, dominance, "
    "total_call_gex, total_put_gex, total_call_oi, total_put_oi, total_call_vol, total_put_vol, "
    "key_call_gex, key_put_gex, key_call_oi, key_put_oi, key_call_vol, key_put_vol, "
    "key_strike, spx_last, flip "
    "FROM live_captures WHERE ntime>=935 ORDER BY ndate, ntime"
).fetchall()
con.close()

for r in live:
    (ndate, ntime, net_gex, sentiment, gex_ratio, kcs, dominance,
     total_call_gex, total_put_gex, total_call_oi, total_put_oi,
     total_call_vol, total_put_vol,
     key_call_gex, key_put_gex, key_call_oi, key_put_oi, key_call_vol, key_put_vol,
     key_strike, spx_last, flip) = r

    if not spx_last: continue
    key = key_strike or spx_last
    records.append({
        "date":             ndate,
        "ntime":            ntime,
        "net_gex":          (net_gex or 0) / 1e9,
        "call_gex":         (total_call_gex or 0) / 1e9,
        "put_gex":          (total_put_gex or 0) / 1e9,
        "sentiment_pct":    sentiment or 50,
        "gex_ratio":        gex_ratio or 0,
        "kcs":              kcs or 0,
        "key_dominance_pct":dominance or 0,
        "total_call_oi":    (total_call_oi or 0) / 1e3,
        "total_put_oi":     (total_put_oi or 0) / 1e3,
        "total_call_vol":   (total_call_vol or 0) / 1e3,
        "total_put_vol":    (total_put_vol or 0) / 1e3,
        "key_call_gex":     (key_call_gex or 0) / 1e9,
        "key_put_gex":      (key_put_gex or 0) / 1e9,
        "key_call_oi":      key_call_oi or 0,
        "key_put_oi":       key_put_oi or 0,
        "key_call_vol":     key_call_vol or 0,
        "key_put_vol":      key_put_vol or 0,
        "dist_to_key":      abs(spx_last - key),
        "dist_to_flip":     abs(spx_last - flip) if flip else 0,
        "dist_to_wall":     0,
        "key2_abs":         0,
    })

df = pd.DataFrame(records).drop_duplicates(subset=["date","ntime"]).dropna()
print(f"Total snapshots for PCA: {len(df)}")
print(f"Dates: {sorted(df['date'].unique())}\n")

if len(df) < 5:
    print("ERROR: Not enough data points for PCA. Need at least 5 snapshots.")
    sys.exit(1)

# ── 2. PCA ───────────────────────────────────────────────────────────────────
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

FEATURES = [
    "net_gex", "call_gex", "put_gex",
    "sentiment_pct", "gex_ratio",
    "kcs", "key_dominance_pct",
    "total_call_oi", "total_put_oi",
    "total_call_vol", "total_put_vol",
    "key_call_gex", "key_put_gex",
    "key_call_oi", "key_put_oi",
    "key_call_vol", "key_put_vol",
    "dist_to_key", "dist_to_flip", "dist_to_wall",
    "key2_abs",
]

X = df[FEATURES].values
X_scaled = StandardScaler().fit_transform(X)

n_components = min(len(FEATURES), len(df) - 1)
pca = PCA(n_components=n_components)
pca.fit(X_scaled)

evr = pca.explained_variance_ratio_
cumulative = np.cumsum(evr)

print("=" * 70)
print("PRINCIPAL COMPONENT VARIANCE EXPLAINED")
print("=" * 70)
print(f"  {'PC':>4}  {'Variance':>10}  {'Cumulative':>12}  Signal")
print(f"  {'-'*4}  {'-'*10}  {'-'*12}  {'-'*20}")
for i, (v, c) in enumerate(zip(evr, cumulative)):
    signal = "▓▓▓▓▓" if v > 0.15 else ("▓▓▓" if v > 0.08 else ("▓▓" if v > 0.04 else ("▓" if v > 0.02 else "·")))
    marker = " ← 80% threshold" if abs(c - 0.80) < 0.05 else (" ← 90% threshold" if abs(c - 0.90) < 0.05 else "")
    print(f"  {i+1:>4}  {v*100:>9.2f}%  {c*100:>11.2f}%  {signal}{marker}")

# How many PCs needed for 80% / 90%
n80 = next(i+1 for i,c in enumerate(cumulative) if c >= 0.80)
n90 = next((i+1 for i,c in enumerate(cumulative) if c >= 0.90), n_components)
print(f"\n  → {n80} PCs capture 80% of variance  (from {len(FEATURES)} features)")
print(f"  → {n90} PCs capture 90% of variance")

# ── 3. Feature loadings — what does each PC represent? ──────────────────────
print("\n" + "=" * 70)
print("TOP FEATURE LOADINGS PER PRINCIPAL COMPONENT")
print("(shows which original metrics dominate each PC)")
print("=" * 70)

components = pca.components_
for pc_idx in range(min(n90, 6)):
    loadings = components[pc_idx]
    sorted_idx = np.argsort(np.abs(loadings))[::-1]
    top = sorted_idx[:5]
    print(f"\n  PC{pc_idx+1}  ({evr[pc_idx]*100:.1f}% variance)")
    for j in top:
        bar = "█" * int(abs(loadings[j]) * 20)
        sign = "+" if loadings[j] > 0 else "-"
        print(f"    {sign}{abs(loadings[j]):.3f}  {FEATURES[j]:<22}  {bar}")

# ── 4. Correlation matrix — which metrics are redundant? ────────────────────
print("\n" + "=" * 70)
print("CORRELATION MATRIX — REDUNDANCY DETECTION")
print("(|r| > 0.85 = highly redundant, one can be dropped)")
print("=" * 70)

df_feat = df[FEATURES].copy()
corr = df_feat.corr().abs()

redundant_pairs = []
for i in range(len(FEATURES)):
    for j in range(i+1, len(FEATURES)):
        r = corr.iloc[i, j]
        if r > 0.85:
            redundant_pairs.append((FEATURES[i], FEATURES[j], r))

redundant_pairs.sort(key=lambda x: -x[2])
if redundant_pairs:
    print(f"\n  {'Feature A':<22}  {'Feature B':<22}  {'|r|':>6}  Verdict")
    print(f"  {'-'*22}  {'-'*22}  {'-'*6}  {'-'*30}")
    for a, b, r in redundant_pairs:
        verdict = "DROP one" if r > 0.95 else "LIKELY redundant"
        print(f"  {a:<22}  {b:<22}  {r:.3f}  {verdict}")
else:
    print("  No highly correlated pairs found (|r| > 0.85)")

# ── 5. Final verdict ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VERDICT: WHICH METRICS ARE UNNECESSARY?")
print("=" * 70)

# Find features that appear in NO top-5 loading across all significant PCs
feature_importance = {f: 0.0 for f in FEATURES}
for pc_idx in range(n90):
    for j, f in enumerate(FEATURES):
        feature_importance[f] += abs(components[pc_idx, j]) * evr[pc_idx]

ranked = sorted(feature_importance.items(), key=lambda x: -x[1])
print(f"\n  Feature importance (weighted loading across first {n90} PCs):")
print(f"  {'Feature':<22}  {'Score':>8}  Verdict")
print(f"  {'-'*22}  {'-'*8}  {'-'*35}")
threshold = ranked[0][1] * 0.25  # bottom quarter of max score
for feat, score in ranked:
    if score < threshold:
        verdict = "⚠ LOW — consider removing"
    elif score < ranked[0][1] * 0.5:
        verdict = "△ MODERATE — keep but monitor"
    else:
        verdict = "✓ HIGH — retain"
    print(f"  {feat:<22}  {score:>8.4f}  {verdict}")
