# SPX GEX Concise Report — 2026-06-17 (Mid-Session Update)
**Capture time:** 2026-06-17 10:33 ET
**SPX last:** 7519.28
**Report generated:** 15:34 BST / 10:34 ET
**Previous report:** analysis-concise-20260617-1254.md (pre-market, 07:51 ET)

---

## Yesterday's Report vs What Actually Happened (2026-06-16)

**Yesterday's thesis:** CALL WALL at 7600. OI sandwich: 7500 (floor) to 7600 (ceiling). Expiration week caution active.

**OHLC confirmed:** Open 7548.78 | High 7564.96 | Low 7508.68 | Close 7511.35

**Verdict:** The 7600 call wall was never tested (high only 7564.96). Price sold off and tested the 7500 put pillar floor — low 7508.68, stopping 8.68 pts above 7500. **The floor held.** Price closed at 7511.35, 37 pts below the open. No entry conditions were triggered on either the call wall (never reached 7600) or the put pillar (never reached 7500). The structural framework correctly identified the day's range boundaries; neither became actionable.

---

## What Changed Since This Morning (07:51 → 10:33 ET)

| Metric | 07:51 ET | 10:33 ET | Change |
|--------|----------|----------|--------|
| SPX Last | 7511.35 | 7519.28 | +7.93 pts |
| Sentiment | 45.0% | 47.5% | +2.5% |
| net_gex | +0.08B | +0.91B | +0.83B ✅ |
| key_strike | 7495 | 7495 | unchanged |
| key_absolute | 3.01B | 3.00B | flat |
| key_vol_net | -147 | **-5618** | ⚠️ heavy put flow |
| key_call_vol | 322 | 1725 | +1403 |
| key_put_vol | 469 | 7343 | +6874 |
| key2_absolute | 2.34B | 2.36B | flat |
| Distance price→key | -16 pts | **-24 pts** | price moving away from pin |

**The most important change is key_vol_net: -5618.** This is a significant intraday volume divergence signal requiring specific analysis below.

---

## Section A — Today's Values in Isolation

**Today's row:** `SPX, 2026-06-17 10:33, last=7519.28`

| Field | Value | Interpretation |
|-------|-------|----------------|
| **last** | 7519.28 | +7.93 pts from open. Price has bounced off the pre-market low and is drifting up. 24 pts above key_strike at 7495. |
| **sentiment** | 47.5% | Just below neutral (50%). Marginal bearish lean — barely in the neutral band. Slight improvement from 45% this morning. |
| **gex_ratio** | 1.07 | Mild call GEX dominance in aggregate. Not a strong directional signal. |
| **net_gex** | +0.91B | Now clearly positive (up from +0.08B this morning). Positive gamma regime confirmed — market makers are net stabilising. The inflection risk from this morning has resolved to the upside. |
| **key_strike** | 7495 | Unchanged. Still the primary GEX anchor. Now 24 pts below current price — the pin is pulling from further below. |
| **key_absolute** | 3.00B | Unchanged — 7495 pin strength is stable. |
| **key_net** | -0.04B | Still near-perfectly balanced call/put GEX at 7495. PIN character fully confirmed. |
| **key_dominance_pct** | 11.79% | Slightly lower than morning (12.26%). GEX remains distributed — no single dominant outlier. |
| **key_call_gex** | 1.48B | Nearly unchanged |
| **key_put_gex** | -1.52B | Nearly unchanged |
| **key_call_oi** | 4426 | Unchanged — OI is structural, does not change intraday |
| **key_put_oi** | 4531 | Unchanged |
| **key_net_oi** | -105 | Unchanged — still balanced OI at 7495 |
| **key_call_vol** | 1725 | Growing through the session |
| **key_put_vol** | 7343 | **Heavily elevated** — 4.25:1 put/call volume ratio at 7495 |
| **key_vol_net** | **-5618** | ⚠️ Strong put volume dominance at key_strike. Critical divergence signal — see Section C. |
| **key2_strike** | 7500 | 5 pts from key_strike — still a two-strike cluster |
| **key2_absolute** | 2.36B | 78.7% of key_absolute — two-strike cluster confirmed |

**key2_strike (7500) OI from Step 2B:**
- Call OI 3122 | Put OI 3587 | Total 6709 | Net OI -465
- Character: balanced / mild put lean. Part of the same 7495/7500 pin cluster.

**Top OI strike (from Step 2B):**
- **7495**: 4426 call / 4531 put | Total 8957 | Net OI -105 | Abs GEX 3.002B
- Top OI and key_strike still agree. Distance: -24 pts below current price.

**Full OI structure (top strikes by total OI):**

| Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX | Character | Distance |
|--------|---------|--------|----------|--------|---------|-----------|----------|
| 7495 | 4426 | 4531 | 8,957 | -105 | 3.002B | **PIN (balanced)** | -24 |
| 7600 | 5426 | 2441 | 7,867 | +2985 | 1.152B | CALL WALL | +81 |
| 7500 | 3122 | 3587 | 6,709 | -465 | 2.357B | Balanced/mild put | -19 |
| 7525 | 709 | 2069 | 2,778 | -1360 | 1.115B | PUT PILLAR (mild) | +6 |

**Updated OI sandwich:** Structural ceiling 7600 (+81 pts), structural floor 7495/7500 cluster (-19 to -24 pts). Price at 7519 is 6 pts above 7525 — which now appears as a mild put pillar just below current price.

---

## Section B — Today vs All Prior Rows

**net_gex (+0.91B):** The morning's near-zero concern has resolved. +0.91B is still the lowest positive reading in the dataset (all other positive days were above +2.36B), but it is now clearly in stabilising territory. Not comparable to the extreme +20.99B on Jun 15 — but the neutral inflection risk is gone.

**sentiment (47.5%):** Still below neutral but recovering. Jun 3 and Jun 8 had 30–32.5% and were the worst days in the dataset. Today's 47.5% is near-neutral — not a bearish alarm.

**key_vol_net (-5618):** This is by far the largest divergence between key_vol_net and key_net_oi (+105 vs -5618 offset from zero) in the dataset. All prior days had vol_net and net_oi broadly aligned. This is a new signal type — analysed fully in Section C.

**Price vs key_strike distance:** Price has drifted from 16 pts above the pin (morning) to 24 pts above. The pin is not pulling price back toward it so far — the morning bounce has carried price away from 7495. This reduces the probability of an immediate touch at 7495 but increases the probability of a future retest.

---

## Section C — GEX Teaching Point Mapping

### ✅ PIN / MAGNET at 7495–7500 — Still Primary Setup

- OI structure unchanged: 4426/4531 at 7495, balanced to within 1%. Classic pin.
- net_gex now +0.91B — positive gamma stabilising backdrop now supports the pin thesis more than this morning.
- Two-strike cluster (7495/7500, 78.7% ratio) still applies — treat as a zone, not a single point.
- Per the transcripts: the pin acts as a gravitational centre. Price has moved away this morning but the structural force persists as long as the key_strike remains 7495.

### ⚠️ VOLUME DIVERGENCE — Critical New Signal

**The signal:** key_vol_net = -5618. key_put_vol = 7343 vs key_call_vol = 1725. That is a 4.25:1 put/call volume ratio at 7495.

**What this means per the transcripts:**
Per the Jack Slocum and Kirk transcript material on volume divergence: "key_vol_net is opposite in sign to key_net_oi... this may indicate the intraday GEX anchor is drifting, not just a sentiment signal."

Three possible interpretations, ranked by probability:

1. **Put buying as protection at the pin (most likely):** Traders who are long SPX above 7495 are buying 7495 puts as hedges as the day progresses. This is flow *into* the pin from buyers who see 7495 as a floor — it actually reinforces the pin level's significance, not undermines it. The large put volume does not necessarily mean directional selling.

2. **Short put positioning at 7495 (second):** Options sellers establishing short put positions at 7495, collecting premium on the pin level. Short put sellers appear in the volume as put "buyers" from the market maker perspective. This also reinforces the pin.

3. **Directional put buying ahead of a breakdown (less likely given net_gex +0.91B):** If traders were anticipating a break below 7495, they would buy 7495 puts for downside exposure. However, with net_gex now +0.91B (stabilising), a breakdown through the pin is less likely than this morning.

**Key conclusion:** The volume divergence is notable and must be watched. It does not by itself invalidate the pin thesis — it may reflect protective hedging *around* the pin. However, if price breaks below 7495 with this put volume already accumulated, the move could be faster than usual as those put holders achieve maximum delta and stop providing support.

**Monitor:** If mid-session GEX refresh shows key_vol_net deepening further negative (e.g., beyond -10,000) while price approaches 7495, treat this as a warning that the pin may be contested.

### ✅ POSITIVE GAMMA STABILISING (net_gex +0.91B)

net_gex has recovered from the morning's near-zero reading. Positive gamma now confirmed. Market maker hedging is net dampening — mean-reverting behaviour expected around the 7495/7500 zone. The morning inflection risk has passed.

### ✅ CAPTAIN CONDOR WARNING (unchanged)

Balanced OI at 7495 (4426/4531) is consistent with condor positioning. The 7343 put volume may include condor leg adjustments or rolls, not purely directional flow. OI alone cannot confirm direction.

### ❌ NOT: NEGATIVE GAMMA ACCELERATION
net_gex +0.91B. Resolved from morning.

---

## Section D — Educational Trade Logic

### Primary: SHORT IRON BUTTERFLY centred at 7495–7500 (unchanged)

The pin setup remains valid. The volume divergence adds caution but does not invalidate.

