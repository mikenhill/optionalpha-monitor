# SPX GEX Concise Report — 2026-06-16
**Capture time:** 2026-06-16 08:16 ET  
**SPX last:** 7554.29

---

## Yesterday's Report vs What Actually Happened (2026-06-15)

**Yesterday's setup:** CALL_WALL at 7550. Key dominance 18.05% — the highest in the dataset. Sentiment was 100% (every strike net positive), net_gex +20.99B, key_call_oi 4991 vs key_put_oi 1618 (strongly call-heavy at 7550). key_vol_net +31,183 — extreme call flow. Call wall thesis: 7550 acts as resistance, short call spread was the indicated trade.

**What actually happened (OHLC):** Close only available = 7554.29. Open/High/Low not yet published by Yahoo Finance.

**Verdict:** Price ended the day 4 pts *above* 7550, suggesting the call wall did not cap the day cleanly — the level was breached or the price settled just above it. The 100% sentiment and extreme net_gex of +20.99B indicated powerful stabilising gamma, which is consistent with a tight range and a close near the key strike. A short call spread at 7550 entered on a touch would have been tested. Without intraday OHLC, a precise accuracy verdict is not possible, but the close of 7554.29 is consistent with the key strike acting as a short-term magnet or being slightly exceeded before settling. Lesson: in highly positive gamma environments, call walls can act more like pins than hard ceilings.

---

## Section A — Today's Values in Isolation

| Field | Value | Interpretation |
|-------|-------|----------------|
| **last** | 7554.29 | SPX at capture — essentially flat from yesterday's close |
| **sentiment** | 47.5% | Slightly below neutral (50%). Just below the 45% bearish threshold — borderline, leaning slightly bearish. Not decisively one way. |
| **gex_ratio** | 1.52 | Call GEX exceeds put GEX by ratio of 1.52:1. Moderate call dominance in aggregate, but not extreme. |
| **net_gex** | +6.45B | Net positive gamma across the window. Market makers are net stabilising — moves should be dampened, not amplified. Not in acceleration territory. |
| **key_strike** | 7600 | The highest absolute GEX strike today. 46 pts above current price. |
| **key_absolute** | 3.65B | Magnitude of GEX at 7600. Moderate by historical comparison (see Section B). |
| **key_net** | +2.71B | Strongly net positive at 7600 — call GEX significantly exceeds put GEX. Call wall character. |
| **key_dominance_pct** | 11.61% | 7600 accounts for 11.6% of total window GEX. Low-moderate concentration — not a dominant outlier. |
| **key_call_gex** | 3.18B | Call GEX at 7600 |
| **key_put_gex** | -0.47B | Put GEX at 7600 — small. Call/put ratio ~6.8:1. Strongly call-sided. |
| **key_call_oi** | 9116 | Large call open interest at 7600 |
| **key_put_oi** | 1350 | Small put OI at 7600 |
| **key_net_oi** | +7766 | Strongly call-heavy. 9116 calls vs 1350 puts. Classic call wall structure. |
| **key_call_vol** | 5571 | Call volume at 7600 today |
| **key_put_vol** | 59 | Negligible put volume at 7600 today |
| **key_vol_net** | +5512 | Call volume flow strongly confirming the call-side structural bias. No divergence — flow aligns with OI. |
| **key2_strike** | 7550 | Second GEX strike — current price level. |
| **key2_absolute** | 2.33B | 63.8% of key_absolute. Not a distant secondary — fairly close cluster (see Section B). |

**key2_strike OI (from Step 2B raw JSON):**
- 7550: Call OI 2198 | Put OI 1921 | Total 4119 | Net OI +277
- Character: **Balanced / mild PIN** — call and put OI nearly equal. Minor call edge. Neither a clean wall nor a pillar. Price is sitting on this level right now.

**Top OI strike (from Step 2B raw JSON):**
- **7600** is the top OI strike with 10,466 total (9116 call / 1350 put). Net OI +7766.
- This is also the key_strike. The top OI strike and the GEX key strike are the same level today — alignment between structural positioning and proximity-weighted GEX.
- Distance from price: +46 pts above current 7554.

**Full OI table (top strikes by total OI):**

