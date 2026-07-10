#!/usr/bin/env python3
"""Check ML model status directly from database."""

import sqlite3
import json

DB_PATH = r"G:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=== ML Model Status ===\n")

cursor.execute("SELECT model_name, trained_at, n_samples, accuracy, features FROM ml_models")
rows = cursor.fetchall()

for row in rows:
    model_name, trained_at, n_samples, accuracy, features_json = row
    features = json.loads(features_json)
    print(f"Model: {model_name}")
    print(f"  Trained: {trained_at}")
    print(f"  Samples: {n_samples}")
    print(f"  Accuracy: {accuracy}")
    print(f"  Features: {len(features)} features")
    print()

conn.close()
