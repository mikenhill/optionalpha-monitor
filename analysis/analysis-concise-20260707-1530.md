# Daily GEX Analysis — 2026-07-07 15:30

**SPX Last:** 7493.26  
**Key Strike:** 7500 | **Key2 Strike:** 7490  
**Setup Classification:** NEGATIVE GAMMA ACCELERATION

## A — Today's Values in Isolation

- **SPX Last:** 7493.26
- **Snapshot Time:** 2026-07-07 15:30
- **Key Strike:** 7500 | **Key2 Strike:** 7490
- **Setup Classification:** NEGATIVE GAMMA ACCELERATION
- **Distance to Key:** 6.74 pts
- **Sentiment:** 27.5% of strikes positive gamma
- **Net GEX:** -11.48B (acceleration risk)
- **Total Call GEX:** 9.97B
- **Total Put GEX:** -21.45B
- **GEX Ratio:** -2.152
- **KCS (Key Call Support):** 13.89
- **Dominance:** 29.39% of total absolute GEX sits at the key strike
- **Flip Level:** None
- **Key Absolute GEX:** 9.24B
- **Key Net GEX:** -3.18B | **Key Balance:** -34.48%
- **Key Call / Put GEX:** 3.03B / -6.21B
- **Key OI:** Call 1,756 / Put 3,604 → Net OI -1,848
- **Key Volume:** Call 102,478 / Put 156,112 → Net Vol -53,634
- **Total Call OI:** 44,519
- **Total Put OI:** 53,039
- **Total Call Volume:** 1,347,724
- **Total Put Volume:** 1,457,606
- **Top OI Strike:** 7550 (total 11,421)
- **Top Vol Strike:** 7500 (total 258,590)
- **Weighted Mean Put Strike (GEX):** 7491.79

## B — Today vs History

Historical rows available: 16
- Sentiment: 18.8% — low/extreme vs history
- Net GEX: 25.0% — middle of historical range
- Key Absolute: 93.8% — high/extreme vs history
- Key Dominance: 100.0% — high/extreme vs history
- Previous session (2026-06-26 11:17) key strike: 7350

## C — ML Enrichment

- **Vol Regime:** TIGHT (confidence 88.10%)
- **Direction:** FLAT (confidence 83.20%)
- **RF Outcome:** NEUTRAL (probability 50.00%)

## D — Trade Logic & Invalidation

**No short premium:** Negative gamma environment — avoid selling premium.

## E — Caution Notes

- Check tomorrow's GEX profile before pinning / iron butterfly theses.
- Verify economic calendar for FOMC, CPI, or other binary events.
- On monthly expiration / triple witching / end-of-quarter days, GEX signals are less reliable.

## F — OI & Volume Structure (Top Strikes)

| Strike | Char | Call OI | Put OI | Total OI | Call Vol | Put Vol | Abs GEX | Notes |
|--------|------|---------|--------|----------|----------|---------|---------|-------|
| 7550 | balanced | 6,555 | 4,866 | 11,421 | 65,468 | 7,707 | 0.43B |  |
| 7500 | put-heavy | 1,756 | 3,604 | 5,360 | 102,478 | 156,112 | 9.24B | KEY |
| 7575 | CALL WALL | 4,237 | 184 | 4,421 | 21,979 | 451 | 0.00B |  |
| 7450 | PUT PILLAR | 975 | 2,876 | 3,851 | 2,335 | 48,665 | 0.51B |  |
| 7580 | CALL WALL | 3,349 | 496 | 3,845 | 15,866 | 192 | 0.00B |  |
| 7400 | PUT PILLAR | 128 | 3,332 | 3,460 | 200 | 12,246 | 0.10B |  |
| 7570 | CALL WALL | 2,879 | 303 | 3,182 | 19,523 | 602 | 0.01B |  |
| 7590 | CALL WALL | 3,114 | 65 | 3,179 | 9,221 | 56 | 0.00B |  |
| 7425 | PUT PILLAR | 67 | 2,911 | 2,978 | 474 | 15,571 | 0.20B |  |
| 7545 | CALL WALL | 1,874 | 844 | 2,718 | 39,969 | 2,751 | 0.18B |  |

- **OI SANDWICH: price 7493.26 between put-heavy 7400 and call-heavy 7545**

## G — Percentile Context (vs History)

- **Sample:** 126 historical days at time 935
- **Net GEX:** 90.5% percentile (126 days at 935)
- **Call GEX:** 30.2% percentile (126 days at 935)
- **Put GEX:** 100.0% percentile (126 days at 935)
- **Call OI:** 23.0% percentile (126 days at 935)
- **Put OI:** 59.5% percentile (126 days at 935)
- **Call Volume:** 100.0% percentile (126 days at 935)
- **Put Volume:** 100.0% percentile (126 days at 935)
- **KCS:** 99.2% percentile (126 days at 935)
- **Dominance:** 100.0% percentile (126 days at 935)

## H — Live Trade Signal

- **Setup Type:** NEG_GAMMA
- **Action:** STAY_OUT
- **Structure:** No Trade
- **Rationale:** NEG_GAMMA: Net GEX = -11.48B — strongly negative. Market maker hedging may amplify moves. Do not sell premium into negative gamma. Risk of cascade below flip point.
- **Invalidation:** N/A — no trade.
- **Caution:** Avoid all short premium strategies until GEX turns positive or neutral.

## I — Lessons from GEX Teaching Files

### Core Principles
- Gamma is potential energy — it is highest at at-the-money, short-dated strikes.
- Market makers hedge continuously to stay delta-neutral; their hedging creates pressure at key strikes.
- Open interest alone is not directional — it can be condors, hedges, or spreads (Captain Condor artifact).
- GEX works best on normal days; it is less reliable on monthly expiration, FOMC, CPI, triple witching, and end-of-month/quarter/year.
- Charm (delta decay) causes hedging flows to change over time even if price does not move.

### Setup-Specific Recommendation
**NEGATIVE GAMMA lesson:** When net GEX is strongly negative, market makers are short gamma. They sell into falls and buy into rallies, which can amplify moves in either direction (convexity / cascade risk).
- **Trade:** No short premium. Avoid credit spreads and iron butterflies.
- **Opportunity:** Long directional spreads (long call or put spreads) in the direction of the break, but only on confirmed momentum.
- **Caution:** If key2 (7490) is close below key (7500), a break of both can produce a rapid move.

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
- **Caution:** Avoid all short premium strategies until GEX turns positive or neutral.
- **Teaching note:** The live signal applies the same embedded rules plus feedback-loop filtering and RF outcome override. Use it as a confirmation, not a guarantee.

## J — OHLC

- Open: 7516.63 | High: 7536.06 | Low: 7478.63 | Close: 7503.85