| Strike | Call OI | Put OI | Total OI | Net OI | Character | Distance |
|--------|---------|--------|----------|--------|-----------|----------|
| 7600 | 9116 | 1350 | 10466 | +7766 | **CALL WALL** | +46 |
| 7500 | 1496 | 3617 | 5113 | -2121 | **PUT PILLAR** | -54 |
| 7650 | 4169 | 54 | 4223 | +4115 | **CALL WALL** | +96 |
| 7550 | 2198 | 1921 | 4119 | +277 | Balanced/PIN | 0 (at price) |

**OI Sandwich:** Price at 7554 is sitting between 7500 (put pillar, -54 pts) and 7600 (call wall, +46 pts). Classic sandwich structure. Structural floor: 7500. Structural ceiling: 7600.

---

## Section B — Today vs All Prior Rows

**Sentiment (47.5%):** 
- Prior range: 30.0% (Jun 3) to 100.0% (Jun 15). Median ~47.5%.
- Today is at the historical median — neutral. A significant drop from yesterday's extreme 100%.

**net_gex (+6.45B):**
- Prior range: -20.03B (Jun 3) to +20.99B (Jun 15).
- Today is moderately positive. Well above the dangerous negative readings of Jun 3 (-20.03B) and Jun 5 (-13.14B). Stabilising environment.

**key_absolute (3.65B):**
- Prior range: 1.14B (Jun 4) to 6.52B (Jun 2) and 6.24B (Jun 5).
- Today is mid-range. Not a high-conviction dominant outlier. Moderate GEX concentration.

**key_dominance_pct (11.61%):**
- Prior range: 10.13% to 18.05% (yesterday).
- Near the low end of the range. GEX is somewhat distributed today — not tightly concentrated at one level.

**key_net_oi (+7766):**
- Prior readings ranged from -3478 (Jun 3, strongly put-heavy) to +3373 (yesterday).
- Today's +7766 is the most call-heavy net OI in the dataset by a significant margin. Structural call positioning at 7600 is the most pronounced we've seen.

**key_vol_net (+5512):**
- Yesterday: +31,183 (extreme call flow). Today is also call-dominated (+5512) but far more moderate.
- No divergence — volume confirms the call-side structural bias at 7600.

**key_strike change:** Yesterday 7550 → today 7600. The primary GEX anchor has shifted upward by 50 pts. This implies the market is tracking the next upper resistance level. The old pin level (7550) is now key2 — it has not disappeared, it's just no longer the dominant anchor.

**key2_absolute vs key_absolute:** 2.33B vs 3.65B = 63.8%. Per the transcripts, if key2 is within ~20% of key, it qualifies as a "two-strike cluster, not a clean single-point pin." At 63.8% of key_absolute, key2 is meaningfully smaller — this is a **moderate outlier** with a secondary, not a two-strike cluster. 7600 is clearly dominant, but 7550 remains a credible secondary level.

---

## Section C — GEX Teaching Point Mapping

### ✅ CALL WALL at 7600
- key_call_gex (3.18B) >> key_put_gex (0.47B). Ratio 6.8:1.
- key_call_oi (9116) >> key_put_oi (1350). Net OI +7766 — strongest call-heavy reading in the dataset.
- key_vol_net +5512 — call flow today confirms structural call positioning.
- The 7600 level is a classic call wall: large one-sided call OI with minimal put counterpart. Per the transcripts (Kirk/Jack), a call wall means market makers are short calls and will sell underlying as price approaches, creating resistance.
- **Primary setup for today: CALL WALL at 7600.**

### ✅ BALANCED PIN / MAGNET at 7550 (secondary)
- key2_strike 7550 has call OI 2198 / put OI 1921 — nearly equal. Net OI +277.
- This is the price's current level. It has mild balanced GEX character (Abs GEX 2.33B).
- Price is essentially sitting on a weak pin structure at 7550, with the dominant pull level 46 pts higher.
- Per the transcripts: "as soon as I find a day where the absolute gamma is associated with one strike and call and put gamma is highest... price has a good chance of pinning." Today's 7550 has balanced OI but not dominant GEX — this is a weak secondary pin, not a full pin setup.

### ✅ POSITIVE GAMMA STABILISING
- net_gex +6.45B — positive. Market makers are net long gamma. Per the transcripts and Mat Cashman interview: positive gamma means market makers buy dips and sell rallies, dampening moves.
- Sentiment 47.5% — borderline, not confirming strong stabilising signal, but the positive net_gex dominates.
- Expect mean-reverting, range-bound behaviour rather than trending acceleration.

