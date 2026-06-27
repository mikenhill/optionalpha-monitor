"""Database connection manager for GEX Viewer.

Handles SQLite connections with retry logic for Google Drive sync issues.
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Database path (same as gex_viewer.py)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "gex.db"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with retry logic.
    
    Tries WAL mode first; if the WAL/SHM files are locked by Google Drive
    (disk I/O error), waits briefly and retries up to 5 times, then falls
    back to DELETE journal mode which avoids WAL files entirely.
    
    Yields:
        sqlite3.Connection: Database connection with row_factory set to sqlite3.Row
        
    Example:
        with get_connection() as con:
            result = con.execute("SELECT * FROM snapshot")
    """
    wal = DB_PATH.with_suffix(".db-wal")
    shm = DB_PATH.with_suffix(".db-shm")
    last_exc = None
    
    for attempt in range(5):
        try:
            con = sqlite3.connect(str(DB_PATH), timeout=10)
            con.execute("PRAGMA journal_mode=WAL")
            con.row_factory = sqlite3.Row
            try:
                yield con
            finally:
                con.close()
            return
        except sqlite3.OperationalError as exc:
            last_exc = exc
            if "disk I/O" in str(exc):
                # Try to remove stale WAL/SHM left by Drive sync
                for f in (wal, shm):
                    try:
                        if f.exists() and f.stat().st_size == 0:
                            f.unlink()
                    except OSError:
                        pass
                time.sleep(0.5 * (attempt + 1))
            else:
                raise
    
    # WAL unavailable — fall back to DELETE mode (no WAL files created)
    try:
        con = sqlite3.connect(str(DB_PATH), timeout=10)
        con.execute("PRAGMA journal_mode=DELETE")
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()
    except sqlite3.OperationalError:
        raise last_exc
