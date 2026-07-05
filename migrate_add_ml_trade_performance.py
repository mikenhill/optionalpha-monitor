"""Create ml_trade_performance table for tracking ML trade signal performance over time."""
import sqlite3

DB_PATH = 'gex.db'

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Create ml_trade_performance table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ml_trade_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ndate INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            training_date TEXT,
            force_retrain INTEGER,
            
            -- Prediction counts
            total_predictions INTEGER,
            high_conf_predictions INTEGER,
            medium_conf_predictions INTEGER,
            low_conf_predictions INTEGER,
            
            -- Trade signal accuracy
            trade_correct INTEGER,
            trade_incorrect INTEGER,
            trade_neutral INTEGER,
            
            -- By trade type
            ic_correct INTEGER,
            ic_total INTEGER,
            sps_correct INTEGER,
            sps_total INTEGER,
            scs_correct INTEGER,
            scs_total INTEGER,
            lcs_correct INTEGER,
            lcs_total INTEGER,
            lps_correct INTEGER,
            lps_total INTEGER,
            
            -- By confidence level
            high_conf_accuracy REAL,
            medium_conf_accuracy REAL,
            
            -- Financial metrics
            total_outcome_points REAL,
            avg_outcome_points REAL,
            max_drawdown REAL,
            
            -- Vol regime accuracy
            vol_regime_correct INTEGER,
            vol_regime_total INTEGER,
            vol_regime_accuracy REAL,
            
            -- Direction accuracy
            direction_2hr_correct INTEGER,
            direction_2hr_total INTEGER,
            direction_2hr_accuracy REAL,
            
            -- Metadata
            computed_at TEXT NOT NULL,
            UNIQUE(ndate, model_version)
        )
    """)
    print("Created ml_trade_performance table")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("ml_trade_performance table already exists")
    else:
        raise

# Create index on ndate for faster queries
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_ml_trade_performance_ndate ON ml_trade_performance (ndate)")
    print("Created index on ndate")
except sqlite3.OperationalError as e:
    print(f"Index creation note: {e}")

con.commit()
con.close()
print("Migration complete")