### ⚠️ OI SANDWICH (price between two structural levels)
- Price 7554 sits between 7500 put pillar (support) and 7600 call wall (resistance).
- This is the most important structural context for today. The range 7500–7600 is defined by structural OI anchors on both sides.

### ❌ NOT: NEGATIVE GAMMA ACCELERATION
- net_gex is +6.45B. No acceleration risk today.

### ❌ NOT: GEX SLIDE
- key_dominance 11.61% is low, but there are clear structural anchors at 7600 and 7500 — this is not a distributed slide day.

### ❌ NOT: VOLUME DIVERGENCE
- key_vol_net +5512 aligns with key_net_oi +7766. No divergence — flow confirms structure.

### ⚠️ CAPTAIN CONDOR WARNING
- 9116 call OI at 7600 is large. This could partly reflect condor/iron butterfly positioning by institutional or systematic traders (the transcripts specifically cite "Captain Condor" — large recurring condor trades). Large one-sided OI alone does not confirm pure directional intent — some of these calls may be spread legs, not directional bets. The call wall thesis stands, but the magnitude of the OI resistance should be interpreted with this caveat.

---

## Section D — Educational Trade Logic

### Primary: SHORT CALL SPREAD at 7600 (Call Wall)

**Setup:** Call wall at 7600. Price currently 46 pts below at 7554. Positive gamma environment — mean reverting, not trending.

**Structure (defined risk):**
- Sell 7600C / Buy 7610C for net credit
- Thesis: 7600 holds as resistance; both legs expire worthless; keep full credit
- Entry zone: price at or just above 7600 (7598–7605), on a touch-and-reject
- Entry timing: wait for price to push up to 7600 and show rejection — do not sell before price reaches the level
- Expected credit: approximately $3–5 (based on SPX 0DTE spreads at 46 pts OTM)
- Max loss: $10 spread width minus credit = $5–7 max loss per spread
- Hold time: scalp to session close — hold if rejection is clean, exit if 7600 is broken with momentum
- **Does NOT qualify for zero-risk iron butterfly** — the balanced OI required for zero-risk construction exists at 7550 (key2), not 7600. 7600 is one-sided call wall, not a balanced pin.

### Secondary: SHORT PUT SPREAD at 7500 (Put Pillar / Floor)

**Structure:**
- Sell 7500P / Buy 7490P for net credit
- Thesis: 7500 acts as structural floor (put pillar OI: 3617 put / 1496 call, net -2121); market makers long puts here will buy underlying on approach, creating support
- Entry zone: price approaching 7500 (7495–7505), after overshoot
- Entry timing: wait for brief break below 7500 then enter on bounce
- Expected credit: deep OTM (~50 pts), credit will be small (~$1–2). Better suited as a defined-risk hedge or lottery trade than primary income.
- Max loss: $10 width minus credit

### Zero-Risk Iron Butterfly consideration at 7550:

Per the "Zero Risk 0DTE" transcript (Jack Slocum): zero-risk iron butterfly requires balanced call/put OI at one strike. Today's 7550 (key2) has call OI 2198 / put OI 1921 — roughly balanced. However, the GEX dominance at 7550 is only 2.33B and key_dominance is split with 7600. The balanced OI at 7550 could support a zero-risk construction **only if**:
1. Tomorrow's GEX confirms 7550 as a key strike
2. Price dips below 7550 first (Stage 1: sell ITM put spread for credit)
3. Price rebounds to 7550 (Stage 2: sell call spread at 7550 for credit)
4. Combined credit ≥ $5 wing width

**Today this construction is marginal** — 7550 is near-balanced but not dominant. The cleaner trade is the short call spread at 7600.

---

## Section E — Invalidation Conditions

### Call wall at 7600:
- **Invalidated if:** SPX breaks and closes above 7610 with volume. A sustained move through 7600 means the call wall has been absorbed or rolled, and upside momentum may accelerate (market makers forced to buy back short delta hedges, adding to upside).
- **Cascade risk upside:** If 7600 breaks, next structural level is 7650 (call wall, 4169 call OI / 54 put OI, +96 pts). Move from 7600 to 7650 could be swift in positive gamma (buy-the-break dynamic from MM delta unwind).
- **Volume/GEX migration signal:** If key_vol_net at 7600 turns negative (put volume accumulating) or if a re-run of the GEX data mid-session shows 7550 or 7650 becoming dominant, the 7600 wall thesis has degraded.

