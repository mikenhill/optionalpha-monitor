# SPX GEX Report — Tuesday 9 June 2026
**Capture time:** 13:12 UK / 08:12 US Eastern  
**Script:** `optionalpha_daily-summary.py` | **Source row:** `daily_gex_summary-concise.csv`

---

## Yesterday's Accuracy Review — Monday 8 June 2026

**Yesterday's setup classified as: PUT_PILLAR at 7450**

Yesterday's report would have predicted 7450 as support with downward momentum risk given strongly negative net GEX (-8.02B) and put-heavy positioning at the key strike (key_put_gex = -2.18B vs key_call_gex = 1.02B, key_net_oi = -2942).

**What actually happened (OHLC):**
- Open: 7440.57 | High: 7466.81 | Low: 7395.13 | Close: 7405.73
- The 7450 key strike was tested intraday (open was below it at 7440) — the pillar did **not** hold as support. Price broke below and closed at 7405.73, well below the 7450 level.
- The low of 7395.13 was a 55pt break below the key strike — consistent with the PUT_PILLAR failing in a negative gamma environment.
- The close confirms downward continuation. The -8.02B net GEX was the most negative in the dataset; the negative gamma acceleration risk flagged for that day was realised.
- **Accuracy verdict:** The PUT_PILLAR thesis gave the correct bias (put-heavy, downside risk) but a trader relying on 7450 as hard support would have been hurt. The negative gamma context was the dominant force. This is a reminder from the transcripts: put pillars in strongly negative net GEX regimes are unreliable — downside cascades are more likely than bounces.

---

## Section A — Today's Values in Isolation

| Field | Value | Interpretation |
|-------|-------|----------------|
| `last` | **7405.73** | SPX price at 13:12 UK / 08:12 ET — captured at the open of the US session |
| `sentiment` | **35.0** | 35% of strikes have net positive GEX — bearish lean (below 45% threshold) |
| `gex_ratio` | **-1.25** | Put GEX slightly exceeds call GEX across the window; modestly put-dominated |
| `net_gex` | **-2.70B** | Total signed GEX is negative — market makers sell into falls, buy into rallies (acceleration regime) |
| `key_strike` | **7450** | Primary GEX anchor — the single highest absolute GEX strike in the window |
| `key_absolute` | **2.38B** | Total GEX magnitude at 7450 — moderate conviction level |
| `key_net` | **+0.18B** | Signed net at key strike is slightly positive (calls > puts at 7450) — atypically call-leaning for the key strike |
| `key_dominance_pct` | **9.88%** | Key strike holds less than 10% of total window GEX — distributed, not a dominant outlier |
| `key_call_gex` | **+1.28B** | Call GEX at 7450 — meaningful call wall presence |
| `key_put_gex` | **-1.10B** | Put GEX at 7450 — meaningful but call GEX is larger |
| `key_call_oi` | **2693** | Call open interest at 7450 |
| `key_put_oi` | **2320** | Put open interest at 7450 |
| `key_net_oi` | **+373** | Call OI exceeds put OI — mildly call-heavy structural positioning at key strike |
| `key_call_vol` | **3083** | Strong call volume at 7450 relative to OI — active call flow today |
| `key_put_vol` | **504** | Minimal put volume at 7450 |
| `key_vol_net` | **+2579** | Call volume heavily dominates put volume at key strike today — strong call flow signal |
| `key2_strike` | **7400** | Second GEX anchor — just 50 points below key strike |
| `key2_absolute` | **1.51B** | Second strike GEX is 63% of key strike magnitude (1.51 / 2.38) — significant two-strike cluster |
| `key2_call_oi` | **1,067** | *(from raw JSON)* Call OI at 7400 |
| `key2_put_oi` | **3,501** | *(from raw JSON)* Put OI at 7400 — strongly put-heavy |
| `key2_net_oi` | **-2,434** | *(from raw JSON)* Put OI dominates heavily at 7400 — PUT PILLAR character |
| **7500 OI** | **8,307 total** | *(from raw JSON)* **Highest OI strike in the window** — 7,315 calls / 992 puts / net_oi +6,323 / abs GEX 1.394B. Not ranked as key/key2 because proximity-weighting deprioritises it (95 pts above price), but represents the dominant structural call ceiling in the chain |

