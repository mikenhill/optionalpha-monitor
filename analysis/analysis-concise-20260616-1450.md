# SPX GEX Concise Report — 2026-06-16
**Capture time:** 2026-06-16 09:36 ET  
**SPX last:** 7563.55  
**Report generated:** 14:50 BST / 09:50 ET

---

## Yesterday's Report vs What Actually Happened (2026-06-15)

**Yesterday's setup (from analysis-concise-20260615-1603.md):** CALL_WALL at 7550. Sentiment 100%, net_gex +20.99B, key_net_oi +3373 (call-heavy), key_vol_net +31,183 (extreme call flow). Thesis: 7550 acts as resistance. Short call spread was the indicated trade.

**What actually happened:** Close only = 7554.29. Open/High/Low not yet published by Yahoo Finance (data lag — expected to populate tomorrow).

**Partial verdict:** Price closed at 7554.29 — 4.29 pts *above* the call wall at 7550. The level was not a hard ceiling; price settled marginally through it. Two interpretations are consistent with the transcripts: (1) the call wall was absorbed intraday and price settled just above the key strike, consistent with a pin/magnet dynamic rather than pure resistance; (2) the extreme positive gamma (+20.99B) and 100% sentiment created a stabilising environment where the call wall became a gravitational centre rather than a barrier. A short call spread entered at 7550 on a touch would have been challenged if price closed above. Full accuracy verdict deferred until OHLC publishes.

---

## Section A — Today's Values in Isolation

**Today's row:** `SPX, 2026-06-16 09:36, last=7563.55`

| Field | Value | Interpretation |
|-------|-------|----------------|
| **last** | 7563.55 | +9.85 pts above yesterday's close of 7553.70 (approx). Opening slightly higher. |
| **sentiment** | 52.5% | Just above neutral. Marginal bullish lean — not decisive. Prior reading was 100% (Jun 15) — significant normalisation. |
| **gex_ratio** | 1.64 | Call GEX exceeds put GEX by 1.64:1. Mild call dominance in aggregate. |
| **net_gex** | +7.65B | Positive gamma environment. Market makers are net stabilising — dampened, mean-reverting price action expected. Slightly higher than this morning's earlier capture (+6.45B). |
| **key_strike** | 7600 | Primary GEX anchor. 36.45 pts above current price. Unchanged from the 08:16 capture — confirmed as the dominant level. |
| **key_absolute** | 3.96B | Moderate-high magnitude. Slightly larger than the 08:16 reading (3.65B) — the 7600 level is building GEX through the session. |
| **key_net** | +2.94B | Strongly net positive at 7600 — call GEX dominates. Call wall character confirmed. |
| **key_dominance_pct** | 12.62% | 7600 accounts for 12.6% of total window GEX. Low-moderate concentration — not a single dominant outlier but clearly the leading strike. |
| **key_call_gex** | 3.45B | Large call GEX at 7600 |
| **key_put_gex** | -0.51B | Small put GEX at 7600. Call/put ratio ~6.8:1 — strongly one-sided. |
| **key_call_oi** | 9116 | Large call OI at 7600 — unchanged from earlier capture (structural, not intraday flow) |
| **key_put_oi** | 1350 | Small put OI. Structural asymmetry confirmed. |
| **key_net_oi** | +7766 | Strongly call-heavy. The most call-dominated reading in the entire dataset. |
| **key_call_vol** | 11,850 | Call volume at 7600 has grown significantly since 08:16 (was 5,571). Active call buying/trading at this level intraday. |
| **key_put_vol** | 188 | Negligible put volume at 7600. |
| **key_vol_net** | +11,662 | Call volume flow strongly confirms structural call positioning. No divergence. Call activity at 7600 is accelerating through the morning. |
| **key2_strike** | 7550 | Second GEX strike — 13.55 pts below current price. |
| **key2_absolute** | 2.24B | 56.6% of key_absolute — secondary but not trivial. |

**key2_strike (7550) OI from Step 2B:**
- Call OI 2198 | Put OI 1921 | Total 4119 | Net OI +277
- Character: **Balanced / weak PIN** — nearly equal call and put OI. Minor call edge. Price has moved above this level this morning (+13.55 pts).

