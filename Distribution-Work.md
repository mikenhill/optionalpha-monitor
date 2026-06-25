# Distribution-Work: Calculation Update Pattern

## Key Decisions (2026-06-25)

### GEX Ratio Formula
- **Rule**: Flip sign based on which side is larger
  - If call GEX > put GEX: positive ratio (call/put) = green
  - If put GEX > call GEX: negative ratio (put/call) = red
- **Example**: 2B neg + 3B pos = 1.5x positive; 3B neg + 2B pos = -1.5x negative

### Volume Scaling
- **Rule**: Volume should NOT be scaled by 1000
- **Reason**: Volume is in contract units (e.g., 83,842 contracts), not thousands
- **OI only**: Only Open Interest (OI) should be scaled to thousands for display readability

### Unit Suffixes
- **Distribution histogram**: Now shows unit suffixes for clarity
  - GEX metrics: 'B' (billions)
  - OI metrics: 'K' (thousands)
  - Volume metrics: no suffix (contracts)
  - Ratios: no suffix

## Pattern Found: Cache Invalidation After Calculation Changes

When changing metric calculation logic (e.g., gex_ratio formula), the system has two stale data sources:

1. **DB flat columns** (`gex_snapshots` and `live_captures`) - store pre-computed values
2. **In-memory cache** (`_HISTORY_CACHE`) - global dict that persists across requests

**This pattern occurred twice on 2026-06-25:**
- First: Fixed gex_ratio field name mismatch (cg/pg vs calls/puts)
- Second: Fixed gex_ratio to flip sign based on which side is larger

## Repeatable Plan for Calculation Updates

When updating any metric calculation logic, follow this sequence:

### 1. Update Calculation Logic
Update all computation functions in `gex_viewer.py`:
- `_compute_flat_summary()` (lines ~3057-3065)
- `_compute_flat_summary()` in other locations (search for `gex_ratio = round`)
- Any other functions that compute the metric

### 2. Backfill live_captures Table
If the metric exists in `live_captures`, recompute it:
```python
def _backfill_live_captures_<metric>() -> dict:
    """Recompute <metric> for all live_captures rows."""
    # SELECT existing columns needed for calculation
    # Recalculate using new formula
    # UPDATE live_captures SET <metric>=? WHERE ndate=? AND ntime=?
```

### 3. Promote Live to Historical
Run `_promote_live_to_historical()` to copy updated values to `gex_snapshots`

### 4. Backfill gex_snapshots Table
Run `_backfill_gex_snapshots_summary(force=True)` to:
- Recompute from JSON for histgex rows
- Copy from live_promoted rows (which now have updated values)

### 5. Clear History Cache
Clear the global cache to force rebuild with new values:
```python
_HISTORY_CACHE.clear()
```

### 6. Restart Server
Restart to apply all changes and rebuild cache on first request

## Implementation Notes

### Global Variable Syntax
- Python doesn't allow `global` declarations on annotated variables
- Use `_HISTORY_CACHE = {}` instead of `_HISTORY_CACHE: dict = {}`
- Use `.clear()` method instead of reassignment to avoid `global` keyword

### Startup Sequence (in `main()`)
```python
_backfill_live_captures_gex_ratio()  # if needed
_promote_live_to_historical()
_backfill_gex_snapshots_summary(force=True)
_HISTORY_CACHE.clear()
```

### Future Improvement: Cache Versioning
Add cache versioning to auto-invalidate when calculation logic changes:
1. Store `cache_version` in DB (settings table or pragma)
2. Store version with cache when built
3. On startup, compare versions and auto-invalidate if mismatched

## Related Files
- `gex_viewer.py` - All calculation logic and backfill functions
- `templates/hscatter.html` - Distribution histogram UI
- `gex.db` - SQLite database with flat columns

## Pending Tasks
None - all items from 2026-06-25 session completed.