### OI sandwich / range 7500–7600:
- **Invalidated if:** SPX breaks below 7500 with momentum. The put pillar at 7500 should absorb the first test, but a break through it in negative gamma (if net_gex deteriorates intraday) could trigger a cascade toward 7450 or lower.
- **Macro override:** FOMC, CPI, Fed speaker, or geopolitical shock would override the GEX setup entirely.

### Balanced pin at 7550:
- **Invalidated if:** Price trends cleanly above 7580 or below 7520 with sustained momentum. The balanced OI structure at 7550 only pins price when there is enough hedging flow at the level — once price moves away decisively, the pin effect is lost for the session.

---

## Section F — Caution Notes

**Calendar check (2026-06-16 — Monday):**
- Not end of month (June 30), not end of quarter, not monthly expiration (that would be third Friday, Jun 19 is the third Friday of June — **this week is expiration week for June monthly options**).
- June monthly expiration is **Friday June 20th, 2026** (third Friday). Today is Monday of expiration week. This is a **heightened caution flag** — per the transcripts (Jack Slocum's crash-out lesson): "on a monthly expiration when there's lots of symbols expiring driving market prices based on their own gamma exposure levels, it's less likely that the SPX gamma exposure levels will be able to control the price range as well." Open interest numbers across individual names will be elevated all week, and Friday is a **triple witching environment** (SPX options, equity options, futures). GEX profiles this week should be treated with increased caution — abnormal days warning applies from today through Friday.
- No FOMC currently scheduled for this date per standard 2026 calendar. Verify economic calendar before trading.

**key_absolute magnitude:** 3.65B is mid-range — not abnormally large. No "abnormal day" warning on GEX size alone today.

**Tomorrow's GEX — REQUIRED, NOT OPTIONAL:**
Tomorrow's GEX profile has **not been checked**. The call wall thesis at 7600 and any pin construction at 7550 **cannot be fully validated** without it. Per the transcripts: "market makers begin repositioning toward tomorrow's level in the final hours of the current session." If tomorrow's key strike is at 7550 or below, the 7600 level may weaken into the close as MM hedging flows rotate. Check tomorrow's GEX on Option Alpha before entering any trade with an end-of-day hold.

**Charm / delta decay:**
Capture was at 08:16 ET — pre-market / very early open. This is early in the US session. Per Mat Cashman's interview: charm (delta decay) means market makers' hedging positions become shorter delta as the day progresses, causing natural drift toward key strikes. The 7600 strike is 46 pts above current price — charm flows from an OTM call wall will have limited effect until price approaches the level. If price drifts toward 7600 intraday, charm effects become increasingly relevant in the afternoon.

**Capture time = 08:16 ET:** This is the pre-market / opening period. The full session (6+ hours of US trading) remains. The GEX profile may shift materially once the session opens and options volume accumulates — this snapshot is early and should be refreshed at 10:00–11:00 ET once the opening range is established.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX profile on Option Alpha.** Confirm whether 7600 is also the key strike for tomorrow. If it is, the call wall thesis extends and end-of-day holds are safer. If tomorrow's key is at 7550 or lower, the 7600 level may degrade into the close.

2. **Confirm intraday volume accumulation.** Monitor whether call volume at 7600 continues to build (confirming wall) or whether volume is accumulating at a different level (migration signal). Run `optionalpha_capture.py` + `optionalpha_daily.py` again at 10:30–11:00 ET once the opening range is established.

3. **Verify the economic calendar.** Confirm no Fed speakers, CPI release, or binary macro events today that would override the GEX structure.

4. **Monitor intraday GEX rotation.** Key question: does 7550 (key2, currently balanced) start accumulating more balanced OI and become the dominant strike intraday? If so, a weak pin at 7550 may develop and an iron butterfly construction becomes more viable.

5. **Expiration week caution active.** This is the week of June monthly expiration (Friday June 20). GEX profiles this week carry elevated noise from individual equity expiration flows. Trade smaller, tighten stops, avoid end-of-day holds on wide structures.

---

*Report generated: 2026-06-16 13:18 BST / 08:18 ET*
