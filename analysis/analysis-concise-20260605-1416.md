# SPX Concise GEX Report — 5 June 2026

**Captured:** 2026-06-05 14:16 BST  
**SPX Last:** 7584.31  

---

## Section A: Today's Values in Isolation

| Field | Value | Note |
|---|---|---|
| Sentiment | **55.0%** | Marginally bullish — 22 of 40 bars net positive |
| GEX Ratio | **-1.70** | Mild put-dominance overall despite positive sentiment |
| Net GEX | **-13.14B** | Negative gamma environment — moves can accelerate |
| Key Strike | **7550** | Primary GEX anchor for the day |
| Key Absolute | **6.24B** | Very large absolute GEX at 7550 |
| Key Net | **-1.05B** | Net negative at key strike — put side heavier |
| Key Dominance | **12.27%** | Key strike holds 12.3% of total window GEX — moderate concentration |
| Key Call GEX | +2.59B | Substantial call exposure |
| Key Put GEX | -3.64B | Put exposure meaningfully larger than calls |
| Key Call OI | 4,459 | |
| Key Put OI | 6,267 | |
| Key Net OI | **-1,808** | Put OI exceeds call OI by 1,808 — put side structurally heavier |
| Key Call Vol | 3,814 | |
| Key Put Vol | 2,860 | |
| Key Vol Net | **+954** | Call volume exceeds put volume today — bullish intraday flow signal |
| Key2 Strike | **7540** | Second-highest GEX strike, only 10pts below key strike |
| Key2 Absolute | **5.29B** | Very close in magnitude to key strike (5.29B vs 6.24B) |

### Setup Classification

**Primary: Near-Pin with Put-Pillar lean**

The 7550 strike has a large absolute GEX (6.24B) with substantial exposure on both the call and put sides. The call/put split is not 50/50 (calls +2.59B vs puts -3.64B), so this is not a perfect pin, but both sides are large enough to create two-directional hedging pressure. This is consistent with a **modified pin / magnet** rather than a clean one-sided wall or pillar.

The put OI significantly outweighs call OI at 7550 (`key_net_oi = -1,808`), which adds a structural **put-pillar** character — suggesting the 7550 level may provide support if price falls toward it.

However, **intraday volume is call-heavy** (`key_vol_net = +954`). This is a potentially important divergence: the structural positioning is put-heavy, but today's trading flow is buying calls.

> **Teaching point — volume as GEX migration signal (More Informed 0DTE Trades transcript):** Jack Slocum explicitly teaches that a surge in call volume at a strike *different from or above* the established key strike can signal that the intraday GEX anchor is migrating upward, not just that sentiment is bullish. The call volume at 7550 (+3,814) with price already at 7584 warrants watching whether volume is clustering above 7550 (suggesting drift toward a higher level) or specifically at 7550 (confirming the existing pin). This is not simply a bullish sentiment signal — it may indicate the GEX level itself is shifting.

**Secondary anchor: 7540 (5.29B)** — very close in magnitude to 7550. The proximity of key2 to key creates a tight cluster: 7540–7550 is a 10-point band of dense GEX. Price is likely to be sensitive to this zone.

> **Teaching point — outlier qualifier (Quick Wins, Zero Risk transcripts):** The transcripts teach that the strongest pin setups occur when *one* strike is a pronounced outlier versus all others. Key2 at 5.29B is only 15% smaller than key (6.24B). This is *not* a clean single-strike domination — it is a two-strike cluster. The pin thesis is weaker than a day with one clearly dominant outlier, and the 7540–7550 band should be treated as the relevant zone rather than a single point.

> **Teaching point — Captain Condor / condor artifact (Mat Cashman transcript):** Large balanced call and put OI at a single strike can reflect condor or iron butterfly trades rather than directional positioning. The 4,459 call OI and 6,267 put OI at 7550 may partially represent condor structures rather than pure directional flow. OI alone cannot reveal whether these contracts represent hedges, spreads, or directional bets. This is a known limitation and does not invalidate the GEX reading, but means OI concentration alone cannot be used as confirmation.

