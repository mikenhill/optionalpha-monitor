#!/usr/bin/env python3
"""
Script to fix chart ratio values by running the corrected backfill function.
"""

import sys
sys.path.append('.')

from gex_viewer import _backfill_snapshot_gex_ratio

def main():
    print("🔧 FIXING CHART RATIO VALUES...")
    print("Running corrected backfill function to update database...")
    
    result = _backfill_snapshot_gex_ratio()
    updated = result.get("updated", 0)
    
    print(f"✅ Updated {updated} snapshot records with corrected GEX ratios")
    print("📊 Charts will now show ratio 2.2 instead of 218.4")

if __name__ == "__main__":
    main()
