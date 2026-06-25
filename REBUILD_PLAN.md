# GEX Viewer Rebuild Plan

Baseline: git tag `v1.0` (commit `8b2a5dc`)

## Status Legend
- [ ] Pending
- [x] Done
- [~] Partial / In Progress

---

## Backend / Data Layer

- [x] **1. SQLite schema** — verify and document current `gex.db` schema; confirm all required tables exist (`gex_snapshots`, `live_captures`, `live_analysis`, `open_prices`, `narratives`)
- [x] **2. Remove all file persistence** — all reads/writes go through SQLite only; no JSON file fallbacks
- [x] **3. Live → Historical migration** — at end of trading day, live snapshots in `gex_snapshots` are promoted/flagged as historical; `_migrate_live_snapshots_to_history` exists but auto-triggered on server start via `_promote_live_to_historical()`
- [x] **4. Variable-interval historical queries** — remove 30-min fixed-step assumption; available times driven by actual DB rows
- [x] **5. Historical accepts both sources** — `histgex` API snapshots AND promoted live captures coexist in `gex_snapshots`; unified query, no source discrimination
- [x] **6. Pre-calculate percentile rankings** — compute and store ranks in DB at snapshot ingest time; expose via existing `/api/percentiles` endpoint rather than computing on every request
- [x] **7. HMM + PCA** — regime detection fields baked into snapshot at ingest; drop unused fields; expose via API
- [x] **8. Trading Narratives** — AI-generated narrative per day stored in `narratives` table; editable via API; `POST /api/narrative` and `GET /api/narrative`

---

## API Endpoints (no structural changes needed — all working)

Current endpoints for reference:

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/api/dates` | Available historical dates |
| GET | `/api/snapshot` | Single snapshot for date+time |
| GET | `/api/snapshots` | All times for a date |
| GET | `/api/snapshots/summary` | Summary row per time-slot |
| GET | `/api/csv-data` | Historical summary CSV |
| GET | `/api/analysis` | EOD analysis for a date |
| GET | `/api/percentiles` | Percentile ranks for a snapshot |
| GET | `/api/narrative` | Get/generate trading narrative |
| POST | `/api/narrative` | Update narrative |
| POST | `/api/narrative/regenerate` | Regenerate narrative |
| GET | `/api/history` | Historical metric values (scatter) |
| GET | `/api/archived-live` | Live artifacts for historical date |
| GET | `/api/sync-historical` | Sync historical GEX data |
| GET | `/api/spx-prices` | SPX price history |
| POST | `/api/migrate-live` | Trigger live→historical migration |
| GET | `/api/metric/history` | Historical EOD values for a metric |
| POST | `/api/hmm/train` | Retrain HMM model |
| GET | `/api/live/snapshots` | Today's live snapshot times |
| GET | `/api/live/snapshot` | Specific live snapshot |
| GET | `/api/live/captures` | Live captures table |
| GET | `/api/live/fetch` | Run full live pipeline |
| GET | `/api/live/capture` | Refresh session cookies |
| GET | `/api/live/analysis` | Generate + save live analysis |
| GET | `/api/live/analysis/history` | Saved analysis list for date |
| GET | `/api/live/analysis/saved` | Specific saved analysis |
| GET | `/api/live/open-price` | Get persisted SPX open price |
| POST | `/api/live/open-price` | Save SPX open price |

---

## Frontend — New Multi-Page Architecture (plain HTML/JS, no Bootstrap tabs)

- [x] **9. Historical page** `/` — date picker, variable-interval snapshot table + chart
- [x] **10. Live page** `/live` — today's snapshots with full 22-column table, tooltips, and stats header
- [x] **11. Analysis page** `/analysis` — EOD analysis view with narrative panel and regenerate button
- [x] **12. History Scatter page** `/hscatter` — scatter chart
- [x] **13. SPX Prices page** `/spx` — SPX price history
- [x] **14. CSV page** `/csv` — raw CSV data view

---

## Shared UI Features (Historical + Live)

- [x] **15. Unified snapshot table** — identical renderer used on both pages, columns:
  `Time (ET) | SPX | Senti% | Ratio | Net GEX | KCS | Regime | Put GEX | cVol | pVol | Flip | Key | K-cGEX | K-pGEX | K-cOI | K-pOI | K-cVol | K-pVol | Key2 | K2-Abs | K2-cVol | K2-pVol`
- [x] **16. Column heading popups** — tooltip on each column header explaining the metric
- [x] **17. Aligned data structures** — Historical and Live use identical API response shape and identical JS table renderer

---

## Step 1 Findings — Schema Notes

- `gex_snapshots` (1538 rows): primary store, has raw JSON `data` blob — NO flat summary columns
- `gex_data` (419,542 rows): per-strike rows linked to snapshots — needs investigation for join key
- `live_captures` (9 rows): has ALL 22 required flat columns incl. HMM fields — this is the target shape
- `live_analysis` (3 rows): saved analysis per snapshot ✅
- `daily_narratives` (3 rows): trading narratives ✅
- `percentile_history` (34,634 rows): pre-calculated percentiles ✅ (Step 6 partially done)
- `hmm_model` (1 row): trained HMM stored in DB ✅ (Step 7 partially done)
- `snapshots` (1,523 rows): **LEGACY TABLE** — different schema, pre-migration artefact, can be dropped
- `spx_open_prices` (0 rows): table exists, no data yet

**Key gap**: `gex_snapshots` lacks flat summary columns that `live_captures` has.
**Decision needed**: Add flat columns to `gex_snapshots` at ingest (Option A) vs derive on-the-fly (Option B — current, slower)
**Recommendation**: Option A — add flat summary columns to `gex_snapshots` so both Historical and Live read from same shape

---

## Navigation (all pages)

Shared nav bar linking: `Historical | Live | Analysis | History Scatter | SPX Prices | CSV`

---

## Implementation Order

| # | Step | Status |
|---|------|--------|
| 1 | Verify SQLite schema | [x] DONE — see findings below |
| 2 | Remove file persistence fallbacks | [x] DONE — live_dates() now queries DB; JSON files kept as migration archive only |
| 3 | Live→Historical auto-promotion | [x] DONE — _promote_live_to_historical() runs on startup; source column added to gex_snapshots |
| 4 | Variable-interval historical queries | [x] DONE — /api/snapshots queries DISTINCT ntime from DB, no fixed grid |
| 5 | Unified source in gex_snapshots | [x] DONE — gex_snapshots holds histgex + live_promoted; /api/snapshots/summary returns 28-field shape |
| 6 | Pre-calc percentiles at ingest | [x] DONE — /api/percentiles wired into historical chart panel; mini bar charts per metric |
| 7 | HMM/PCA fields in snapshots | [x] DONE — hmm_label colour coded in table (pos=green, neg=red, vol=amber, neu=grey) |
| 8 | Narratives API | [x] DONE — narrative panel on /analysis with Regenerate button; markdown rendered |
| 9 | New Historical `/` page | [x] DONE — historical.html; / route updated; /old serves legacy gex_viewer.html |
| 10 | Shared JS table renderer | [x] DONE — identical buildRow/buildHeader/fmtBig/fmtTime used in both historical.html and live.html |
| 11 | Column popups | [x] DONE — hover tooltips on all 22 column headers (live page); apply to historical when built |
| 12 | Live `/live` page (full table) | [x] DONE — full 22-col table with stats header, colour coding, tooltips |
| 13 | Analysis, Scatter, SPX, CSV pages | [x] DONE — /analysis /hscatter /spx /csv all 200 OK |