---

## Section B — Today vs All Prior Rows

**Full history for context:**

| Date | last | sentiment | net_gex | key_strike | key_absolute | key_dominance | key_net_oi | key_vol_net |
|------|------|-----------|---------|------------|--------------|---------------|------------|-------------|
| 02-Jun | 7595.78 | 50.0 | +2.36B | 7600 | 6.52B | 14.91% | +487 | +17906 |
| 03-Jun | 7560.13 | 30.0 | -20.03B | 7550 | 3.94B | 10.13% | -3478 | -73614 |
| 04-Jun | 7553.68 | 32.5 | -2.63B | 7550 | 1.14B | 12.17% | -311 | +1901 |
| 05-Jun | 7584.31 | 55.0 | -13.14B | 7550 | 6.24B | 12.27% | -1808 | +954 |
| 08-Jun | 7438.95 | 32.5 | -8.02B | 7450 | 3.20B | 10.26% | -2942 | +6206 |
| **09-Jun** | **7405.73** | **35.0** | **-2.70B** | **7450** | **2.38B** | **9.88%** | **+373** | **+2579** |

**Comparative observations:**

- **Sentiment (35.0):** Below-neutral for the third session in a row. Only 02-Jun and 05-Jun reached 50–55. The market is in a persistent bearish-lean GEX regime.
- **net_gex (-2.70B):** Less negative than yesterday (-8.02B) and much less than the extreme 03-Jun (-20.03B). However it remains negative — this is the fourth consecutive negative net GEX day. No positive gamma stabilisation in sight.
- **key_absolute (2.38B):** Lower than yesterday (3.20B) and well below the strong days (02-Jun: 6.52B, 05-Jun: 6.24B). Conviction is moderate-to-low. The key strike is not an authoritative outlier.
- **key_dominance_pct (9.88%):** The weakest dominance in the dataset. Below 10% means no single strike is clearly running the show — this approaches GEX Slide territory.
- **key_net_oi (+373):** A notable shift from yesterday (-2942). For the first time in the dataset, the key strike has net positive OI (more calls than puts). This is a structural change at 7450.
- **key_vol_net (+2579):** Very strong call volume dominance today (3083 calls vs 504 puts at 7450). This is directionally consistent with key_net_oi — both point to call flow. Compare 03-Jun where -73614 key_vol_net confirmed a brutal put-dominated day.
- **key_strike unchanged at 7450:** The key strike has held at 7450 for two consecutive sessions. However, yesterday's price (7438.95) and today's open (7405.73) are both below it, meaning 7450 is overhead resistance today, not a pin target.
- **key2_strike = 7400 (63% of key):** The second strike at 7400 is very close to the key (50 pts) and at 1.51B is 63% of key_absolute. This is a meaningful two-strike cluster, not a single dominant outlier. The 7400 level is directly relevant.

---

## Section C — GEX Teaching Point Mapping

### ❌ PIN / MAGNET — Does NOT fully qualify
- `key_net = +0.18B` means the balance at 7450 is slightly call-leaning, not balanced.
- `key_call_gex = 1.28B` vs `key_put_gex = -1.10B` — ratio is 54%/46%, borderline.
- `key_dominance_pct = 9.88%` — below 10% is a weak outlier. Per the transcripts, a clean pin requires the absolute gamma to be a pronounced outlier. At 9.88% of total window GEX, this is not it.
- `key2_absolute / key_absolute = 63%` — **TWO-STRIKE CLUSTER confirmed.** The transcripts explicitly state: if key2 is within ~20% of key, this is not a clean single-point pin. At 63% it is well within that range.
- **Verdict:** PIN is NOT the primary classification today. At best, weak pin dynamics may cause price to oscillate around 7450 during the US morning, but this cannot be traded as a clean butterfly setup.

### Full OI structure — three levels matter today

| Strike | Call OI | Put OI | Total OI | Net OI | Character | Distance from price |
|--------|---------|--------|----------|--------|-----------|-------------------|
| **7500** | 7,315 | 992 | **8,307** | +6,323 | Major CALL CEILING | +95 pts above |
| **7450** | 2,693 | 2,320 | 5,013 | +373 | CALL WALL (mild) | +45 pts above |
| *7405* | — | — | — | — | *current price* | — |
| **7400** | 1,067 | 3,501 | 4,568 | -2,434 | PUT PILLAR | -5 pts below |

