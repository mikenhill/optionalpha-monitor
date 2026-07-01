"""Script to remove all records for 2026-06-28 (Sunday)."""
import sqlite3

DB_PATH = "gex.db"
TARGET_DATE = 20260628

def remove_sunday_records():
    """Remove all records for target date from gex_strike_window and snapshot tables."""
    print(f"Removing records for date {TARGET_DATE}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_deleted = 0
    
    # Check and delete from gex_strike_window
    cursor.execute(f"SELECT COUNT(*) FROM gex_strike_window WHERE ndate={TARGET_DATE}")
    strike_count = cursor.fetchone()[0]
    print(f"gex_strike_window: {strike_count} records")
    
    if strike_count > 0:
        cursor.execute(f"DELETE FROM gex_strike_window WHERE ndate={TARGET_DATE}")
        total_deleted += cursor.rowcount
        print(f"  Deleted {cursor.rowcount} records from gex_strike_window")
    
    # Check and delete from snapshot
    cursor.execute(f"SELECT COUNT(*) FROM snapshot WHERE ndate={TARGET_DATE}")
    snapshot_count = cursor.fetchone()[0]
    print(f"snapshot: {snapshot_count} records")
    
    if snapshot_count > 0:
        cursor.execute(f"DELETE FROM snapshot WHERE ndate={TARGET_DATE}")
        total_deleted += cursor.rowcount
        print(f"  Deleted {cursor.rowcount} records from snapshot")
    
    conn.commit()
    print(f"✓ Total deleted: {total_deleted} records")
    
    conn.close()
    return total_deleted

if __name__ == "__main__":
    print("=" * 60)
    print("Sunday Date Removal Script")
    print("=" * 60)
    
    deleted_count = remove_sunday_records()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Records deleted: {deleted_count}")
    print(f"Date removed: {TARGET_DATE}")
