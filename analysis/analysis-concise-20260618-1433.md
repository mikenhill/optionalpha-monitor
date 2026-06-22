# SPX GEX Concise Report — 2026-06-18
**Capture time:** 2026-06-18 09:31 ET
**SPX last:** 7501.96
**Report generated:** 14:33 BST / 09:33 ET

---

## Yesterday's Report vs What Actually Happened (2026-06-17)

**Yesterday's thesis:** PIN / MAGNET at 7495–7500 cluster. OI sandwich: floor 7495/7500 (balanced), ceiling 7600 (call wall). Volume divergence warning (heavy put flow at 7495). Expiration week caution.

**OHLC confirmed:** Open 7524.50 | High 7532.17 | Low 7402.61 | Close 7420.10

**Verdict:** The pin at 7495–7500 **failed decisively.** Price broke below 7495 with momentum and never recovered — the low hit 7402.61, a full 92 pts below the pin. The heavy put volume at 7495 (key_vol_net = -5618) that was flagged as a divergence warning materialised as the catalyst: when price broke the pin, accumulated put positions reached full delta and market makers sold futures aggressively, cascading through the 7450 and 7425 support levels. Close at 7420.10 was 100 pts below the pin zone. **The volume divergence signal was the critical warning and proved prescient.** The call wall at 7600 was never tested (high only 7532.17). The iron butterfly at 7495–7500 would have been a max loss if entered. Lesson confirmed: volume divergence in an expiration week environment degrades pin reliability.

---

## Section A — Today's Values in Isolation

**Today's row:** `SPX, 2026-06-18 09:31, last=7501.96`

| Field | Value | Interpretation |
|-------|-------|----------------|
| **last** | 7501.96 | Price has bounced +82 pts from yesterday's close of 7420.10. Currently right at the 7500 key strike. |
| **sentiment** | 62.5% | Bullish lean — 62.5% of strikes have net positive GEX. Highest since Jun 15 (100%) and Jun 9 (55%). |
| **gex_ratio** | 1.32 | Positive — call GEX exceeds put GEX. Moderate call dominance. |
| **net_gex** | +4.94B | Strongly positive. Third-highest reading after Jun 15 (+20.99B) and Jun 16 (+7.65B). Stabilising/mean-reverting regime. |
| **key_strike** | 7500 | The dominant GEX anchor for today. Price is sitting directly at this level (within 2 pts). |
| **key_absolute** | 4.45B | Strong. Second-highest since Jun 5 (6.24B) and Jun 2 (6.52B). High conviction anchor. |
| **key_net** | +0.70B | Net positive GEX — call GEX exceeds put GEX at key strike. Mild call wall character. |
| **key_dominance_pct** | 12.4% | Moderate — consistent with recent days (10–14% range). Not extreme concentration. |
| **key_call_gex** | 2.57B | Strong call GEX component. |
| **key_put_gex** | -1.88B | Substantial put GEX but clearly smaller than call side. |
| **key_call_oi** | 6192 | Large call OI at 7500. |
| **key_put_oi** | 4518 | Meaningful put OI but lower than calls. |
| **key_net_oi** | +1674 | **Call-heavy.** 6192 calls vs 4518 puts. Ratio ~1.37:1. This is a call wall, not a balanced pin. |
| **key_call_vol** | 5900 | Strong call volume already at capture time. |
| **key_put_vol** | 1437 | Low put volume. |
| **key_vol_net** | +4463 | **Strongly call-dominant flow.** Volume agrees with OI — no divergence today. |
| **key2_strike** | 7525 | 25 pts above key_strike. |
| **key2_absolute** | 1.98B | Only 44.5% of key_absolute — **not** a two-strike cluster. 7500 is a single dominant outlier. |

**key2_strike (7525) OI from Step 2B:**
- Call OI 2738 | Put OI 1757 | Total 4495 | Net OI +981
- Character: **CALL WALL (secondary).** Moderate call-heavy skew.

**Top OI strike (from Step 2B):**
- **7600**: Call OI 24,682 | Put OI 19,541 | Total 44,223 | Net OI +5141 | Abs GEX 3.23B
- Distance from current price: **+98 pts**
- Character: **MASSIVE CALL WALL** — highest total OI by far (44,223 vs 10,710 at 7500). However, it is 98 pts away and significantly discounted by the proximity-weighted GEX algorithm. This is why 7500 (10,710 OI but at-the-money) outranks 7600 as the key strike — the proximity weight gives much higher emphasis to near-price strikes.

