# Daily GEX Analysis — 2026-07-08 03:42

**SPX Last:** 7503.85  
**Key Strike:** 7500 | **Key2 Strike:** 7525  
**Setup Classification:** CALL WALL

## A — Today's Values in Isolation

- **SPX Last:** 7503.85
- **Snapshot Time:** 2026-07-08 03:42
- **Key Strike:** 7500 | **Key2 Strike:** 7525
- **Setup Classification:** CALL WALL
- **Distance to Key:** 3.85 pts
- **Sentiment:** 50.0% of strikes positive gamma
- **Net GEX:** 0.30B (stabilising)
- **Total Call GEX:** 6.64B
- **Total Put GEX:** -6.34B
- **GEX Ratio:** 1.0471
- **KCS (Key Call Support):** 13.07
- **Dominance:** 19.79% of total absolute GEX sits at the key strike
- **Flip Level:** 7572.1
- **Key Absolute GEX:** 2.57B
- **Key Net GEX:** 0.93B | **Key Balance:** 36.04%
- **Key Call / Put GEX:** 1.75B / -0.82B
- **Key OI:** Call 3,531 / Put 1,660 → Net OI 1,871
- **Key Volume:** Call 2,049 / Put 3,004 → Net Vol -955
- **Total Call OI:** 25,371
- **Total Put OI:** 19,755
- **Total Call Volume:** 27,394
- **Total Put Volume:** 25,674
- **Top OI Strike:** 7500 (total 5,191)
- **Top Vol Strike:** 7500 (total 5,053)
- **Weighted Mean Put Strike (GEX):** 7480.01
- **VOLUME DIVERGENCE: intraday flow opposite to structural OI at key strike**

## B — Today vs History

Historical rows available: 16
- Sentiment: 68.8% — middle of historical range
- Net GEX: 68.8% — middle of historical range
- Key Absolute: 25.0% — middle of historical range
- Key Dominance: 81.2% — high/extreme vs history
- Previous session (2026-06-26 11:17) key strike: 7350

## C — ML Enrichment

- **Vol Regime:** TIGHT (confidence 61.70%)
- **Direction:** FLAT (confidence 43.50%)
- **RF Outcome:** NEUTRAL (probability 50.00%)

## D — Trade Logic & Invalidation

**Call Wall:** Short call spread at/just above 7500. Invalidates if price breaks 7500 on strong volume and holds above.

## E — Caution Notes

- Check tomorrow's GEX profile before pinning / iron butterfly theses.
- Verify economic calendar for FOMC, CPI, or other binary events.
- On monthly expiration / triple witching / end-of-quarter days, GEX signals are less reliable.

## F — OI & Volume Structure (Top Strikes)

| Strike | Char | Call OI | Put OI | Total OI | Call Vol | Put Vol | Abs GEX | Notes |
|--------|------|---------|--------|----------|----------|---------|---------|-------|
| 7500 | call-heavy | 3,531 | 1,660 | 5,191 | 2,049 | 3,004 | 2.57B | KEY |
| 7525 | CALL WALL | 2,554 | 448 | 3,002 | 2,159 | 46 | 1.21B | KEY2 |
| 7475 | PUT PILLAR | 707 | 2,109 | 2,816 | 95 | 1,309 | 1.21B |  |
| 7450 | PUT PILLAR | 473 | 1,691 | 2,164 | 38 | 2,439 | 0.65B |  |
| 7575 | CALL WALL | 2,009 | 92 | 2,101 | 183 | 1 | 0.15B |  |
| 7600 | CALL WALL | 1,819 | 109 | 1,928 | 115 | 3 | 0.06B |  |
| 7580 | CALL WALL | 1,453 | 239 | 1,692 | 159 | 2 | 0.10B |  |
| 7550 | CALL WALL | 1,204 | 404 | 1,608 | 1,944 | 24 | 0.33B |  |
| 7425 | PUT PILLAR | 227 | 1,292 | 1,519 | 7 | 1,167 | 0.29B |  |
| 7560 | put-heavy | 492 | 977 | 1,469 | 753 | 3 | 0.20B |  |

- **OI SANDWICH: price 7503.85 between put-heavy 7500 and call-heavy 7560**

## G — Percentile Context (vs History)

- **Sample:** 1 historical days at time 342
- **Net GEX:** 0.0% percentile (1 days at 342)
- **Call GEX:** 100.0% percentile (1 days at 342)
- **Put GEX:** 100.0% percentile (1 days at 342)
- **Call OI:** 100.0% percentile (1 days at 342)
- **Put OI:** 100.0% percentile (1 days at 342)
- **Call Volume:** 100.0% percentile (1 days at 342)
- **Put Volume:** 100.0% percentile (1 days at 342)
- **KCS:** 100.0% percentile (1 days at 342)
- **Dominance:** 100.0% percentile (1 days at 342)

## H — Live Trade Signal

- **Setup Type:** STAY_OUT
- **Action:** STAY_OUT
- **Structure:** No Trade
- **Rationale:** Insufficient GEX conviction or pre-market snapshot. No trade recommended.
- **Invalidation:** N/A
- **Caution:** Wait for RTH open and clearer GEX setup.

## I — Lessons from GEX Teaching Files

### Core Principles
- Gamma is potential energy — it is highest at at-the-money, short-dated strikes.
- Market makers hedge continuously to stay delta-neutral; their hedging creates pressure at key strikes.
- Open interest alone is not directional — it can be condors, hedges, or spreads (Captain Condor artifact).
- GEX works best on normal days; it is less reliable on monthly expiration, FOMC, CPI, triple witching, and end-of-month/quarter/year.
- Charm (delta decay) causes hedging flows to change over time even if price does not move.

### Setup-Specific Recommendation
**CALL WALL lesson:** A strike with outsized call gamma + call open interest acts as a resistance ceiling. As price rises toward it, market makers sell hedges, creating downward pressure.
- **Trade:** Short call spread at/just above 7500 (sell call at 7500, buy further OTM call).
- **Entry zone:** price at or just above 7500 after a small overshoot.
- **Thesis:** call wall holds as resistance; both legs expire worthless; keep full credit.
- **Invalidation:** price breaks 7500 on strong volume and holds above.

### Discipline Checklist (from transcripts)
- [ ] Why am I making this trade? Is the gamma profile still valid at entry?
- [ ] Did I wait for price to stretch slightly beyond the key level before entering on reversion?
- [ ] Is this a defined-risk structure (spread / butterfly / condor)? No naked shorts.
- [ ] Have I checked tomorrow's GEX profile to confirm the same key strike?
- [ ] Is today a normal day, or is it end-of-month, FOMC, CPI, or triple witching?
- [ ] Am I in a state of peace / logic, or chasing/recovering from a previous loss?
- [ ] Did I set a profit target and invalidation level before entering?

### Live Trade Signal Integration
- **Action:** STAY_OUT
- **Structure:** No Trade
- **Caution:** Wait for RTH open and clearer GEX setup.
- **Teaching note:** The live signal applies the same embedded rules plus feedback-loop filtering and RF outcome override. Use it as a confirmation, not a guarantee.

## J — OHLC

- OHLC not available from Yahoo Finance for this date.
