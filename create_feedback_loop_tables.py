#!/usr/bin/env python3
"""
Create database tables for trade signal feedback loop implementation.

This script creates the necessary tables to support:
1. Trade signal performance features
2. Wall performance history
3. Signal reliability by regime
"""

import sqlite3
import sys
from datetime import datetime

def create_trade_signal_features_table():
    """Create table for calculated trade signal performance features."""
    with sqlite3.connect('gex.db') as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trade_signal_features (
                ndate INTEGER NOT NULL,
                ntime INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                
                -- Trade Signal Performance Features
                call_wall_success_rate_7d REAL,
                call_wall_success_rate_30d REAL,
                put_wall_success_rate_7d REAL,
                put_wall_success_rate_30d REAL,
                wall_strength_score REAL,
                signal_reliability_score REAL,
                recent_signal_performance_5 REAL,
                recent_signal_performance_20 REAL,
                
                -- Market Regime Features
                high_volatility_regime INTEGER,
                trending_market INTEGER,
                choppy_market INTEGER,
                macro_event_risk INTEGER,
                
                -- Metadata
                calculated_at TEXT NOT NULL,
                
                PRIMARY KEY (ndate, ntime, symbol)
            )
        """)
        
        # Create indexes for efficient queries
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_signal_features_ndate 
            ON trade_signal_features(ndate)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_signal_features_calculated_at 
            ON trade_signal_features(calculated_at)
        """)
        
        print("✅ Created trade_signal_features table")

def create_wall_performance_history_table():
    """Create table for historical wall performance by strike level."""
    with sqlite3.connect('gex.db') as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS wall_performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ndate INTEGER NOT NULL,
                strike_level REAL NOT NULL,
                wall_type TEXT NOT NULL,  -- 'CALL_WALL' or 'PUT_WALL'
                
                -- Performance metrics
                total_signals INTEGER NOT NULL,
                successful_signals INTEGER NOT NULL,
                success_rate REAL NOT NULL,
                avg_points REAL,
                max_points REAL,
                min_points REAL,
                
                -- Context metrics
                avg_sentiment REAL,
                avg_volume REAL,
                avg_volatility REAL,
                
                -- Time-based metrics
                holding_period_avg REAL,
                break_speed_avg REAL,
                
                calculated_at TEXT NOT NULL,
                
                UNIQUE(ndate, strike_level, wall_type)
            )
        """)
        
        # Create indexes
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_wall_performance_history_strike 
            ON wall_performance_history(strike_level, wall_type)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_wall_performance_history_ndate 
            ON wall_performance_history(ndate)
        """)
        
        print("✅ Created wall_performance_history table")

def create_signal_reliability_by_regime_table():
    """Create table for signal success rates by market regime."""
    with sqlite3.connect('gex.db') as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS signal_reliability_by_regime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regime_type TEXT NOT NULL,  -- 'volatility', 'trend', 'time_of_day', etc.
                regime_value TEXT NOT NULL,  -- 'HIGH', 'LOW', 'TRENDING', etc.
                signal_type TEXT NOT NULL,   -- 'CALL_WALL', 'PUT_WALL', 'IRON_BUTTERFLY', etc.
                
                -- Performance metrics
                total_signals INTEGER NOT NULL,
                successful_signals INTEGER NOT NULL,
                success_rate REAL NOT NULL,
                avg_confidence REAL,
                avg_points REAL,
                
                -- Sample size and confidence
                sample_size INTEGER NOT NULL,
                confidence_interval REAL,
                
                calculated_at TEXT NOT NULL,
                
                UNIQUE(regime_type, regime_value, signal_type)
            )
        """)
        
        # Create indexes
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_signal_reliability_regime 
            ON signal_reliability_by_regime(regime_type, regime_value)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_signal_reliability_signal 
            ON signal_reliability_by_regime(signal_type)
        """)
        
        print("✅ Created signal_reliability_by_regime table")

def create_feedback_loop_indexes():
    """Create additional indexes for performance optimization."""
    with sqlite3.connect('gex.db') as con:
        # Indexes for trade_signals table to support feedback calculations
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_signals_outcome 
            ON trade_signals(outcome, ndate, ntime)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_signals_setup_type 
            ON trade_signals(setup_type, ndate, ntime)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_signals_regime 
            ON trade_signals(regime, ndate, ntime)
        """)
        
        print("✅ Created feedback loop indexes")

def main():
    """Create all feedback loop tables and indexes."""
    print("Creating feedback loop database tables...")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        create_trade_signal_features_table()
        create_wall_performance_history_table()
        create_signal_reliability_by_regime_table()
        create_feedback_loop_indexes()
        
        print(f"\n✅ All feedback loop tables created successfully!")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
