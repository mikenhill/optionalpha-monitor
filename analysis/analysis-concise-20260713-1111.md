# Daily GEX Analysis — 2026-07-13 11:11

**SPX Last:** 7550.85  
**Key Strike:** 7550 | **Key2 Strike:** 7545  
**Setup Classification:** PUT PILLAR

## A — Today's Values in Isolation

- **SPX Last:** 7550.85
- **Snapshot Time:** 2026-07-13 11:11
- **Key Strike:** 7550 | **Key2 Strike:** 7545
- **Setup Classification:** PUT PILLAR
- **Distance to Key:** 0.85 pts
- **Sentiment:** 47.5% of strikes positive gamma
- **Net GEX:** -1.14B (acceleration risk)
- **Total Call GEX:** 16.91B
- **Total Put GEX:** -18.05B
- **GEX Ratio:** -1.0675
- **KCS (Key Call Support):** 9.14
- **Dominance:** 13.12% of total absolute GEX sits at the key strike
- **Flip Level:** None
- **Key Absolute GEX:** 4.59B
- **Key Net GEX:** -1.01B | **Key Balance:** -22.03%
- **Key Call / Put GEX:** 1.79B / -2.80B
- **Key OI:** Call 1,932 / Put 3,024 → Net OI -1,092
- **Key Volume:** Call 36,798 / Put 42,785 → Net Vol -5,987
- **Total Call OI:** 57,116
- **Total Put OI:** 52,376
- **Total Call Volume:** 539,036
- **Total Put Volume:** 495,464
- **Top OI Strike:** 7500 (total 6,037)
- **Top Vol Strike:** 7550 (total 79,583)
- **Weighted Mean Put Strike (GEX):** 7532.68

## B — Today vs History

Historical rows available: 16
- Sentiment: 62.5% — middle of historical range
- Net GEX: 62.5% — middle of historical range
- Key Absolute: 62.5% — middle of historical range
- Key Dominance: 62.5% — middle of historical range
- Previous session (2026-06-26 11:17) key strike: 7350

## C — ML Enrichment

- **Vol Regime:** TIGHT (confidence 80.00%)
- **Direction:** FLAT (confidence 89.80%)
- **RF Outcome:** NEUTRAL (probability 50.00%)
- **HMM Regime:** Negative Trending

## D — Trade Logic & Invalidation

**Put Pillar:** Short put spread at/just below 7550. Invalidates if price breaks 7550 with momentum and holds below.

## E — Caution Notes

- Check tomorrow's GEX profile before pinning / iron butterfly theses.
- Verify economic calendar for FOMC, CPI, or other binary events.
- On monthly expiration / triple witching / end-of-quarter days, GEX signals are less reliable.

## F — OI & Volume Structure (Top Strikes)

| Strike | Char | Call OI | Put OI | Total OI | Call Vol | Put Vol | Abs GEX | Notes |
|--------|------|---------|--------|----------|----------|---------|---------|-------|
| 7500 | PUT PILLAR | 1,058 | 4,979 | 6,037 | 2,047 | 40,762 | 1.43B |  |
| 7600 | CALL WALL | 4,592 | 1,154 | 5,746 | 29,436 | 1,525 | 0.69B |  |
| 7495 | PUT PILLAR | 198 | 4,855 | 5,053 | 508 | 14,640 | 1.00B |  |
| 7450 | PUT PILLAR | 1,022 | 4,009 | 5,031 | 99 | 8,996 | 0.24B |  |
| 7550 | balanced | 1,932 | 3,024 | 4,956 | 36,798 | 42,785 | 4.59B | KEY |
| 7480 | PUT PILLAR | 302 | 4,578 | 4,880 | 370 | 12,870 | 0.58B |  |
| 7475 | PUT PILLAR | 1,118 | 2,682 | 3,800 | 327 | 10,477 | 0.38B |  |
| 7545 | call-heavy | 2,534 | 1,230 | 3,764 | 19,402 | 30,368 | 3.36B | KEY2 |
| 7530 | call-heavy | 2,565 | 1,117 | 3,682 | 6,744 | 29,625 | 2.41B |  |
| 7625 | CALL WALL | 3,503 | 36 | 3,539 | 6,015 | 95 | 0.17B |  |