**7500 is the dominant structural OI level in the entire window** — 8,307 total OI with a massively call-heavy net (+6,323). This is not ranked as key/key2 only because the proximity-weighted GEX algorithm discounts strikes far from the current price. But from a raw OI perspective, 7500 represents the **major call ceiling** for any sustained rally. Market makers with large call exposure at 7500 will be heavily delta-hedged (short futures) as price approaches that level.

The structural picture is therefore a **three-level stack:**
1. **7500** — major call ceiling / ultimate resistance (OI-dominant)
2. **7450** — intermediate call wall / near-term resistance (GEX-dominant)
3. **7400** — put pillar / near-term support (5 pts below current price)

SPX at 7405 is sitting just 5 points above the 7400 floor with two call ceilings stacked above. The proximity-weighted GEX correctly identifies 7450 and 7400 as the near-term anchors, but 7500 must be factored into any rally thesis — a move through 7450 does not have a clear path to 7500 without absorbing significant call hedging pressure along the way.

**Why 7450 ranks as KEY despite 7400 being closer to price — proximity-weighted GEX calculation:**

The algorithm (`process_gex_window.py`) scores each strike using a Gaussian decay:
```
weighted_GEX = raw_abs_GEX × exp(−0.5 × (distance / 50)²)
```
A strike 50 pts away retains ~60% of its raw weight; 100 pts away retains ~14%.

| Strike | Raw abs GEX | Dist from 7405.73 | Decay | Weighted GEX | Result |
|--------|-------------|-------------------|-------|--------------|--------|
| **7450** | 2.3834B | 44.3 pts | 0.6757 | **1.6105B** | **KEY** |
| **7400** | 1.5108B | 5.7 pts | 0.9935 | **1.5009B** | KEY2 |

7400 loses despite being 38 pts closer because its raw GEX (1.51B) is only 63% of 7450's (2.38B). The proximity advantage cannot overcome the raw GEX deficit. The margin is razor-thin — **only 0.11B separates KEY from KEY2** — confirming these are genuinely co-dominant anchors. If 7450's raw GEX fell below ~1.51B intraday, 7400 would become the KEY strike.

### ⚠️ CALL WALL (partial) — Developing at 7450
- `key_call_gex (+1.28B)` > `key_put_gex (-1.10B)` — calls dominate at key strike.
- `key_net_oi = +373` — mildly call-heavy OI.
- `key_vol_net = +2579` — strong call volume today.
- SPX at 7405 is **45 points below** the key strike. The 7450 strike is overhead.
- Per the transcripts (Kirk, Jack): when price is below a call-heavy strike with strong call OI, that strike acts as resistance. If price rallies towards 7450, market makers with call exposure will hedge by selling futures — capping upside at or near 7450.
- **Verdict:** 7450 is a CALL WALL / overhead resistance for today's session from the 7405 open. It is not a pin target because price needs to reach it first.

### ✅ NEGATIVE GAMMA ACCELERATION — Active
- `net_gex = -2.70B` — negative for the fourth consecutive session.
- Per the Matt Cashman interview: in negative gamma, market makers sell into falling prices and buy into rising prices. Moves in both directions may be amplified.
- The cascade risk below 7400 is real: `key2_strike = 7400` at 1.51B is the next significant level. If 7400 breaks with momentum, the next meaningful GEX concentration may be considerably lower, creating a rapid unidirectional move.
- **Cascade risk level: MODERATE.** Net GEX at -2.70B is far less extreme than 03-Jun (-20.03B) but still in acceleration territory.

### ⚠️ GEX SLIDE — Approaching
- `key_dominance_pct = 9.88%` — below 10%, the lowest in the dataset.
- GEX is distributed across many strikes rather than concentrated at one dominant level.
- Per the transcripts (Jack Slocum, "How I Recovered"): the GEX Slide means gamma exposure is spread, causing price to move through multiple strikes with hedging at each — fast, disjointed movement rather than a pin.
- Not a full GEX Slide yet, but the distribution is heading in that direction. No clean trade anchor exists.

