# GEX Metrics Specification

**Last Updated:** 2026-06-30  
**Purpose:** Comprehensive specification of all GEX metrics, their sources, calculations, frontend exposure, and percentile tracking.

---

## 1. Raw JSON Data Fields (from Option Alpha)

These fields are received directly from Option Alpha API and stored in `gex_strike_window.data` as JSON.

| Field | Type | Description |
|-------|------|-------------|
| `strike` | int | Strike price |
| `cg` | float | Call Gamma (positive value) |
| `pg` | float | Put Gamma (negative value) |
| `total` | float | Net GEX at strike (cg + pg) |
| `coi` | int | Call Open Interest |
| `poi` | int | Put Open Interest |
| `cvol` | int | Call Volume |
| `pvol` | int | Put Volume |
| `abs` | float | Absolute total GEX (abs(total)) |
| `pcmag` | float | Put/Call magnitude ratio |
| `cotm` | float | Call time multiplier |
| `potm` | float | Put time multiplier |
| `net` | float | Same as total (net GEX at strike) |

---

## 2. Derived Metrics (from `controllers/gex_calculations.py`)

These metrics are calculated from raw JSON fields using the functions in `gex_calculations.py`.

### 2.1 Core Metrics

| Metric | Function | Calculation | Description |
|--------|----------|-------------|-------------|
| `sentiment` | `calculate_sentiment()` | % of strikes with net > 0 | Sentiment percentage (0-100) |
| `gex_ratio` | `calculate_gex_ratio()` | call_gex / abs(put_gex) with sign flip | Signed call/put GEX ratio |
| `net_gex` | `calculate_net_gex()` | sum(cg) + sum(pg) | Total net GEX across window |
| `kcs` | `calculate_kcs()` | weighted score (0.5*gex + 0.3*oi + 0.2*vol) * proximity | Key Confluence Score (0-15 typically) |
| `dominance` | `calculate_dominance()` | key_abs / total_abs * 100 | Key strike's % of total absolute GEX |

### 2.2 Key Strike Metrics (from `calculate_key_strike_stats()`)

| Metric | Description |
|--------|-------------|
| `key_strike` | Strike with highest abs * proximity weighted |
| `key_call_gex` | Call GEX at key strike |
| `key_put_gex` | Put GEX at key strike |
| `key_call_oi` | Call OI at key strike |
| `key_put_oi` | Put OI at key strike |
| `key_call_vol` | Call volume at key strike |
| `key_put_vol` | Put volume at key strike |
| `key2_strike` | Secondary key strike (highest abs * proximity, excluding key_strike) |
| `key2_abs` | Absolute GEX at secondary key strike |
| `key2_call_vol` | Call volume at secondary key strike |
| `key2_put_vol` | Put volume at secondary key strike |

### 2.3 Total Metrics (from `calculate_total_oi_and_vol()` and `calculate_total_gex()`)

| Metric | Function | Calculation |
|--------|----------|-------------|
| `total_call_oi` | `calculate_total_oi_and_vol()` | sum(coi) across window |
| `total_put_oi` | `calculate_total_oi_and_vol()` | sum(poi) across window |
| `total_call_vol` | `calculate_total_oi_and_vol()` | sum(cvol) across window |
| `total_put_vol` | `calculate_total_oi_and_vol()` | sum(pvol) across window |
| `total_call_gex` | `calculate_total_gex()` | sum(cg) across window |
| `total_put_gex` | `calculate_total_gex()` | sum(pg) across window |

### 2.4 Additional Metrics

| Metric | Function | Calculation | Description |
|--------|----------|-------------|-------------|
| `flip` | `calculate_flip_level()` | Zero crossing of cumulative net GEX | Strike where cumulative net GEX crosses zero |

---

## 3. Frontend-Exposed Metrics

These metrics are exposed to the frontend via API endpoints and displayed in the UI.

### 3.1 Snapshot Display Metrics (Historical/Live/GEX pages)