**Full OI structure (top strikes by total OI):**

| Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX | Character | Distance |
|--------|---------|--------|----------|--------|---------|-----------|----------|
| 7600 | 24,682 | 19,541 | 44,223 | +5,141 | 3.23B | **CALL WALL (massive)** | +98 |
| 7500 | 6,192 | 4,518 | 10,710 | +1,674 | 4.45B | **CALL WALL (moderate)** | -2 |
| 7475 | 2,500 | 3,439 | 5,939 | -939 | 1.93B | **PUT PILLAR (mild)** | -27 |
| 7550 | 4,364 | 1,280 | 5,644 | +3,084 | 1.88B | **CALL WALL (strong)** | +48 |

**OI Sandwich:** Price (7502) sits between PUT PILLAR at 7475 (-27 pts, net OI -939) below and CALL WALL at 7525/7550 (+23/+48 pts) above. The true structural ceiling is 7600 (+98 pts, massive 44K OI), but the nearer resistance is 7525–7550. The structural floor is 7475.

---

## Section B — Today vs All Prior Rows

| Metric | Today | Historical Context |
|--------|-------|-------------------|
| **sentiment** (62.5%) | Highest since Jun 15 (100%). Above Jun 9 (55%). Bullish lean confirmed. |
| **net_gex** (+4.94B) | Third-highest in dataset. Strong positive gamma. The only higher days: Jun 15 (+20.99B, major outlier) and Jun 16 (+7.65B). Far above yesterday's +0.91B. |
| **key_absolute** (4.45B) | Strong — second tier. Higher than Jun 16 (3.96B), Jun 17 (3.00B). Matches Jun 3 (3.94B). High conviction level. |
| **key_dominance_pct** (12.4%) | Middle of historical range (10.1–18.1%). Neither concentrated nor distributed. |
| **key_net_oi** (+1674) | **Most call-heavy reading in the dataset.** Previous highs: +7766 (Jun 16 at 7600), +487 (Jun 2). Today's +1674 at the actual key_strike confirms this is a call wall, not a pin. |
| **key_vol_net** (+4463) | Strongly positive and aligned with key_net_oi direction. **No divergence.** This contrasts sharply with yesterday's -5618 divergence. Flow and structure agree. |
| **key_strike shift** | Moved from 7495 → 7500. After yesterday's 100pt selloff, the dominant anchor has reset 5 pts higher. The market has "re-centred" gamma at the round number. |
| **key2_absolute vs key_absolute** | 44.5% ratio — this is NOT a two-strike cluster. 7500 is a clear dominant outlier — much more single-point dominance than yesterday's 78.7% cluster. |

---

## Section C — GEX Teaching Point Mapping

### ✅ CALL WALL at 7500 — Primary Setup

- key_call_gex (2.57B) significantly exceeds key_put_gex (1.88B)
- key_net_oi = +1674 (call-heavy)
- key_vol_net = +4463 (intraday call volume strongly dominant)
- Per the transcripts: when price rises toward or above a call wall, market makers who sold those calls must sell underlying to hedge (negative delta adjustment), providing resistance.
- Price is currently AT the 7500 call wall — this is the first resistance test point.
- If price pushes above 7500, the next call walls are 7525 (net OI +981) and 7550 (net OI +3084).

### ✅ POSITIVE GAMMA STABILISING

- net_gex = +4.94B, the highest since Jun 16.
- Market makers are net dampening moves — selling into rallies, buying into dips.
- Mean-reversion behaviour expected. Large moves in either direction are less likely.
- Combined with the call wall at 7500: this creates resistance at current price but with a stabilising floor beneath.

### ✅ PUT PILLAR at 7475 — Secondary Support

- 7475: Put OI 3439 > Call OI 2500, net OI -939.
- Abs GEX 1.93B — the strongest put-leaning strike in the window.
- 27 pts below current price. If price sells off, 7475 is the first structural support.

### ✅ FULL OI STRUCTURE — Layered Call Walls Above

The OI structure from Step 2B reveals a strongly call-heavy environment above price:
- 7500: call wall (net OI +1674) — **current level**
- 7525: call wall (net OI +981) — 23 pts above
- 7550: call wall (net OI +3084) — 48 pts above
- 7600: massive call wall (net OI +5141, 44K total OI) — 98 pts above

