# Session Summary - June 26, 2026

## Objective
Refactor database to use unified `snapshot` table only, eliminating references to old `live_captures` and `gex_snapshots` tables.

## Changes Made

### Database
- Renamed `live_captures` → `obsolete_live_captures`
- Renamed `gex_snapshots` → `obsolete_gex_snapshots`
- Deleted rogue 11:08 snapshot (20260626, ntime=1108)

### Code Changes (gex_viewer.py)
- Replaced all references to `live_captures` and `gex_snapshots` with `snapshot`
- Removed `_migrate_to_snapshot` function (migration logic no longer needed)
- Removed auto-migration from `_api_live_fetch_inner`
- Fixed SQL column references:
  - `data` → `raw_json` in SELECT/INSERT statements
  - `spx_last` → `uprice` in SELECT statements
- Fixed `_ensure_snapshot_table` to use `rowid` instead of `id` for duplicate removal
- Added `source='gex'` filter to Historical page queries (`total_live` count and `live_rows`)

## Current Problem

**Error**: "29 values for 33 columns" when Fetch Live Data is clicked

**Root Cause**: In `_api_live_fetch_inner` (lines 5625-5651), the INSERT statement has:
- Line 5633: 5 question marks (ndate, ntime, uprice, raw_json, capture_ts)
- Line 5634: 28 question marks (should be 26)
- Total: 33 question marks, but only 31 values in the tuple

**Expected**: 31 question marks total (33 columns - 2 hardcoded: symbol='SPX', source='gex')

**Fix Required**: Line 5634 needs 26 question marks instead of 28.

## Database State
- Latest snapshot row has 33 total columns, but only 7 are populated (26 null)