- **OI SANDWICH: price 7550.85 between put-heavy 7500 and call-heavy 7625**

## G — Percentile Context (vs History)

- **Sample:** 1 historical days at time 1111
- **Net GEX:** 0.0% percentile (1 days at 1111)
- **Call GEX:** 100.0% percentile (1 days at 1111)
- **Put GEX:** 100.0% percentile (1 days at 1111)
- **Call OI:** 100.0% percentile (1 days at 1111)
- **Put OI:** 100.0% percentile (1 days at 1111)
- **Call Volume:** 100.0% percentile (1 days at 1111)
- **Put Volume:** 100.0% percentile (1 days at 1111)
- **KCS:** 100.0% percentile (1 days at 1111)
- **Dominance:** 100.0% percentile (1 days at 1111)

## H — Live Trade Signal

- **Setup Type:** PUT_PILLAR
- **Action:** SHORT_PUT_SPREAD
- **Structure:** Short Put Spread
- **Short Strike:** 7550
- **Wing Strike:** 7540
- **Rationale:** PUT_PILLAR: Put-heavy GEX at 7550 with strong put OI. Level may act as support. Sell put spread at/just below pillar. Entry: wait for price to touch or briefly break below 7550 then enter on rebound.
- **Invalidation:** Pillar fails if price breaks 7550 with momentum and closes below. Negative gamma acceleration below 7545 would signal cascade risk.
- **Caution:** OI alone cannot confirm direction. Volume at 7550 must confirm. Regime: Negative Trending.

## I — Lessons from GEX Teaching Files

### Core Principles
- Gamma is potential energy — it is highest at at-the-money, short-dated strikes.
- Market makers hedge continuously to stay delta-neutral; their hedging creates pressure at key strikes.
- Open interest alone is not directional — it can be condors, hedges, or spreads (Captain Condor artifact).
- GEX works best on normal days; it is less reliable on monthly expiration, FOMC, CPI, triple witching, and end-of-month/quarter/year.
- Charm (delta decay) causes hedging flows to change over time even if price does not move.

### Setup-Specific Recommendation
**PUT PILLAR lesson:** A strike with outsized put gamma + put open interest acts as a support floor. As price drops toward it, market makers buy hedges, creating upward pressure.
- **Trade:** Short put spread at/just below 7550 (sell put at 7550, buy further OTM put).
- **Entry zone:** price at or just below 7550 after a small overshoot.
- **Thesis:** put pillar holds as support; both legs expire worthless; keep full credit.
- **Invalidation:** price breaks 7550 with momentum and holds below.

### Discipline Checklist (from transcripts)
- [ ] Why am I making this trade? Is the gamma profile still valid at entry?
- [ ] Did I wait for price to stretch slightly beyond the key level before entering on reversion?
- [ ] Is this a defined-risk structure (spread / butterfly / condor)? No naked shorts.
- [ ] Have I checked tomorrow's GEX profile to confirm the same key strike?
- [ ] Is today a normal day, or is it end-of-month, FOMC, CPI, or triple witching?
- [ ] Am I in a state of peace / logic, or chasing/recovering from a previous loss?
- [ ] Did I set a profit target and invalidation level before entering?

### Live Trade Signal Integration
- **Action:** SHORT_PUT_SPREAD
- **Structure:** Short Put Spread
- **Caution:** OI alone cannot confirm direction. Volume at 7550 must confirm. Regime: Negative Trending.
- **Teaching note:** The live signal applies the same embedded rules plus feedback-loop filtering and RF outcome override. Use it as a confirmation, not a guarantee.

## J — OHLC

- Open: 7547.53 | High: 7565.37 | Low: 7529.33 | Close: 7550.75