**Current price 7519 — 24 pts above the pin zone:**
- Price has drifted away from the entry zone (within 10 pts of 7495–7500).
- The morning entry opportunity (price at 7511, 11–16 pts above) has passed without a touch.
- **Wait for a pullback to 7495–7510 before entering.** Do not chase the pin by entering 24 pts away from centre.

**If price pulls back to 7500–7510:**
- Sell 7495C + Sell 7500P / Buy 7515C + Buy 7480P (or equivalent)
- Entry within 10 pts of the cluster is required for reasonable iron butterfly credit
- Exit at 50% credit profit or if 7480 or 7520 is breached with momentum

**Zero-risk construction — still requires tomorrow's GEX confirmation.**

### What NOT to trade:

- **Do not sell a short call spread at 7600** — 81 pts OTM, no actionable entry today.
- **Do not sell directional puts on the volume divergence** — the put volume at 7495 is not a confirmed directional breakdown signal while net_gex is positive.
- **Do not enter the iron butterfly now** (price 7519) — wait for a pullback to within 10 pts of the pin zone.

---

## Section E — Invalidation Conditions

### PIN at 7495–7500:

- **Upside invalidation:** Price breaks above 7535–7540 with sustained momentum. The mild put pillar at 7525 (net OI -1360) provides the first friction zone above current price. A break above 7540 would suggest the pin is not pulling price back and the day's character has changed — the 7550 zone and ultimately 7600 call wall become relevant.

- **Downside invalidation:** Price breaks below 7485 with momentum. Given the heavy put volume already accumulated at 7495 (7343 puts), a break below the pin could see those put holders achieve full delta — market makers who sold those puts would need to sell futures aggressively, potentially accelerating the move toward 7450 and 7425.

- **Volume divergence escalation:** If key_put_vol exceeds 15,000 by mid-afternoon while price sits below 7495, treat the pin as failing — the accumulated put positions become a source of selling pressure rather than support.

- **net_gex turning negative intraday:** If a mid-session refresh shows net_gex below zero, exit all iron butterfly positions immediately.

---

## Section F — Caution Notes

**⚠️ EXPIRATION WEEK — WEDNESDAY, THREE DAYS TO JUNE MONTHLY:**
Today is Wednesday June 17. June monthly expiration is Friday June 20. Per the transcripts, GEX reliability degrades from Wednesday onward in expiration week as positions roll and the gamma profile shifts toward next week's strikes. **Today is the last day with reasonable GEX reliability this week. Consider not trading new 0DTE positions Thursday and Friday.**

**⚠️ VOLUME DIVERGENCE REQUIRES MONITORING:**
The -5618 key_vol_net is the most significant intraday warning in the current dataset. While the pin thesis remains intact, the put accumulation at 7495 must be tracked through the afternoon. Re-run `optionalpha_daily.py` at 12:00–13:00 ET for an updated reading.

**⚠️ TOMORROW'S GEX — NOT CHECKED (REQUIRED):**
Tomorrow's GEX profile has not been checked. With expiration on Friday, tomorrow (Thursday June 18) will show significant position rotation. The 7495/7500 pin may not persist into Thursday — check Option Alpha before any end-of-session iron butterfly hold.

**Charm / delta decay:**
Capture at 10:33 ET — approximately 3 hours into the session, 3.75 hours remain. Charm effects are building — the heaviest decay period is 13:00–15:00 ET (approximately 18:00–20:00 BST). The 7495/7500 balanced OI will decay symmetrically, but the heavy put volume skew (4.25:1) means the put-side charm decay may slightly favour call-side dominance in the afternoon.

**Capture time = 10:33 ET (mid-morning):** Active session. Recommend next refresh at 12:00–13:00 ET once mid-session positioning is complete.

---

## Section G — Required Actions Before Trading

1. **Monitor key_vol_net at 7495 through the session.** If put volume continues building rapidly (from -5618 toward -10,000+) while price approaches 7495, treat the pin as contested and reduce size.

2. **Wait for price to return within 10 pts of 7495–7500 before entering the iron butterfly.** Price at 7519 is currently too far from centre for a good entry. Entry at 7500–7510 is required.

3. **Check tomorrow's GEX on Option Alpha.** Thursday is one day before June monthly expiration — tomorrow's key_strike is critical before any hold-to-expiry plan.

4. **Re-run `optionalpha_daily.py` + `optionalpha_daily-summary.py` at 12:00–13:00 ET** for a mid-session update. The volume divergence needs a second reading to determine if it is growing or stabilising.

5. **Stop new 0DTE entries from Thursday morning.** Today (Wednesday) is the last reliable GEX day this expiration week per the transcripts.

---

*Report generated: 2026-06-17 15:34 BST / 10:34 ET*
*Previous report: analysis-concise-20260617-1254.md*