Price must work through a sequence of call walls to rally significantly. In positive gamma, this creates a "resistance staircase" — each level provides friction on the upside. This strongly favours a session that stays near 7500 or drifts slowly, rather than a sharp rally.

The proximity-weighted algorithm ranked 7500 as key strike (4.45B) despite 7600 having 4x the OI (44K vs 10.7K) because: at 98 pts distance, the decay weight reduces 7600's effective contribution. The algorithm produces 3.23B for 7600 vs 4.45B for 7500 — the at-the-money strike wins.

### ❌ NOT: PIN / MAGNET
- key_net_oi = +1674 (call-heavy, not balanced)
- key_net = +0.70B (not close to zero)
- This is a directional call wall, not a balanced pin.

### ❌ NOT: NEGATIVE GAMMA ACCELERATION
- net_gex = +4.94B (strongly positive)
- No cascade risk today.

### ❌ NOT: GEX SLIDE
- key_dominance_pct at 12.4% with clear single-strike dominance. Not distributed.

### ❌ NOT: VOLUME DIVERGENCE
- key_vol_net (+4463) agrees with key_net_oi (+1674). No divergence signal. Flow confirms structure.

### ⚠️ CAPTAIN CONDOR WARNING (mild)
- 7600 has enormous OI on both sides (24,682 calls / 19,541 puts). This balanced but massive OI may reflect iron condor/butterfly positioning rather than directional flow. However, net OI is still +5141 (call-heavy) and 7600 is 98 pts from price — this warning is theoretical, not immediately actionable.

---

## Section D — Educational Trade Logic

### Primary: SHORT CALL SPREAD at 7525–7550 (Credit)

**Setup:** Call wall. Price at the first call wall (7500), with stacked call walls above.

**Structure:**
- Sell 7525C / Buy 7535C for net credit (~$2.50–$3.50 depending on fills)
- OR Sell 7550C / Buy 7560C for net credit (~$1.50–$2.50)
- $10 wide spread

**Thesis:** The call wall at 7525 (net OI +981, GEX 1.98B) holds as resistance. In positive gamma (+4.94B), market maker hedging dampens rallies. Price stays below 7525 and both legs expire worthless — keep full credit.

**Entry zone:** Wait for price to push above 7500 toward 7510–7520. Enter the short call spread when price shows first rejection/stall (ideally 7515–7525 with a candle showing upper wick).

**Entry timing:** Do not enter immediately. Wait for the first move above 7500 to confirm the wall is holding. If price blasts through 7525 with momentum, do not enter.

**Credit vs max loss:** ~$2.50 credit on $10 wide = $7.50 max loss. Reward:risk ~1:3.
**Hold time:** Session hold to expiry. With positive gamma, price should not sprint through resistance.

### Secondary: SHORT PUT SPREAD at 7475 (Credit) — Conditional

**Setup:** Put pillar. Only enter if price pulls back toward 7475.

**Structure:**
- Sell 7475P / Buy 7465P for net credit
- $10 wide

**Thesis:** Put pillar at 7475 (put OI 3439, net OI -939) holds as support. In positive gamma regime, dips are dampened.

**Entry zone:** Price at 7475–7482 after a pullback from 7500. Enter on first sign of support bounce.

**Credit vs max loss:** ~$2.00–$3.00 credit on $10 wide = $7.00–$8.00 max loss.
**Hold time:** Session hold to expiry.

### NOT Eligible: Zero-Risk Iron Butterfly

The zero-risk iron butterfly requires a BALANCED PIN where key_net is near zero and key_net_oi is near zero. Today's key_strike is a call wall (key_net +0.70B, key_net_oi +1674) — the setup does not qualify for the zero-risk construction. Do not attempt.

### NOT Eligible: Iron Butterfly at 7500

An iron butterfly would require price to stay pinned at exactly 7500. Today's setup is a call wall, not a pin. Price is more likely to drift away from 7500 (pull to either 7475 floor or 7525+ resistance staircase) than to oscillate around it symmetrically. The asymmetry in OI makes a pin unlikely.

---

## Section E — Invalidation Conditions

