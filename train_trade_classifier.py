#!/usr/bin/env python3
"""
Train a Random Forest classifier to predict intraday trade outcomes.

Uses labelled trade_signals data (outcome based on next-snapshot price)
to learn which GEX features predict profitable trades.
"""
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
import joblib
from pathlib import Path

DB_PATH = Path("gex.db")
MODEL_PATH = Path("trade_rf_model.pkl")
SCALER_PATH = Path("trade_rf_scaler.pkl")


def load_training_data():
    """Load labelled trade signals with features from the database."""
    con = sqlite3.connect(DB_PATH)
    
    # Join trade_signals with gex_snapshots to get features
    query = """
        SELECT 
            ts.ndate, ts.ntime,
            ts.setup_type, ts.action, ts.outcome,
            gs.uprice, gs.net_gex, gs.sentiment, gs.gex_ratio, 
            gs.kcs, gs.dominance, gs.total_call_gex, gs.total_put_gex,
            gs.total_call_oi, gs.total_put_oi, gs.total_call_vol, gs.total_put_vol,
            gs.key_strike, gs.key_call_gex, gs.key_put_gex,
            gs.key_call_oi, gs.key_put_oi, gs.key_call_vol, gs.key_put_vol,
            gs.key2_strike, gs.key2_abs, gs.key2_call_vol, gs.key2_put_vol,
            gs.flip, gs.hmm_state
        FROM trade_signals ts
        LEFT JOIN gex_snapshots gs ON ts.ndate = gs.ndate AND ts.ntime = gs.ntime AND gs.symbol = 'SPX'
        WHERE ts.outcome IS NOT NULL 
          AND ts.outcome != 'NEUTRAL'
          AND gs.uprice IS NOT NULL
        ORDER BY ts.ndate, ts.ntime
    """
    
    df = pd.read_sql_query(query, con)
    con.close()
    
    if df.empty:
        print("No labelled data found. Generate trade signals first.")
        return None, None, None
    
    print(f"Loaded {len(df)} labelled samples")
    print(f"Outcome distribution:\n{df['outcome'].value_counts()}")
    
    return df


def prepare_features(df):
    """Prepare feature matrix and target labels."""
    # Feature columns
    feature_cols = [
        'uprice', 'net_gex', 'sentiment', 'gex_ratio', 
        'kcs', 'dominance', 'total_call_gex', 'total_put_gex',
        'total_call_oi', 'total_put_oi', 'total_call_vol', 'total_put_vol',
        'key_strike', 'key_call_gex', 'key_put_gex',
        'key_call_oi', 'key_put_oi', 'key_call_vol', 'key_put_vol',
        'key2_strike', 'key2_abs', 'key2_call_vol', 'key2_put_vol',
        'flip', 'hmm_state'
    ]
    
    # Calculate derived features
    df['net_oi'] = df['total_call_oi'] - df['total_put_oi']
    df['net_vol'] = df['total_call_vol'] - df['total_put_vol']
    df['key_net_gex'] = df['key_call_gex'] - df['key_put_gex']
    df['key_net_oi'] = df['key_call_oi'] - df['key_put_oi']
    df['dist_to_key'] = (df['uprice'] - df['key_strike']).abs()
    df['dist_to_flip'] = (df['uprice'] - df['flip']).abs() if df['flip'].notna().any() else df['uprice'] * 0
    
    # Add derived features to feature list
    feature_cols.extend(['net_oi', 'net_vol', 'key_net_gex', 'key_net_oi', 'dist_to_key', 'dist_to_flip'])
    
    # Fill NaN values
    X = df[feature_cols].fillna(0)
    
    # Target: binary classification (WIN vs LOSS)
    # Map WIN, CORRECT -> 1 (positive outcome)
    # Map LOSS, MISSED -> 0 (negative outcome)
    # Skip PARTIAL for binary classification
    y = df['outcome'].map({
        'WIN': 1, 'CORRECT': 1,
        'LOSS': 0, 'MISSED': 0
    })
    
    # Remove samples with PARTIAL outcome
    mask = y.notna()
    X = X[mask]
    y = y[mask].astype(int)
    
    print(f"After filtering: {len(X)} samples for binary classification")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    print(f"Total features: {len(feature_cols)}")
    
    return X, y, feature_cols


def train_classifier(X, y, feature_cols):
    """Train Random Forest classifier and evaluate."""
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        class_weight='balanced'
    )
    
    rf.fit(X_train_scaled, y_train)
    
    # Evaluate
    train_score = rf.score(X_train_scaled, y_train)
    test_score = rf.score(X_test_scaled, y_test)
    cv_scores = cross_val_score(rf, X_train_scaled, y_train, cv=5)
    
    print(f"\nTraining accuracy: {train_score:.3f}")
    print(f"Test accuracy: {test_score:.3f}")
    print(f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    print("\nClassification Report:")
    y_pred = rf.predict(X_test_scaled)
    print(classification_report(y_test, y_pred, target_names=['LOSS', 'WIN']))
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Feature Importances:")
    print(importance.head(10).to_string(index=False))
    
    # Save model and scaler
    joblib.dump(rf, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Scaler saved to {SCALER_PATH}")
    
    return rf, scaler, importance


def main():
    print("Loading training data...")
    df = load_training_data()
    if df is None:
        return
    
    print("\nPreparing features...")
    X, y, feature_cols = prepare_features(df)
    
    print("\nTraining classifier...")
    rf, scaler, importance = train_classifier(X, y, feature_cols)
    
    print("\nDone.")


if __name__ == "__main__":
    main()