**Top OI strike (from Step 2B):**
- **7600**: 9116 call / 1350 put | Total 10,466 | Net OI +7766 | Abs GEX 3.961B
- Top OI and key_strike are the same level. Distance: +36.45 pts above price.
- This alignment means the proximity-weighted GEX algorithm and raw OI structure agree — 7600 is unambiguously the dominant structural level.

**Full OI structure (top strikes by total OI):**

| Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX | Character | Distance |
|--------|---------|--------|----------|--------|---------|-----------|----------|
| 7600 | 9116 | 1350 | 10,466 | +7766 | 3.961B | **CALL WALL** | +36 |
| 7500 | 1496 | 3617 | 5,113 | -2121 | 1.019B | **PUT PILLAR** | -64 |
| 7650 | 4169 | 54 | 4,223 | +4115 | 0.328B | **CALL WALL** | +86 |
| 7550 | 2198 | 1921 | 4,119 | +277 | 2.242B | Balanced/PIN | -14 |

**OI Sandwich:** Price at 7563 sits between 7500 (put pillar / structural floor, -64 pts) and 7600 (call wall / structural ceiling, +36 pts). The sandwich range has narrowed from the earlier view — price has moved up 9 pts since the 08:16 capture, closing in on the call wall.

---

## Section B — Today vs All Prior Rows

**Sentiment (52.5%):**
- Prior range: 30% (Jun 3) to 100% (Jun 15).
- Today is right at the historical median. A sharp pullback from yesterday's extreme 100% — the market is no longer in an extreme stabilising state. Broadly neutral.

**net_gex (+7.65B):**
- Prior range: -20.03B (Jun 3) to +20.99B (Jun 15).
- Today is moderately positive — well above the dangerous negative readings of Jun 3 and Jun 5. Comfortably in stabilising territory. Slightly stronger than the 08:16 reading (+6.45B), suggesting intraday GEX is building.

**key_absolute (3.96B):**
- Prior range: 1.14B (Jun 4) to 6.52B (Jun 2).
- Mid-range. Not a high-conviction dominant outlier. Comparable to Jun 8 (3.20B) and Jun 9 (2.58B). Moderate concentration.

**key_dominance_pct (12.62%):**
- Prior range: 10.13% to 18.05% (yesterday).
- Near the lower end of the range — GEX is somewhat distributed. Yesterday's 18.05% was unusually concentrated; today is more normal.

**key_net_oi (+7766):**
- Prior range: -3478 (Jun 3) to +3373 (Jun 15, yesterday).
- **Today is by far the most call-heavy net OI in the dataset.** +7766 vs +3373 yesterday. The structural call positioning at 7600 has increased materially.

**key_vol_net (+11,662):**
- Yesterday's +31,183 was extreme. Today's +11,662 by 09:36 is already substantial for early session — call flow at 7600 is active. Aligns with net_oi (no divergence).

**key_strike shift:** 7550 (Jun 15) → 7600 (Jun 16). The dominant GEX anchor has shifted up 50 pts. This is consistent with the market settling above 7550 yesterday and the 7600 call wall becoming the next structural resistance target.

**key2 proximity:** 2.24B vs 3.96B = 56.6% of key_absolute. This is a moderate secondary — closer to a two-level structure than a clean single-point outlier, but 7600 is clearly dominant. Not a pure two-strike cluster.

---

## Section C — GEX Teaching Point Mapping

### ✅ CALL WALL at 7600 — Primary Setup
- key_call_gex (3.45B) vs key_put_gex (-0.51B). 6.8:1 ratio.
- key_call_oi (9116) vs key_put_oi (1350). Net OI +7766 — strongest in dataset.
- key_vol_net +11,662 — call volume accelerating this morning, confirming structural positioning.
- Per the transcripts (Kirk's scalping videos, Jack's GEX wall trades): "when I see a large block of call open interest, that to me was showing that this could potentially be a wall that's going to be hard to push through." Entry is to wait for price to reach the level and show rejection, then sell a short call spread.
- **Confirmed as the primary setup for today.**

