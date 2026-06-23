# SPX GEX Concise Report — 2026-06-22
**Capture time:** 2026-06-22 09:48 (US Eastern)  
**SPX last:** 7521.87  
**Report generated:** 2026-06-22 14:58 local

---

## Section A — Today's Values in Isolation

**Setup:** PIN — GEX Pin / Magnet

| Field | Value | Interpretation |
|-------|-------|----------------|
| last | 7521.87 | SPX price at capture; 21.87 pts above the 7500 key strike |
| sentiment | 57.5% | Mild bullish lean; more than half the window has positive net GEX |
| gex_ratio | 1.26 | Positive signed call/put GEX ratio; call gamma slightly dominant |
| net_gex | 3.14B | Positive net GEX — stabilising / mean-reverting environment |
| key_strike | 7500 | Primary anchor for the day; price is hovering just above it |
| key_absolute | 4.67B | Total absolute GEX at the key strike — high but not extreme |
| key_net | -0.30B | Slight net negative GEX at the key strike (put > call), so the magnet is slightly put-biased |
| key_dominance_pct | 17.17% | About 17% of all window GEX is concentrated at 7500 — meaningful pin |
| key_call_gex | 2.18B | Significant call gamma at 7500 |
| key_put_gex | 2.49B | Slightly larger put gamma at 7500 |
| key_call_oi | 4258 | Call open interest at 7500 |
| key_put_oi | 4853 | Put open interest at 7500 |
| key_net_oi | -595 | Slightly put-heavy OI at the key strike |
| key_call_vol | 9257 | Call volume today at 7500 |
| key_put_vol | 9982 | Put volume today at 7500 |
| key_vol_net | -725 | Intraday put flow slightly dominates at the key strike |
| key2_strike | 7550 | Second-highest GEX strike, 28.13 pts above price |
| key2_absolute | 3.54B | Second GEX cluster is ~76% of the key strike size |
| key2 OI character | Not available | Raw JSON OI breakdown was not retrieved today; assume balanced until verified |
| top OI strike | Not available | Raw JSON OI breakdown was not retrieved today |

**Read of the day in isolation:** A balanced PIN at 7500 with slight put bias. Price is already sitting just above the magnet, so the most attractive short-premium entries are when price stretches a few points away from 7500 and reverts. Net GEX is positive, so this is a stabilising environment rather than an acceleration day.

---

## Section B — Today vs All Prior Rows

- **Sentiment:** 57.5% is neutral-to-bullish versus history. It is not as extreme as the 100% bullish reading on 2026-06-15.
- **Net GEX:** 3.14B positive is firmly in the stabilising camp. It is much less negative than the -20.03B on 2026-06-03 or the -13.14B on 2026-06-05.
- **Key absolute:** 4.67B is moderate. Recent history has ranged from 1.14B to 13.21B; today is mid-range conviction, not a blow-out concentration.
- **Key dominance:** 17.17% is moderate. The 27.83% on 2026-06-18 was a much stronger single-strike outlier.
- **Key net OI:** -595 put-heavy is a shift from yesterday's +1674 call-heavy at the same 7500 strike, but the magnitude is small.
- **Key vol net:** -725 put flow today contrasts with the huge +78,673 call flow on Friday. Volume is relatively balanced today.
- **Key strike vs yesterday:** 7500 remains the key strike, unchanged from Friday's EOD. This is constructive for the pin thesis.
- **Key2 vs key:** 7550 is 3.54B, about 76% of the key's 4.67B. This is a meaningful second pole but not close enough to call it a clean two-strike cluster (within ~20% would be needed). The key strike is the dominant outlier.

**Yesterday's report accuracy:** Friday's EOD data pinned 7500 with 27.83% dominance. SPX closed at 7500.58, almost exactly at the key strike. The magnet thesis worked well into the close. Friday's call volume dominance (+78,673) did not prevent the pin from holding, suggesting much of that flow was likely hedging or spreads rather than directional buying.

---

## Section C — GEX Teaching Point Mapping

**PIN / MAGNET — applies.** 7500 has large balanced call and put GEX (2.18B vs 2.49B) with a near-zero net (-0.30B). Key dominance is 17.17% and key2 is at 7550, not within 20% of the key. This is a single-strike pin rather than a two-strike cluster. Price is already just above the pin, so the best playbook is to wait for a small stretch away from 7500 and sell premium expecting reversion.

**PUT PILLAR — minor qualifier.** Put GEX and put OI at the key strike both slightly exceed call equivalents. The key strike can act as minor support on any dip, but it is not a strong one-sided put pillar because the GEX is fairly balanced.

**CALL WALL — minor qualifier.** Call GEX is slightly smaller than put GEX at the key strike. There is no strong call wall above price today; 7550 is the secondary cluster and could act as a soft ceiling if reached.

**NEGATIVE GAMMA ACCELERATION — not applicable.** Net GEX is +3.14B. No cascade risk below 7500 from negative gamma today.

**GEX SLIDE — not applicable.** Key dominance of 17.17% and a clear second cluster means exposure is not distributed across many strikes.

**POSITIVE GAMMA STABILISING — applies.** Net GEX is positive, sentiment is above 50%, and the key strike is a balanced magnet. Market-maker hedging is likely to dampen moves and create mean reversion around 7500.