| Metric | Display Name | Location |
|--------|--------------|----------|
| `uprice` | SPX Price | Header, charts, table |
| `sentiment_pct` | Sentiment | Stats bar, table column |
| `gex_ratio` | GEX Ratio | Stats bar, table column |
| `net_gex` | Net GEX | Stats bar, table column, charts |
| `kcs` | KCS | Stats bar, table column, KCS chart |
| `dominance` | Dominance | Table column (on some pages) |
| `key_strike` | Key Strike | Chart annotation |
| `key_call_gex` | Key Call GEX | Table column |
| `key_put_gex` | Key Put GEX | Table column |
| `key_call_oi` | Key Call OI | Table column |
| `key_put_oi` | Key Put OI | Table column |
| `key_call_vol` | Key Call Vol | Table column |
| `key_put_vol` | Key Put Vol | Table column |
| `key2_strike` | Key2 Strike | Table column |
| `key2_abs` | Key2 Abs | Table column |
| `key2_call_vol` | Key2 Call Vol | Table column |
| `key2_put_vol` | Key2 Put Vol | Table column |
| `total_call_gex` | Total Call GEX | Percentile display |
| `total_put_gex` | Total Put GEX | Percentile display |
| `total_call_oi` | Total Call OI | Percentile display |
| `total_put_oi` | Total Put OI | Percentile display |
| `total_call_vol` | Total Call Vol | Percentile display |
| `total_put_vol` | Total Put Vol | Percentile display |
| `flip` | Flip Level | Chart annotation |
| `hmm_label` | HMM Regime | Badge display |

### 3.2 Percentile Display Metrics

These metrics have percentile mini-bars shown on the frontend.

| Metric | Percentile Display Location |
|--------|----------------------------|
| `net_gex` | Bearish percentile mini-bar |
| `total_call_gex` | Call GEX percentile mini-bar |
| `total_put_gex` | Put GEX percentile mini-bar |
| `total_call_oi` | Call OI percentile mini-bar |
| `total_put_oi` | Put OI percentile mini-bar |
| `total_call_vol` | Call Vol percentile mini-bar |
| `total_put_vol` | Put Vol percentile mini-bar |
| `kcs` | KCS percentile mini-bar |
| `dominance` | Dominance percentile mini-bar |

---

## 4. Percentile-Calculated Metrics

These metrics have percentile values pre-calculated and stored in `gex_percentile_history` table.

| Metric | Percentile Calculation | Time Slot Matching |
|--------|----------------------|-------------------|
| `net_gex` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `sentiment` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `gex_ratio` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `kcs` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `dominance` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_call_gex` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_put_gex` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_call_oi` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_put_oi` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_call_vol` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |
| `total_put_vol` | ✅ Yes | Uses requested time slot (or nearest standard time slot) |

**Note:** Irregular time slots (e.g., 940, 946, 1005) use the nearest standard RTH time slot for percentile comparison (935, 1000, etc.).

---

## 5. Metrics Without Percentile Tracking

These metrics are calculated and used but do NOT have percentile tracking:

| Metric | Reason |
|--------|--------|
| `uprice` | SPX price - not a GEX metric |
| `key_strike` | Strike price identifier - not a magnitude metric |
| `key_call_gex` | Strike-specific value - not aggregated |
| `key_put_gex` | Strike-specific value - not aggregated |
| `key_call_oi` | Strike-specific value - not aggregated |
| `key_put_oi` | Strike-specific value - not aggregated |
| `key_call_vol` | Strike-specific value - not aggregated |
| `key_put_vol` | Strike-specific value - not aggregated |
| `key2_strike` | Secondary strike identifier - not a magnitude metric |
| `key2_abs` | Secondary strike-specific value - not aggregated |
| `key2_call_vol` | Secondary strike-specific value - not aggregated |
| `key2_put_vol` | Secondary strike-specific value - not aggregated |
| `flip` | Derived level - not a magnitude metric |
| `hmm_label` | Classification label - not a magnitude metric |

---

## 6. Standard RTH Time Slots

These are the mandatory RTH time slots (9:35 AM to 3:55 PM ET) used for percentile calculations:

```
935, 1000, 1030, 1100, 1130, 1200, 1230, 1300, 1330, 1400, 1430, 1500, 1530, 1555
```

Irregular time slots (e.g., 940, 946, 1005) use the nearest standard time slot for percentile comparison.

---

## 7. Data Flow

1. **Raw Data:** Option Alpha API → `gex_strike_window.data` (JSON)
2. **Calculations:** `gex_calculations.py` functions → derived metrics
3. **Storage:** Metrics calculated on-the-fly when queried (not stored as flat columns)
4. **Percentiles:** `populate_gex_percentile_history.py` → `gex_percentile_history` table
5. **Frontend:** API endpoints → templates → UI display

---

## 8. Important Notes

- **On-the-fly Calculation:** All derived metrics are calculated on-the-fly from raw JSON data, not stored as flat columns in the database
- **Percentile Backfill:** When adding new time slots, run `populate_gex_percentile_history.py` with the time slot as argument
- **Time Slot Fallback:** Irregular time slots automatically use nearest standard RTH time slot for percentile comparison
- **HMM Regimes:** Calculated for RTH only (ntime >= 935), pre-market snapshots show hmm_label = null