### ⚠️ VOLUME DIVERGENCE — ABSENT (signals aligned)
- `key_vol_net = +2579` is in the same direction as `key_net_oi = +373` (both call-positive).
- This means intraday flow (calls being bought/traded at 7450 today) is consistent with structural OI positioning. No migration signal.
- However, note that this call activity at a strike 45 points above the current price is more likely to represent call buying for a rally than directional rotation of the pin anchor.

### ⚠️ CAPTAIN CONDOR / CONDOR ARTIFACT WARNING
- `key_call_oi = 2693`, `key_put_oi = 2320` at 7450 — moderately sized.
- These OI numbers may reflect iron condor or iron butterfly positioning (Captain Condor) rather than directional flow. Per the Matt Cashman interview, you cannot determine the purpose of OI from OI alone. A large balanced OI position at 7450 may simply be a condor whose strikes happen to be at 7450/7400, not a directional bet.
- **State explicitly:** OI alone cannot confirm directionality. The call_vol dominance (3083 vs 504 today) is more actionable than static OI.

---

## Section D — Educational Trade Logic

### Primary applicable setup: CALL WALL / OVERHEAD RESISTANCE at 7450

**Short Call Spread (Credit) — if price rallies to 7450:**
- Sell the **7450C**, buy the **7460C** for net credit
- Thesis: 7450 acts as overhead resistance; market makers hedge call exposure by selling futures at that level; price is repelled back below 7450
- Entry zone: price at 7448–7455 (at or just above the strike on a rally attempt)
- Entry timing: **wait for price to touch or briefly break above 7450, then enter on the rejection** — per Kirk's transcripts, the market can stretch just beyond a level; don't enter prematurely
- Expected credit: ~$1.50–2.50 for a $10 spread (estimate; verify live pricing)
- Max loss: spread width minus credit (e.g., $10 – $2.00 = $8.00 max loss, always defined)
- Hold time: scalp or session hold; exit if price closes above 7450 with momentum
- Zero-risk iron butterfly construction: **not applicable today** — current price (7405) is 45 points away from key strike; Stage 1 (ITM short put spread) and Stage 2 (ATM short call spread) require price to be at or near key_strike. Do not attempt zero-risk construction unless price rallies to within 5 points of 7450.

### Secondary applicable setup: KEY2 at 7400 as potential support test

**Short Put Spread (Credit) — if price dips to/below 7400:**
- Sell the **7400P**, buy the **7390P** for net credit
- Thesis: 7400 is the second-largest GEX cluster (1.51B); if price touches 7400, market maker hedging may cause a bounce
- Entry zone: 7395–7402 (at or just below 7400 on a dip)
- Entry timing: wait for price to touch or briefly break below 7400, then enter on the reversion attempt
- **Caution:** In a negative gamma environment (-2.70B net GEX), put pillars are unreliable. Yesterday's 7450 put pillar failed entirely. This trade carries elevated risk; use smaller size.
- Max loss: width minus credit (always defined)
- Hold time: scalp only — do not hold through lunch in negative gamma

### ❌ Iron Butterfly — NOT recommended today
- `key_dominance_pct = 9.88%` and two-strike cluster: the academic conditions for a clean iron butterfly pin are not met. The transcripts (Jack Slocum, Zero Risk video) require a pronounced single-strike outlier with balanced call/put GEX. Today does not have that.

---

## Section E — Invalidation Conditions

**Call Wall thesis (7450 resistance):**
- Invalidated if: SPX closes a 5-minute bar **above 7455** with rising volume. A sustained break above 7450 means the call wall has been absorbed and the level is no longer resistance.
- Migration signal: if `key_vol_net` turns negative intraday (put volume starts dominating at 7450), the anchor is drifting downward.

