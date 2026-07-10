"""Script to backup gex_strike_window table, remove 930 records, and test historical sync."""
import sqlite3
import shutil
from datetime import datetime

DB_PATH = "gex.db"
BACKUP_PATH = f"gex_strike_window_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_table():
    """Backup gex_strike_window table to a separate database file."""
    print(f"Step 1: Backing up gex_strike_window table to {BACKUP_PATH}...")
    
    # Connect to source and destination databases
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(BACKUP_PATH)
    
    # Copy the table structure and data
    src_cursor = src_conn.cursor()
    dst_cursor = dst_conn.cursor()
    
    # Get the CREATE TABLE statement
    src_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='gex_strike_window'")
    create_stmt = src_cursor.fetchone()[0]
    dst_cursor.execute(create_stmt)
    
    # Copy all data
    src_cursor.execute("SELECT * FROM gex_strike_window")
    rows = src_cursor.fetchall()
    
    if rows:
        # Get column count
        src_cursor.execute("PRAGMA table_info(gex_strike_window)")
        columns = [col[1] for col in src_cursor.fetchall()]
        placeholders = ','.join(['?' for _ in columns])
        dst_cursor.executemany(f"INSERT INTO gex_strike_window VALUES ({placeholders})", rows)
    
    dst_conn.commit()
    print(f"✓ Backed up {len(rows)} records to {BACKUP_PATH}")
    
    src_conn.close()
    dst_conn.close()
    return len(rows)

def remove_930_records():
    """Remove records with ntime=930 from gex_strike_window."""
    print("\nStep 2: Removing 930 records from gex_strike_window...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count 930 records before deletion
    cursor.execute("SELECT COUNT(*) FROM gex_strike_window WHERE ntime=930")
    count_before = cursor.fetchone()[0]
    
    if count_before == 0:
        print("No 930 records found - nothing to delete")
        conn.close()
        return 0
    
    # Show sample of records to be deleted
    cursor.execute("SELECT ndate, ntime, symbol, source FROM gex_strike_window WHERE ntime=930 LIMIT 5")
    samples = cursor.fetchall()
    print(f"Sample records to be deleted (showing first 5):")
    for sample in samples:
        print(f"  {sample}")
    
    # Delete 930 records
    cursor.execute("DELETE FROM gex_strike_window WHERE ntime=930")
    deleted = cursor.rowcount
    
    conn.commit()
    print(f"✓ Deleted {deleted} records with ntime=930")
    
    conn.close()
    return deleted

def test_historical_sync():
    """Test historical sync for older dates."""
    print("\nStep 3: Testing historical sync for older dates...")
    
    try:
        from gex_historical_intraday import fetch_histgex
        
        # Test the date from user's API example (2026-02-18) and other dates
        test_cases = [
            (20260218, 955, "2026-02-18 (user's example)"),
            (20260628, 935, "2026-06-28 (previously failed)"),
            (20260630, 935, "2026-06-30 (recent)"),
        ]
        
        all_passed = True
        for test_date, test_time, desc in test_cases:
            print(f"\nTesting fetch_histgex for {desc} ({test_date}@{test_time})...")
            result = fetch_histgex("SPX", test_date, test_time)
            
            if result and isinstance(result, dict):
                data_points = result.get('data', [])
                print(f"✓ Fetch successful - got {len(data_points)} data points")
                print(f"Result keys: {list(result.keys())}")
                if data_points:
                    print(f"Sample data point: {data_points[0]}")
            else:
                print(f"✗ Fetch failed - result: {result}")
                all_passed = False
        
        return all_passed
            
    except Exception as e:
        print(f"✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("gex_strike_window 930 Record Removal Script")
    print("=" * 60)
    
    # Step 1: Backup
    try:
        backup_count = backup_table()
    except Exception as e:
        print(f"✗ Backup failed: {str(e)}")
        exit(1)
    
    # Step 2: Remove 930 records
    try:
        deleted_count = remove_930_records()
    except Exception as e:
        print(f"✗ Deletion failed: {str(e)}")
        print("Backup is available at:", BACKUP_PATH)
        exit(1)
    
    # Step 3: Test
    try:
        test_success = test_historical_sync()
    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
        print("Backup is available at:", BACKUP_PATH)
        exit(1)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Backup saved to: {BACKUP_PATH}")
    print(f"Records backed up: {backup_count}")
    print(f"Records deleted: {deleted_count}")
    print(f"Test result: {'PASS' if test_success else 'FAIL'}")
    print("\nIf test failed, you can restore the backup using:")
    print(f"  sqlite3 gex.db < {BACKUP_PATH}")
