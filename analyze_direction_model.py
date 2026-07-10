#!/usr/bin/env python3
"""Analyze direction model performance and identify improvement opportunities."""

import sqlite3
import json
from collections import Counter

DB_PATH = r"G:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db"

def analyze_label_distribution():
    """Check distribution of direction labels across different time horizons."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=== Label Distribution ===\n")
    
    for horizon in ['direction_1hr', 'direction_2hr', 'direction_eod']:
        cursor.execute(f"""
            SELECT {horizon}, COUNT(*) as cnt 
            FROM ml_labels 
            WHERE {horizon} IS NOT NULL 
            GROUP BY {horizon}
            ORDER BY cnt DESC
        """)
        rows = cursor.fetchall()
        total = sum(r[1] for r in rows)
        print(f"{horizon}:")
        for label, cnt in rows:
            pct = cnt / total * 100
            print(f"  {label}: {cnt} ({pct:.1f}%)")
        print(f"  Total: {total}\n")
    
    conn.close()

def analyze_direction_accuracy_by_horizon():
    """Compare direction accuracy across different time horizons."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=== Direction Accuracy by Horizon ===\n")
    
    # Check what columns exist
    cursor.execute("PRAGMA table_info(ml_predictions)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Available columns: {columns}\n")
    
    for horizon in ['direction_1hr', 'direction_2hr']:
        pred_col = horizon + '_actual'
        correct_col = horizon + '_correct'
        
        if correct_col not in columns:
            print(f"{horizon}: Column {correct_col} not found")
            continue
            
        # Get accuracy from predictions
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                AVG({correct_col}) as accuracy
            FROM ml_predictions
            WHERE {pred_col} IS NOT NULL
        """)
        row = cursor.fetchone()
        if row and row[0] > 0:
            print(f"{horizon}: {row[1]*100:.2f}% accuracy (n={row[0]})")
        else:
            print(f"{horizon}: No data")
    
    conn.close()

def analyze_feature_importance():
    """Extract feature importance from trained direction model."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== Feature Importance from Direction Model ===\n")
    
    cursor.execute("""
        SELECT model_blob, features 
        FROM ml_models 
        WHERE model_name = 'direction'
    """)
    row = cursor.fetchone()
    
    if row:
        import pickle
        blob, features_json = row
        payload = pickle.loads(blob)
        clf = payload['clf']
        features = json.loads(features_json)
        
        importances = clf.feature_importances_
        feature_imp = list(zip(features, importances))
        feature_imp.sort(key=lambda x: x[1], reverse=True)
        
        print("Feature | Importance")
        print("-" * 30)
        for feat, imp in feature_imp:
            print(f"{feat:20s} | {imp:.4f}")
    else:
        print("No direction model found in database")
    
    conn.close()

def analyze_misclassifications():
    """Look for patterns in misclassified predictions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== Misclassification Analysis ===\n")
    
    cursor.execute("""
        SELECT 
            direction_pred,
            direction_2hr_actual,
            COUNT(*) as cnt
        FROM ml_predictions
        WHERE direction_2hr_actual IS NOT NULL
        GROUP BY direction_pred, direction_2hr_actual
        ORDER BY cnt DESC
    """)
    
    rows = cursor.fetchall()
    print("Predicted -> Actual | Count")
    print("-" * 30)
    for pred, actual, cnt in rows:
        print(f"{pred:10s} -> {actual:6s} | {cnt}")
    
    conn.close()

if __name__ == '__main__':
    analyze_label_distribution()
    analyze_direction_accuracy_by_horizon()
    analyze_feature_importance()
    analyze_misclassifications()