**7400 PUT PILLAR thesis:**
- 7400 has strongly put-heavy OI (3,501 puts vs 1,067 calls, net_oi = -2,434). This is a genuine PUT PILLAR character — put sellers / market makers have significant hedging obligations at this level that may cause a bounce when price reaches 7400.
- **However:** yesterday's 7450 put pillar (net_oi = -2,942, even more put-heavy) failed entirely in the negative gamma regime. The same risk applies here.
- Invalidated if: SPX breaks below **7390** with momentum and does not recover within 2–3 bars. In a negative gamma regime, cascades are self-reinforcing.
- Cascade scenario below 7400: with `net_gex = -2.70B`, a break below 7400 removes both structural anchors simultaneously. The next meaningful GEX level below 7400 is unknown without the full window data — treat any break of 7390 as an open cascade risk.

**What a negative gamma cascade looks like:**
- Per Matt Cashman (interview): price breaks below a key level, market makers must sell more futures to re-hedge their negative gamma, which drives price lower, requiring more selling. The process becomes self-reinforcing. It looks like a sharp, fast break with no bounce — "it just runs," as described in the transcripts. This is distinct from a normal sell-off.

**Macro override:**
- Any binary event (FOMC, CPI, NFP, geopolitical shock) overrides GEX mechanics entirely. Market makers may cease active hedging or widen their hedge ratios dramatically. Do not trade GEX setups into a scheduled binary event.

---

## Section F — Caution Notes

**Calendar:**
- Today is Monday 9 June 2026. This is **not** end of month, end of quarter, monthly expiration, or FOMC day based on calendar position. No elevated caution flag on calendar grounds — but **verify the economic calendar** before trading (Section G).

**Abnormal OI warning:**
- OI at key strike (call: 2693, put: 2320) is within normal range. No abnormal accumulation warning (compare: the crash-out day in Jack's "How I Recovered" transcript had 15,000–23,000 OI across multiple strikes).

**TOMORROW'S GEX — REQUIRED, NOT OPTIONAL:**
- Tomorrow's GEX profile has **not been checked**. Per the transcripts (Jack Slocum, Zero Risk video; Kirk's scalping video): market makers begin repositioning toward tomorrow's key strike in the final hours of today's session. If tomorrow's key strike differs from 7450, the 7450 call wall thesis may degrade after approximately 14:00–15:00 ET. **Any iron butterfly or late-session pin thesis cannot be validated without tomorrow's GEX profile.**

**Charm / delta decay:**
- Per Matt Cashman (interview): charm (delta decay) means market maker hedge ratios change throughout the day from time passage alone, independently of price. An OTM call position that had a delta of 0.30 this morning may have a delta of 0.15 by 14:00 ET — market makers will be buying back the futures they sold to hedge, creating a natural upward drift bias in the afternoon. This effect is most acute after 14:00 ET. Be aware of this bias when holding short call spreads into the afternoon.

**Capture time:**
- Data captured at **13:12 UK = 08:12 US Eastern** — at the US market open. This is very early in the session. The GEX profile may evolve significantly as the day progresses. Full 6.5-hour session remains. Intraday volume data is minimal at this point; the call volume spike (3083) at 7450 was captured at open and should be monitored for continuation or reversal. The transcripts consistently show that early-morning trades are the most uncertain; the best-quality setups develop after the first hour.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX profile on Option Alpha** — is the key strike also 7450? If yes, the call wall may persist into the close and a later-session short call spread becomes higher conviction. If no, do not hold any position at 7450 into the final 90 minutes of today.

2. **Confirm intraday call/put volume at 7450** — the 3083 call volume vs 504 put volume was captured at the open. Monitor whether call volume is continuing to accumulate (supports the call wall thesis) or whether put volume is picking up (signals the level is rotating lower). Per Jack's transcripts: volume confirming OI direction is the strongest entry signal.

3. **Verify the economic calendar** — confirm no CPI, FOMC, Fed speakers, or other binary macro events today. GEX setups do not hold through binary events.

4. **Monitor intraday GEX chart for profile rotation** — the 9.88% dominance and two-strike cluster means the GEX profile is relatively unstable. If 7400 begins to show higher absolute GEX than 7450 intraday, the key strike has migrated down. Per Kirk and Jack's transcripts, intraday profile shifts are common and must be tracked in real time.

---

*Report generated: 09 Jun 2026, 13:12 UK / 08:12 ET*  
*Source: `daily_gex_summary-concise.csv` | Transcripts: `Gex/*.txt`*