### Call Wall at 7525:
- **Invalidated if:** Price breaks above 7535 with sustained momentum (two consecutive 5-min closes above 7535). This would indicate the 7525 call wall has been absorbed and the next target is 7550.
- **Cascade risk:** If 7525 breaks, the stacked call walls at 7550 (+3084 net OI) and 7600 (+5141) create successive resistance — a "blow through" all the way to 7600 is unlikely in positive gamma, but each level must be monitored independently.

### Put Pillar at 7475:
- **Invalidated if:** Price breaks below 7465 with momentum. If 7475 fails, the next support is 7450 (OI 4584, balanced net OI -2) and then 7425 (net OI -345, mild put).
- **Negative gamma cascade risk:** Not applicable today (net_gex +4.94B). Even if 7475 breaks, the move should be dampened, not accelerated.

### Overall regime change:
- If net_gex turns negative on a mid-session refresh, the positive gamma stabilising thesis collapses. In that scenario, exit all short premium positions.
- If key_vol_net shifts from +4463 to significantly negative (e.g., -3000+), this would be a divergence signal indicating the call wall may be migrating — re-assess.

### Macro override:
- FOMC announcement would override all GEX levels. See Section F.

---

## Section F — Caution Notes

**⚠️ EXPIRATION WEEK — THURSDAY, TWO DAYS TO JUNE MONTHLY:**
Today is Thursday June 18. June monthly (triple) expiration is Friday June 20. Per the transcripts: "on monthly expirations... the zero DTE action which is typically a major driver of SPX price becomes less relevant" and "on those days specifically end of month, end of quarter, end of year, triple witching... the gamma exposure profiles on those days are not as reliable." **Today and tomorrow have reduced GEX reliability.** Position size accordingly.

**⚠️ FOMC DAY — VERIFY ECONOMIC CALENDAR:**
June 18 is the date of the June 2026 FOMC statement/press conference (typically released 14:00 ET). **If FOMC is today, do NOT trade any short premium positions.** Binary events override all GEX levels entirely. **VERIFY THIS IMMEDIATELY on the economic calendar before any trades.**

**⚠️ TOMORROW'S GEX — NOT CHECKED (REQUIRED):**
Tomorrow's GEX profile has not been checked. With monthly expiration on Friday, tomorrow (Friday June 20) will see massive position rotation and OpEx mechanics. The 7500 call wall may not persist into tomorrow. Market makers begin repositioning toward tomorrow's level in the final hours of today's session. Check Option Alpha before any afternoon hold.

**Charm / delta decay:**
Capture at 09:31 ET — approximately 30 minutes into the session. Full trading day remains (5.75 hours). Charm effects are minimal at this early time. The heaviest decay period is 13:00–15:00 ET. The call-heavy OI at 7500 will decay asymmetrically — call delta decays faster than put delta if price stays at or below 7500, which may slightly reduce the call wall's resistance strength toward end of day.

**Capture time = 09:31 ET (early session):** Very early capture. The full OI structure is fresh but intraday volume patterns are just beginning to develop. Recommend refreshing at 11:00–12:00 ET for a mid-session update once volume patterns are established.

**Abnormal OI at 7600:** The 44,223 total OI at 7600 is extraordinarily large — likely reflects monthly expiration positioning (both structured trades and hedging). This is not a normal 0DTE level — it is monthly OpEx OI. Treat it as background structure, not an intraday actionable target.

---

## Section G — Required Actions Before Trading

1. **CRITICAL: Verify FOMC schedule.** If FOMC is today (June 18), do NOT trade short premium. Binary event overrides all GEX analysis. Check economic calendar immediately.

2. **Check tomorrow's (Jun 19/20) GEX profile on Option Alpha.** Monthly expiration Friday — confirm whether 7500 remains the key strike for tomorrow or if gamma is migrating.

3. **Monitor key_vol_net through the session.** Currently +4463 (no divergence). If it flips negative (>-2000), the call wall thesis weakens and the anchor may be migrating.

4. **Wait for price to push 10–20 pts above 7500 before entering the short call spread.** Do not sell the 7525C immediately — wait for the call wall to be tested and show rejection.

5. **Re-run `optionalpha_daily.py` + `optionalpha_daily-summary.py` at 11:00–12:00 ET** for mid-session update. Early capture means volume patterns are still developing.

6. **Reduce position size.** Expiration week + potential FOMC = double caution. Use half normal size on any trade today.

---

*Report generated: 2026-06-18 14:33 BST / 09:33 ET*
*Previous report: analysis-concise-20260617-1534.md*