### Price Context

SPX last at **7584.31** is **+34.31 pts above the 7550 key strike**. Price has already moved above the key strike. This is the classic "above the wall/pin" scenario. The key questions intraday are:

1. Will 7550 act as support on any pullback?
2. Is the +34pt stretch enough to justify a mean-reversion short?
3. Does the call-volume signal suggest a continuation bid rather than a fade?

---

## Section B: Today vs Prior Days

| Date | Last | Sentiment | Net GEX | Key Strike | Key Abs | Key Net | Key Net OI | Key Vol Net | Key2 |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-03 | 7560.13 | 30.0% | -20.03B | 7550 | 3.94B | -3.21B | -3,478 | -73,614 | 7580 |
| 2026-06-04 | 7553.68 | 32.5% | -2.63B | 7525 | 1.16B | -0.13B | -252 | -789 | 7550 |
| 2026-06-05 | 7584.31 | **55.0%** | -13.14B | 7550 | **6.24B** | -1.05B | -1,808 | **+954** | 7540 |

### Key Observations vs History

**1. Sentiment has flipped materially bullish.**  
Jun 3–4 sentiment was 30–32.5% — decisively bearish-leaning. Today it jumps to 55.0%. This is a significant one-day shift and aligns with SPX price moving ~30 pts higher from Jun 4's 7553 to today's 7584.

**2. Key strike 7550 is now well-established.**  
Jun 3 had 7550 as the key strike too (3.94B). Jun 4 shifted to 7525 (1.16B — notably weaker). Today 7550 returns with much greater force (6.24B). The 7550 level has been the dominant GEX strike for two of the last three days and is significantly stronger today than on Jun 3.

**3. Key absolute GEX has surged: 1.16B → 6.24B.**  
Jun 4 was a low-conviction day with a weak key strike (1.16B). Today's 6.24B is more than 5× that. This is a high-conviction structural day with a well-defined anchor, much closer to the Jun 3 character (3.94B) but larger.