### ✅ BALANCED ZONE at 7550–7565 (distributed friction, not a clean pin)
- 7550: OI 4119, net +277 (balanced). Abs GEX 2.242B.
- 7560: OI 3678, net -188 (slightly put-heavy). Abs GEX 2.166B.
- 7555: OI 3124, net -440 (mild put lean). Abs GEX 1.785B.
- Price (7563) is currently sitting within this zone.
- As discussed earlier today: **these strikes cannot be simply summed** — each triggers separate hedging events at separate price points. The correct reading is a zone of distributed balanced GEX creating friction and oscillation at current price levels, not a single dominant anchor.
- This zone may act as a gravitational band keeping price range-bound until it decisively moves toward 7600 or pulls back toward 7500.

### ✅ POSITIVE GAMMA STABILISING
- net_gex +7.65B — positive. Stabilising hedging regime.
- Sentiment 52.5% — neutral, not extreme.
- Mean-reverting, range-bound behaviour expected. Moves amplified only if net_gex deteriorates intraday.

### ✅ OI SANDWICH (price between 7500 floor and 7600 ceiling)
- Structural floor: 7500 (put pillar, net OI -2121).
- Structural ceiling: 7600 (call wall, net OI +7766).
- Price at 7563 is 63 pts above the floor and 37 pts below the ceiling. Closer to the ceiling.

### ❌ NOT: NEGATIVE GAMMA ACCELERATION
- net_gex +7.65B. No acceleration risk.

### ❌ NOT: GEX SLIDE
- Clear structural anchors exist at 7600 and 7500. Not a distributed slide day.

### ❌ NOT: VOLUME DIVERGENCE
- key_vol_net +11,662 aligns with key_net_oi +7766. Flow confirms structure.

### ⚠️ CAPTAIN CONDOR WARNING
- 9116 call OI at 7600 is large. Per the Mat Cashman interview: "I've heard them referred to as Captain Condor... they trade a lot of condors." Large one-sided call OI at a round number (7600) may partially reflect condor short call legs or spread positioning, not purely directional call buying. The call wall thesis is sound, but the magnitude of OI should be interpreted with this caveat — it cannot confirm that 7600 is a ceiling for entirely directional reasons.

---

## Section D — Educational Trade Logic

### Primary: SHORT CALL SPREAD at 7600 (Call Wall)

**Structure (defined risk, short premium):**
- **Sell 7600C / Buy 7610C** for net credit
- Thesis: call wall at 7600 holds as resistance; price fails to break through; both legs expire worthless
- **Entry zone:** Price at or just above 7600 (7598–7605)
- **Entry timing:** Wait for price to push up to 7600 and show a clear rejection — do not pre-sell 37 pts away from current price. Per the transcripts: "I should have waited a little bit longer... the market can stretch just a little bit beyond these levels."
- **Expected credit:** ~$3–6 for a 10-pt wide spread (SPX 0DTE, 37 pts OTM at time of writing — credit will increase as price approaches)
- **Max loss:** $10 spread width minus credit = ~$4–7 per spread
- **Hold time:** Scalp to session close — take profit on rejection; exit with a stop if 7610 is breached
- **Zero-risk construction:** Not applicable — 7600 is strongly one-sided (call wall), not the balanced call/put OI required for the zero-risk iron butterfly

### Secondary: SHORT PUT SPREAD at 7500 (Put Pillar / Floor)

**Structure:**
- **Sell 7500P / Buy 7490P** for net credit
- Thesis: structural put pillar at 7500 acts as support; market makers long puts hedge by buying underlying on approach
- Entry zone: only relevant if price falls to 7495–7505 (currently 63 pts away — not actionable now)
- Max loss: $10 width minus credit
- **Not actionable at current price** — monitor for later in session if price pulls back sharply

### Zero-Risk Iron Butterfly consideration at 7550/7560 zone:

The balanced OI zone (7550–7560) has the near-equal call/put structure required for the zero-risk construction. However:
1. No single strike in this zone is dominant enough as a standalone pin — GEX is distributed across 7550, 7555, 7560
2. Tomorrow's GEX has not been checked — required before attempting this construction
3. Price has already moved above 7550 — Stage 1 (selling ITM put spread on a dip below 7550) may require waiting for a pullback

**If price pulls back to 7550–7555 and tomorrow's GEX confirms the same zone as key:** the zero-risk construction becomes viable. Stage 1: sell ITM put spread on the dip below 7550. Stage 2: sell call spread at 7550–7555 on the rebound. Combined credit must exceed $5 wing width for zero risk.