**VOLUME DIVERGENCE — minor put-flow confirmation.** Key vol net is -725 (slightly put-heavy), while key net OI is -595 (also slightly put-heavy). They are aligned, so there is no strong divergence signal. Put flow is modestly confirming the slight put bias at the key strike.

**CAPTAIN CONDOR / CONDOR ARTIFACT WARNING — possible.** Balanced call and put OI at 7500 with significant volume could include iron condor or butterfly positioning. OI alone cannot confirm direction, so treat the level as a structural pin, not a directional bet.

**FULL OI STRUCTURE — not available.** The raw JSON OI breakdown could not be retrieved today. The concise CSV shows the top two GEX strikes are 7500 and 7550. Price is sitting just above 7500, so any dip toward 7500 is likely to find a magnet, while an extension toward 7550 may face the secondary cluster. Tomorrow's GEX profile should be checked to confirm whether 7500 remains relevant into the close.

---

## Section D — Educational Trade Logic

Preferred style: **short premium with defined risk**.

**PIN setup → Short Iron Butterfly (primary) or Short Iron Condor (wider, lower credit):**
- Sell the 7500 call and 7500 put, buy 7495/7505 or 7490/7510 wings.
- Price is 21.87 pts above 7500, so this is not a perfect entry zone. Better entry would be a small pullback to 7500–7502 or a further stretch above 7505 with reversion expected.
- Entry timing: wait for price to stretch slightly above 7500 (e.g., 7505–7510) and then sell the butterfly, or wait for a dip to 7495–7500 and sell it.
- Max profit if price pins at 7500 at expiry.
- Zero-risk construction: only attempt if tomorrow's GEX confirms the same 7500 key strike. Today's data supports the pin, but confirmation from tomorrow's profile is required for a zero-risk butterfly.
- Expected credit: moderate, because the wings are narrow. For a 10-pt wide butterfly, credit could be roughly $4–$5 per dollar of width, with max loss equal to width minus credit.
- Hold time: scalp to session hold; take profit quickly if price reverts to the pin.

**PUT PILLAR setup → minor; not the best trade today:**
- Put-side GEX only slightly exceeds call-side at 7500. A short put spread (e.g., sell 7500P / buy 7495P) is viable only on a dip to 7495–7500 with a clear rebound.
- Entry zone: price at or just below 7500.
- Entry timing: wait for a small overshoot below 7500 and enter on reversion.
- Max loss: width minus credit.

**CALL WALL setup → minor; 7550 is the secondary cluster:**
- If price rallies toward 7550 and stalls, a short call spread (e.g., sell 7550C / buy 7560C) could work.
- Entry zone: price at or just above 7550.
- Entry timing: wait for a brief break above 7550 and rejection.
- Max loss: width minus credit.

**NEG_GAMMA / LOW_CONV → no trade.** Not applicable today because net GEX is positive.

---

## Section E — Invalidation Conditions

- **Pin failure:** A decisive break below 7490 or above 7525 with momentum and volume would mean the 7500 magnet has failed. The key2 cluster at 7550 may act as a secondary ceiling, so a break above 7550 would be more significant.
- **Negative gamma cascade:** Not expected today because net GEX is positive. A break below 7490 without support would be a normal range expansion, not a gamma cascade.
- **Level migration:** If intraday volume and OI shift to a different strike (e.g., 7550 becomes the dominant volume strike while 7500 volume fades), the pin is migrating. The concise CSV cannot track this; monitor the live GEX chart.
- **Macro override:** Any unexpected Fed, CPI, or geopolitical headline could override the GEX setup entirely.

---

## Section F — Caution Notes

- **Special day check:** 2026-06-22 is a Monday, not month-end, quarter-end, monthly expiration, triple witching, or FOMC day. No special calendar warning applies unless an unscheduled macro event occurs.
- **Key absolute:** 4.67B is moderate, not extreme. Not an abnormal day by concentration.
- **Tomorrow's GEX:** This is a required check. Tomorrow's profile has not been verified. If tomorrow's key strike is not 7500, the pin may degrade later in the session as market makers reposition. Do not hold a narrow pin trade into the close without checking tomorrow's GEX.
- **Charm / delta decay:** By mid-afternoon US time, hedging flows around 7500 will change from time decay alone, even if price does not move. This can weaken or strengthen the pin.
- **Capture time:** The snapshot was taken at 09:48 US Eastern, relatively early in the session. There is still most of the day for the profile to evolve. The pin thesis is most reliable early in the session but can degrade by the close.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX profile on Option Alpha.** Confirm whether 7500 remains the key strike for the next session.
2. **Confirm intraday call/put volume at 7500.** The CSV shows slightly put-heavy volume, but the live GEX chart should be monitored for migration to 7550 or another level.
3. **Verify the economic calendar.** Confirm no FOMC, CPI, or other binary events today.
4. **Monitor the intraday GEX chart.** Watch for profile rotation during the session, especially after 12:00 PM Eastern.

---

*Note: The full raw-JSON OI breakdown could not be retrieved today due to a script execution issue. Sections relying on key2 OI character and top OI strike are therefore marked as unavailable. The rest of the report is based on the concise CSV and the GEX teaching transcripts.*