**4. Key2 converging toward key strike.**  
Jun 3: key2 = 7580 (above).  
Jun 4: key2 = 7550 (same as today's key).  
Jun 5: key2 = 7540 (below, and very strong at 5.29B).  
The cluster is tightening around 7540–7550, and both strikes are substantial. This is consistent with the 7540–7550 zone being a gravitational band rather than a single price pin.

**5. Put-heavy positioning consistent across all three days.**  
`key_net_oi` has been negative all three days (-3,478 / -252 / -1,808). The structural bias at the key strike is consistently put-heavy OI. **Today's positive `key_vol_net` (+954) is the first call-volume-dominant day in this short series** and stands out as a change in intraday character.

**6. Net GEX swings — negative gamma persists.**  
Net GEX remains negative all three days, meaning the broader gamma environment continues to support move amplification rather than dampening. The -13.14B today is lower in magnitude than Jun 3 (-20.03B) but much larger than Jun 4 (-2.63B).

---

## Section C: GEX Teaching Point Mapping

| Teaching Point | Applies? | Evidence |
|---|---|---|
| **Pin / Magnet** | ✅ Partial | Both call and put GEX large at 7550; tight cluster with 7540 |
| **Put Pillar** | ✅ Yes | Put OI and put GEX dominate at 7550; support if price revisits |
| **Call Wall** | ⚠️ Weak | Call GEX at 7550 is large in absolute terms but put side larger |
| **Negative Gamma Acceleration** | ✅ Yes | Net GEX -13.14B; moves can cascade in either direction |
| **GEX Slide** | ❌ No | Exposure concentrated at 7550/7540, not spread across many strikes |
| **Positive Gamma Stabilising** | ❌ No | Overall net GEX is negative |
| **Today/Tomorrow Alignment** | ❌ Not checked — required step | No tomorrow data captured yet — see note below |

The dominant setup is: **negative gamma environment with a near-pin / put-pillar at 7540–7550**, currently trading 34 pts above the key strike, with intraday call volume suggesting possible GEX migration rather than simple bullish sentiment.

> **Teaching point — tomorrow's GEX is a required step, not optional (Zero Risk, Quick Wins, Anticipate 0DTE transcripts):** All three transcripts explicitly state that checking tomorrow's GEX profile is a *required* part of evaluating whether today's pin will hold into the close. If tomorrow's key strike is at a different level, market makers will begin repositioning in the late afternoon and the pin may break before expiration. The report cannot assign full confidence to the 7550 pin thesis without this check. **This is the single most significant gap in this analysis.** Tomorrow's GEX should be captured or checked on the Option Alpha platform before placing any trades based on pin or iron butterfly logic.

> **Teaching point — pin timing degradation (Quick Wins transcript):** Even when a pin is valid, it may not hold all day. Slocum explicitly shows a case where the price opened near the prior day's key strike, traded around it through the session, but began drifting toward the *following* day's key strike in the final hours. At 14:16 BST (approximately 09:16 US Eastern), this report was captured before the US session midpoint. If a tomorrow check reveals a different key strike, the 7550 pin may weaken materially after 13:00–14:00 ET.

> **Teaching point — charm / delta decay (Mat Cashman transcript):** Cashman specifically teaches that charm — the change in delta over time — causes market makers to adjust hedges throughout the day even when price does not move. As 0DTE options decay toward expiration, delta exposure at each strike changes purely from time passage. This means hedging flows around 7550 are not static — they will intensify or diminish as the day progresses regardless of price action. By mid-afternoon US time, charm effects are at their most acute and can cause price to drift toward or away from the GEX strike without any obvious news trigger.

---

## Section D: Educational Trade Logic

> These are educational examples only. Not financial advice.

### Setup 1 — Put-Pillar Rebound (if price pulls back to 7550)

**Thesis:** If SPX pulls back from 7584 toward 7550–7555, the put-pillar and pin character of 7550 (large put OI + balanced absolute GEX) may trigger market maker hedging that supports a bounce.

- **Structure:** Long call spread, e.g. 7550/7555 (buy 7550C, sell 7555C)
- **Entry zone:** Price between 7550–7555, ideally after a small overshoot below 7550
- **Target:** Quick revert to 7560–7565
- **Hold time:** Minutes, not hours
- **Reward-to-risk:** Look for 80–100% R/R on entry

### Setup 2 — Fade the Extension (if price pushes toward 7600+)

**Thesis:** Price is already 34 pts above key strike. If it stretches further toward 7600 without much volume support, the call GEX at 7550 creates a pull back toward the strike. Look for a short-duration put spread.

- **Structure:** Long put spread, e.g. 7580/7575 (buy 7580P, sell 7575P)
- **Entry zone:** Price 7590–7600 with no new GEX justification
- **Target:** Revert toward 7575–7580
- **Caution:** Positive `key_vol_net` today (+954 calls) may mean the bid is real — wait for rejection signal in price action before fading

### Setup 3 — Iron Butterfly at 7550 (pin play / zero-risk construction)

**Thesis:** If price returns to the 7550 zone, the 7540–7550 cluster could produce oscillation (pin behaviour). A narrow iron butterfly centred at 7550 would profit from staying in range.

> **Teaching point — zero-risk iron butterfly construction (Zero Risk transcript):** Slocum teaches a specific two-legged entry mechanic designed to achieve zero net risk. Step 1: when price dips *below* 7550, open an **in-the-money short put spread** (e.g. sell 7555P / buy 7545P) for a credit. Step 2: when price bounces back *up to* 7550, add a **short call spread at 7550** (e.g. sell 7550C / buy 7560C) for a second credit. If the combined credit equals or exceeds the width of the wings, the iron butterfly has zero maximum risk. This construction is only viable when today's pin thesis is high-conviction *and* tomorrow's GEX confirms the same level — both legs must be entered before checking whether the pin is drifting.

- **Structure:** Two-stage iron butterfly (short put spread on dip → short call spread on rebound)
- **Entry zone:** Stage 1 below 7550; Stage 2 at/near 7550 on rebound
- **Target:** Hold for large portion of combined credit; close before final 30 mins unless pin is very strong
- **Risk:** -13.14B net GEX means accelerated moves are possible if 7540 breaks. Keep wings tight and size small. **Do not attempt zero-risk construction without confirming tomorrow's GEX first.**

---

## Section E: Invalidation Conditions

- **7550 breaks decisively to the downside** — if price drops through 7540 with momentum and put OI does not provide a bounce, the pillar has failed. Close long call spreads immediately.
- **Cascade risk below 7540 in negative gamma** — with net GEX at -13.14B, a clean break below 7540 (key2 level) could trigger market maker selling into the decline, accelerating the move sharply. The teaching is explicit: in negative gamma, hedgers sell as price falls. A break of 7540 is not just a stop-out signal — it may be the start of a fast directional move. Do not add to long positions on a break of 7540.
- **GEX profile rotates intraday** — if the key strike shifts materially (e.g. to 7500 or 7600), today's setup is stale.
- **Call volume surge continues above 7590** — positive `key_vol_net` (+954) suggests buyers are active. If SPX rips through 7590–7600 with increasing call volume, the fade thesis is wrong and should be abandoned.
- **Broad market news or catalyst** — any unexpected macro news can override GEX entirely in a negative gamma environment.

---

## Section F: Caution Notes

| Factor | Status |
|---|---|
| **FOMC / Fed day** | Unknown — check calendar |
| **End of month** | No — early June |
| **Monthly expiration** | No — 5 June is a standard Friday expiration |
| **Triple witching** | No |
| **Unusually large OI** | Moderate — key put OI 6,267, call OI 4,459. Not extreme. |
| **Low conviction day** | No — key absolute 6.24B is the strongest day in this 3-day series |
| **Intraday profile change risk** | Moderate — negative gamma (-13.14B net) means profiles can shift quickly |
| **Tomorrow's GEX — required check** | ⚠️ **Not done** — pin and iron butterfly thesis cannot be fully validated without this |
| **Charm / delta decay** | Active — at 14:16 BST capture time, charm is increasing and will affect hedging through the US afternoon session |

**June monthly expiration Friday (third Friday) is June 20.** Today, June 5, is a standard weekly expiration. Volume and OI at the key strike (6.2K put OI / 4.5K call OI) are meaningful but not extreme. The setup is relatively reliable compared to expiration or event days.

The most important caution today is the **divergence between structural positioning (put-heavy OI) and intraday flow (call-volume dominant)**. This is not a clean one-directional signal. The put pillar at 7550 supports longs on a dip, but the call-volume strength argues against aggressively fading the current level. A wait-and-see approach to allow price to define its range first is consistent with the teaching framework.

---

---

## Section G: What This Report Did Not Have — Required Actions Before Trading

The following steps are explicitly taught across the transcripts as **required** before acting on any GEX-based trade. They were not available at report generation time:

1. **Check tomorrow's GEX profile** on the Option Alpha platform. Identify whether tomorrow's key strike is also 7550. If it is, the pin thesis for today is reinforced. If it is elsewhere, expect drift toward that level in the late afternoon US session.
2. **Recheck intraday call volume distribution** — is the call volume accumulating *at* 7550 (confirming the pin) or *above* 7550 at higher strikes (suggesting GEX migration upward)?
3. **Verify no scheduled macro events** — FOMC, CPI, or other binary events were marked as unknown in this report. Confirm the calendar is clear before applying GEX-pin logic.
4. **Monitor intraday GEX chart for profile rotation** — the GEX chart updates through the session. If the key strike shifts intraday, all levels above are stale.

---

*Report generated from `daily_gex_summary-concise.csv`, `GEX Trading Teaching Points Synopsis.md`, and all 8 source transcripts in the Gex directory.*
