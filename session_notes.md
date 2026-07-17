# Session Notes

## 2026-07-17

### Active Work
Bot analysis and Magnet Days tab bug fixes; documenting NEG_GAMMA signal source.

### Changes Made

1. **Fixed Magnet Days tab table synchronization in `templates/magnet.html`**
   - `clearAverages()` now also clears and re-renders the 12:00 Screen table (Table 2).
   - `computeAverages()` now calls `loadRows1200()` after `loadRows()` so both tables populate after a compute.

2. **Added standalone ML bot analysis scripts and reports**
   - `bocca_gap_analysis.py` / `analysis_bocca_gap.md` — Bocca Gap 0DTE iron condor (48 trades, 52.1% WR). Key finding: `range_expansion` (PM range / AM range) is the dominant loss predictor.
   - `analysis_orb60.md` — ORB-60 put/call spread bot (20 trades, 85% WR). Key finding: losses on narrow-ORB, gap-down, false-breakout days.

3. **Documented `NEG_GAMMA` trade signal rationale source**
   - Located in `gex_viewer.py` lines 412-421 (`setup_type == "NEG_GAMMA"` branch).
   - Rationale string is built from `net_gex` value, `flip` level, and static caution text.

### Server Status
- Flask app running at `http://127.0.0.1:5050`
- Start command (run from `G:\My Drive\Colab Notebooks\optionalpha-monitor`):
  ```powershell
  python gex_viewer.py --port 5050
  ```

### Pending Items
- Review bot analysis recommendations and update OptionAlpha scanner filters if desired.
- Decide whether to implement VIX <= 18 / AM return filters in Bocca Gap config.
- Consider widening Bocca Gap IC wings or reducing stop loss from 90% to 60-70%.

## 2026-07-10

### Active Work
Fixing Flip display and related historical-sync issues on the `/gex` page.

### Changes Made

1. **Fixed historical sync crash for RTH snapshots**
   - File: `gex_viewer.py` (line ~9960)
   - Problem: `calculate_key_strike_stats(window_strikes)` was missing the required `uprice` argument, causing `sync_historical_gex` to fail for every RTH time slot.
   - Fix: `calculate_key_strike_stats(window_strikes, uprice)`

2. **Added `flip` to `/api/gex/snapshots` response**
   - File: `controllers/gex_controller.py`
   - `GexController.get_gex_snapshots()` now computes `flip` on-the-fly via `calculate_flip_level(strikes)` and includes it in the JSON response.

3. **Made `/api/snapshots/summary` compute `flip` on-the-fly**
   - File: `gex_viewer.py` (route `/api/snapshots/summary`)
   - Removed dependency on the stored `flip` column; calculates it from strike data instead.

4. **Reverted `calculate_flip_level` extrapolation**
   - File: `controllers/gex_calculations.py`
   - Decision: keep the original semantics — flip only exists when cumulative net GEX crosses zero inside the 40-strike window. One-sided windows show `--` in the Flip column.

5. **Re-fetched 2026-07-08 15:55 record**
   - Deleted the partial record and re-ran `/api/sync-historical?mode=datetime&date=2026-07-08&time=1555`.
   - Verified it now appears in `/api/gex/snapshots?date=2026-07-08` with 16 rows and HMM label `Negative Trending`.

### Server Status
- Flask app running at `http://127.0.0.1:5050`
- Start command (run from `G:\My Drive\Colab Notebooks\optionalpha-monitor`):
  ```powershell
  python gex_viewer.py --port 5050
  ```

### Pending Item
- Compare current commit `15ea8d993c3bcac913562341cb28b0283b41a3d4` with branched ML work at `a10051f5da23f62c899060597191e73ff202606b` and identify functionality in the latter needed in the former.
  - Outstanding command (run from `G:\My Drive\Colab Notebooks\optionalpha-monitor`):
    ```powershell
    git log --oneline a10051f5da23f62c899060597191e73ff202606b ^15ea8d993c3bcac913562341cb28b0283b41a3d4
    ```