---

## Section E — Invalidation Conditions

### Call wall at 7600:
- **Invalidated if:** SPX breaks and closes above 7610 with momentum and volume. A clean break means the wall has been absorbed — upside may accelerate as MM delta unwinds from short call hedges add buying pressure toward 7650 (next call wall, OI 4223, net +4115).
- **Cascade scenario upside:** 7600 break → 7620 (call OI 2699) → 7650 (call wall, 4169 OI). Each level has residual call OI but much smaller than 7600 — a break of 7600 with momentum could reach 7620–7650 quickly.
- **Migration signal:** If key_vol_net at 7600 turns negative (put flow accumulating at the level) or a mid-session GEX refresh shows 7550 or 7650 becoming dominant, the 7600 thesis has degraded.

### Balanced zone 7550–7565:
- **Invalidated if:** Price breaks cleanly below 7545 with momentum — the distributed balanced GEX friction zone has failed, and price likely moves toward 7500.
- Below 7500 (put pillar): a break of the structural floor with momentum could trigger a negative gamma cascade toward 7450, particularly if net_gex deteriorates intraday.

### OI sandwich range 7500–7600:
- **Macro override:** Fed speaker, unexpected CPI revision, geopolitical shock, or binary event would override GEX structure entirely.

---

## Section F — Caution Notes

**⚠️ EXPIRATION WEEK — HEIGHTENED CAUTION:**
Today is **Monday of June monthly expiration week**. June monthly options expire **Friday June 20, 2026** (third Friday). Per Jack Slocum's crash-out lesson: "on a monthly expiration when there's lots of symbols expiring driving market prices based on their own gamma exposure levels, it's less likely that the SPX gamma exposure levels will be able to control the price range." Individual equity options expirations all week will add noise to SPX GEX profiles. **Trade smaller position sizes, tighten stops, and avoid wide end-of-day holds through Friday.**

**key_absolute magnitude (3.96B):** Mid-range — not abnormally large. No abnormal day warning on GEX size alone.

**⚠️ TOMORROW'S GEX — NOT CHECKED (REQUIRED):**
Tomorrow's GEX profile has not been checked. The call wall thesis at 7600 **cannot be fully validated** without it. Per the transcripts (Jack Slocum, Zero Risk video): "if tomorrow's gamma exposure profile is different, the pin won't hold all the way until end of day because towards the end of the day, the price will naturally start gravitating towards wherever the pin price is for the following day." Check Option Alpha for tomorrow's key strike before any end-of-day hold.

**Charm / delta decay:**
Capture at 09:36 ET — early in the US session. Charm effects are minimal now but become most acute by mid-afternoon (13:00–15:00 ET). As the 7600 call wall OI decays delta over the session, MM hedging flows will evolve independently of price. By 14:00 ET, check whether the call wall is still holding or whether charm-driven delta unwind is causing the level to weaken.

**Capture time = 09:36 ET:** Early session — approximately 5.5 hours of US trading remain. The GEX profile should be refreshed at 11:00–11:30 ET once the opening range is established. Today's dominant structure (7600 call wall) is consistent across both the 08:16 and 09:36 captures — this increases confidence in the level.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX on Option Alpha.** Is 7600 the key strike for tomorrow as well? If yes, the call wall thesis extends and end-of-day holds are supported. If tomorrow's key is at 7550 or lower, the 7600 level may degrade into the close as MM flows reposition.

2. **Monitor intraday call volume at 7600.** At 09:36 key_call_vol was already 11,850. If this continues to build without price approaching the level, it may indicate positioning for a push to 7600 later in the session — increasing the probability of a touch and potential rejection entry.

3. **Verify the economic calendar.** Confirm no Fed speakers, macro releases, or binary events today that would override the GEX structure. June expiration week often coincides with increased macro sensitivity.

4. **Re-run capture at 11:00–11:30 ET** once the opening range is established. Run `optionalpha_capture.py` + `optionalpha_daily.py` and regenerate the concise CSV to get an updated snapshot with mid-morning OI and volume data.

5. **Expiration week active — trade smaller.** This applies Monday through Friday this week. Reduce position size relative to a normal week.

---

*Report generated: 2026-06-16 14:50 BST / 09:50 ET*
