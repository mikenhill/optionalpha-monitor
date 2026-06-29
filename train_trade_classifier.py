"""Train a Random Forest classifier on historical trade signals + GEX features.

Uses outcome labels (WIN/LOSS/NEUTRAL/CORRECT/MISSED) joined with gex_strike_window
features to predict trade signal quality. Persists the model to the rf_model table.
"""
import sqlite3
import os
import sys
import pickle
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "gex.db")

FEATURES = [
    "net_gex", "total_call_gex", "total_put_gex",
    "sentiment", "gex_ratio", "kcs", "dominance",
    "total_call_oi", "total_put_oi",
    "total_call_vol", "total_put_vol",
    "key_call_gex", "key_put_gex",
    "key_call_oi", "key_put_oi",
    "key_call_vol", "key_put_vol",
    "key2_call_vol", "key_net_oi",
    "dist_to_key", "dist_to_flip", "key2_abs",
]

# Map outcomes to binary: 1 = good trade (WIN/CORRECT), 0 = bad (LOSS/MISSED/NEUTRAL)
OUTCOME_MAP = {
    "WIN": 1,
    "CORRECT": 1,
    "PARTIAL": 1,
    "LOSS": 0,
    "MISSED": 0,
    "NEUTRAL": 0,
}


def main():
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        import numpy as np
    except ImportError:
        print("ERROR: scikit-learn not installed. Run: pip install scikit-learn", file=sys.stderr)
        return 1

    # Import GEX calculation functions
    sys.path.insert(0, os.path.dirname(__file__))
    from controllers.gex_calculations import (
        calculate_sentiment,
        calculate_gex_ratio,
        calculate_net_gex,
        calculate_kcs,
        calculate_dominance,
        calculate_key_strike_stats,
        calculate_total_oi_and_vol,
        calculate_total_gex,
        calculate_flip_level,
    )

    con = sqlite3.connect(DB_PATH)

    # Join trade_signals with gex_strike_window
    rows = con.execute("""
        SELECT
            g.ndate, g.ntime, g.price, g.data,
            t.outcome, t.setup_type, t.action
        FROM trade_signals t
        JOIN gex_strike_window g ON t.ndate=g.ndate AND t.ntime=g.ntime AND g.symbol='SPX' AND g.source='gex'
        WHERE t.outcome IS NOT NULL
          AND t.outcome != ''
          AND g.ntime >= 935
    """).fetchall()

    con.close()

    if len(rows) < 50:
        print(f"ERROR: Not enough labelled data ({len(rows)} rows, need at least 50)", file=sys.stderr)
        return 1

    print(f"Loaded {len(rows)} labelled rows")

    X, y, meta = [], [], []
    for row in rows:
        ndate, ntime, uprice, data_json, outcome, setup_type, action = row

        if not uprice or not data_json:
            continue

        try:
            strikes = json.loads(data_json)
        except:
            continue

        if not strikes:
            continue

        # Calculate all RF features using gex_calculations module
        sentiment = calculate_sentiment(strikes)
        gex_ratio = calculate_gex_ratio(strikes)
        net_gex = calculate_net_gex(strikes)
        kcs = calculate_kcs(strikes, uprice)
        dominance = calculate_dominance(strikes, uprice)
        key_stats = calculate_key_strike_stats(strikes, uprice)
        total_oi_vol = calculate_total_oi_and_vol(strikes)
        total_gex_vals = calculate_total_gex(strikes)
        flip = calculate_flip_level(strikes)

        # Compute distance features
        key_strike = key_stats["key_strike"] or uprice
        dist_to_key = abs(uprice - key_strike)
        dist_to_flip = abs(uprice - flip) if flip else 0

        # Compute key_net_oi (net OI at key strike: coi - poi)
        key_net_oi = (key_stats["key_call_oi"] or 0) - (key_stats["key_put_oi"] or 0)

        label = OUTCOME_MAP.get(outcome)
        if label is None:
            continue

        # Build feature dict exactly matching FEATURES order
        features = [
            net_gex,
            total_gex_vals["total_call_gex"],
            total_gex_vals["total_put_gex"],
            sentiment,
            gex_ratio,
            kcs,
            dominance,
            total_oi_vol["total_call_oi"],
            total_oi_vol["total_put_oi"],
            total_oi_vol["total_call_vol"],
            total_oi_vol["total_put_vol"],
            key_stats["key_call_gex"],
            key_stats["key_put_gex"],
            key_stats["key_call_oi"],
            key_stats["key_put_oi"],
            key_stats["key_call_vol"],
            key_stats["key_put_vol"],
            key_stats["key2_call_vol"],
            key_net_oi,
            dist_to_key,
            dist_to_flip,
            key_stats["key2_abs"],
        ]

        X.append(features)
        y.append(label)
        meta.append({"outcome": outcome, "setup_type": setup_type, "action": action})

    import numpy as np
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)

    print(f"Training on {len(X)} samples (class balance: {y.mean():.2%} positive)")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=5,
        random_state=42,
        class_weight="balanced"
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=["Bad", "Good"])
    print("Classification report:\n", report)

    # Feature importances
    importances = dict(zip(FEATURES, clf.feature_importances_.tolist()))
    top = sorted(importances.items(), key=lambda x: -x[1])[:5]
    print("Top features:", top)

    # Persist to DB
    model_blob = pickle.dumps(clf)
    trained_at = datetime.utcnow().isoformat() + "+00:00"
    meta_json = json.dumps({
        "features": FEATURES,
        "n_samples": len(X),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_importances": importances,
        "outcome_map": OUTCOME_MAP,
        "class_balance": float(y.mean()),
        "report": report,
    })

    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS rf_model (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trained_at  TEXT NOT NULL,
            n_samples   INTEGER,
            meta_json   TEXT,
            model_blob  BLOB NOT NULL
        )
    """)
    con.execute(
        "INSERT INTO rf_model (trained_at, n_samples, meta_json, model_blob) VALUES (?, ?, ?, ?)",
        (trained_at, len(X), meta_json, model_blob)
    )
    con.commit()
    con.close()

    print(f"\nModel saved to rf_model table. trained_at={trained_at}, n_samples={len(X)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
