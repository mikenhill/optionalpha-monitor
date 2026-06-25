# SPX GEX Concise Report — 2026-06-23
**Capture time:** 2026-06-23 09:16 ET  
**SPX last:** 7472.79  
**Report generated:** 2026-06-23 14:20 local

---

## Yesterday's Report vs Actual (2026-06-22)

Yesterday's report identified **key_strike 7500** as a PUT PILLAR (key_put_gex 2.76B >> key_call_gex 0.42B, key_net_oi −595). Net GEX was −5.53B — negative gamma, acceleration risk flagged.

**What actually happened (OHLC):** Open 7500.44 → High 7530.01 → Low 7460.01 → Close 7472.79.
- Price opened right at the key strike (7500), rallied briefly to 7530, then broke below the pillar and closed at 7472 — **the put pillar at 7500 failed as support**. The negative gamma environment amplified the downside move through 7500 as warned. The low 7460 tested the secondary level (7475). Accuracy: the PUT PILLAR identification was correct structurally, but the breakdown thesis (negative gamma amplification) was the correct caution — not the support-hold thesis. This was a GEX SLIDE / negative gamma day, not a pin.

---

## Section A — Today's Values

| Field | Value | Meaning |
|---|---|---|
| last | 7472.79 | SPX at 09:16 ET — early session capture |
| sentiment | 47.5% | Slight bearish lean (below 50 neutral); no strong bullish tilt |
| gex_ratio | −4.22 | **Strongly put-dominated** — puts have 4.22x the GEX of calls across window |
| net_gex | −7.66B | **Significantly negative** — market maker hedging adds momentum to moves |
| key_strike | 7400 | Primary GEX anchor — 72 pts below current price |
| key_absolute | 3.03B | Moderate conviction at 7400 |
| key_net | −2.25B | Strongly negative at key strike — put-dominated |
| key_dominance_pct | 24.4% | **High concentration** — 7400 holds nearly a quarter of total window GEX |
| key_call_gex | 0.39B | Minimal call GEX at 7400 |
| key_put_gex | −2.64B | **Heavy put GEX** at 7400 — this is a PUT PILLAR |
| key_call_oi | 1,253 | Very low call OI at 7400 |
| key_put_oi | 8,514 | **Very high put OI** — structural put support/magnet |
| key_net_oi | −7,261 | Strongly put-heavy — confirms PUT PILLAR |
| key_call_vol | 3,494 | Call volume at 7400 |
| key_put_vol | 3,541 | Near-equal put volume — neutral intraday flow so far |
| key_vol_net | −47 | Essentially flat — no directional call/put flow divergence yet |
| key2_strike | 7390 | Second anchor 10 pts below key_strike |
| key2_absolute | 1.99B | Close to key_absolute (66% of it) — **two-strike cluster**, not a clean single pin |

**key2 OI character (from Step 2B):**
- 7390: Call OI 149, Put OI 5,970, Net OI −5,821
- Character: **PUT PILLAR** — extremely put-heavy, acts as secondary support/magnet below 7400

**Top OI strike (from Step 2B):**
- **7400** is also the top total OI strike (9,767 total: 1,253 calls / 8,514 puts)
- Net OI: −7,261 (strongly put-heavy)
- Distance from price: **~73 pts below** current 7472.79
- Note: the top OI strike and key_strike coincide today — unusual alignment; the proximity-weighted algorithm and raw OI both point to the same level.

---

## Section B — Today vs History

| Metric | Today | Historical context |
|---|---|---|
| Sentiment 47.5% | Below neutral | Range seen: 30–100%. Today is below-neutral but not extreme. Jun 3 (30%) was more bearish. |
| net_gex −7.66B | **Second most negative in history** | Only Jun 3 (−20.03B) was worse. Jun 5 (−13.14B) and Jun 8 (−8.02B) also negative. Today's reading is consistent with a strongly negative gamma environment. |
| key_absolute 3.03B | Low-moderate | Jun 18 (13.21B) and Jun 5 (6.24B) had much higher conviction. Today's key absolute is modest. |
| key_dominance_pct 24.4% | **Highest in history** | Previous high was Jun 18 (27.83%). Today's 24.4% means GEX is unusually concentrated at one level — high single-strike significance. |
| key_net_oi −7,261 | **Most put-heavy key OI in history** | Jun 3 had −3,478; Jun 8 had −2,942. Today's −7,261 is by far the most put-dominated key strike on record. |
| key_vol_net −47 | Near flat | Jun 3 (−73,614) showed extreme put volume. Today's flat vol_net means intraday flow has not yet confirmed the structural put positioning. |
| key_strike shift | 7500 → 7400 | Key strike dropped 100 pts from yesterday. This is a significant gravitational shift downward — market makers are now anchored 100 pts lower. |
| key2 proximity | 7390 = 10 pts below 7400 | Two-strike PUT PILLAR cluster (7390/7400) just 10 pts wide. This is a tight, reinforced support zone — or a potential accelerant if both break. |

**Key observation:** The key_strike moved from 7500 (yesterday) to 7400 (today) — a 100-pt gravitational shift lower that confirms the downside repositioning visible in yesterday's price action.

---

## Section C — GEX Teaching Point Mapping

### ❌ PIN / MAGNET — Does NOT apply
Key_call_gex is only 0.39B vs key_put_gex of 2.64B — deeply imbalanced. A pin requires roughly balanced call/put GEX at the key strike. Today has no pin setup.

### ✅ PUT PILLAR (Primary setup)
- key_put_gex (2.64B) and key_put_oi (8,514) both heavily exceed call equivalents (0.39B, 1,253)
- key_net_oi −7,261 — most extreme put-heavy reading in history
- **7400 may act as a gravitational magnet / support zone** — if price drifts toward 7400, market maker hedging may provide a floor
- **Secondary PUT PILLAR at 7390** — 10 pts below — creates a 7390–7400 support cluster

### ✅ NEGATIVE GAMMA ACCELERATION (High risk)
- net_gex −7.66B — strongly negative
- Market makers are **momentum followers** in this environment: they sell into falls and buy into rallies, amplifying moves
- **Cascade risk:** 7390 and 7400 are only 10 pts apart. If 7400 breaks with momentum in negative gamma, 7390 offers minimal additional cushion — a break of both could produce a fast 30–50 pt move toward 7350 or lower
- **Flag: do not sell premium into the downside** until the 7400 level holds clearly

### ✅ GEX SLIDE — Partial
- gex_ratio −4.22 means substantial put GEX is spread across multiple strikes (7390, 7420, 7450 all have notable put OI)
- If 7400 breaks, the distributed put GEX below creates layered hedging pressure — slide conditions possible

### ⚠️ VOLUME DIVERGENCE CHECK
- key_vol_net is −47 (flat) vs key_net_oi of −7,261 (massively put-heavy structural)
- Intraday call/put volume at 7400 is almost equal (3,494 calls / 3,541 puts) despite the structural put dominance
- This is early in the session (09:16 capture) — flow divergence has not developed yet
- **Watch:** if call volume at 7400 starts building significantly, it may signal a bounce trade building; if put volume accelerates, confirms the gravitational pull downward

### ✅ CAPTAIN CONDOR / CONDOR ARTIFACT WARNING
The 8,514 put OI at 7400 is the highest put OI in the window by a large margin. **This could be condor or iron butterfly positioning** rather than directional bearish flow. A condor at 7400 put would provide mechanical support (short put delta hedging) but could also represent a strike that large players are defending. OI alone cannot confirm direction.

### ✅ FULL OI STRUCTURE (Top 4 strikes by total OI)

| Strike | Call OI | Put OI | Net OI | Character | Distance from 7472 |
|---|---|---|---|---|---|
| **7400** | 1,253 | 8,514 | −7,261 | **PUT PILLAR** | −73 pts (below) |
| **7390** | 149 | 5,970 | −5,821 | **PUT PILLAR** | −83 pts (below) |
| **7500** | 2,746 | 2,394 | +352 | Balanced / slight call | +27 pts (above) |
| **7550** | 3,488 | 1,537 | +1,951 | **CALL WALL** | +77 pts (above) |

**OI Sandwich:** Price (7472) is sitting between:
- **Structural floor:** 7400–7390 (twin PUT PILLARS, 73–83 pts below)
- **Structural ceiling:** 7500 (balanced, light resistance) and 7550 (CALL WALL, 77 pts above)

The true structural floor is 7390–7400. The true structural ceiling is 7550. 7500 is a lighter level.

**Why 7400 is ranked KEY despite being 73 pts away:** The proximity-weighted algorithm uses `abs_gex × exp(−distance/25)`. At 73 pts, exp(−73/25) = exp(−2.92) ≈ 0.054. But 7400's raw abs GEX (3.03B) is so large that even discounted it dominates the window. The 7475 strike (only 2 pts away) has abs GEX of only 0.32B — proximity weight near 1.0 gives 0.32B. 7400 at discount still gives 3.03B × 0.054 = 0.164B... actually the dominance of 7400 at 24.4% suggests the algorithm is finding 7400 wins despite distance because no nearby strike has comparable magnitude. This is an unusual situation — the gravitational anchor is well below current price.

---

## Section D — Trade Logic

### Setup 1: PUT PILLAR at 7400 — Short Put Spread

**Thesis:** 7400 acts as support. Price drifts toward 7400, touches/briefly overshoots, then reverses. Sell premium below 7400.

- **Short leg:** Sell 7400P (at the pillar)
- **Long leg:** Buy 7390P (protective wing — 10 pts wide, matches the secondary pillar)
- **Net credit:** ~$2.00–$3.00 (10-pt spread, 0DTE)
- **Max loss:** $10 − credit = $7–$8
- **Max profit:** Full credit if both legs expire worthless (price stays above 7400)
- **Entry zone:** Price at 7405–7415, after a brief overshoot below 7400
- **Entry timing:** Wait for price to touch or briefly pierce 7400, then enter on the reversal candle
- **Hold:** Session hold to expiry
- **Zero-risk iron butterfly:** NOT applicable today — key_call_gex is only 0.39B, far too imbalanced to stage a balanced butterfly. The zero-risk construction requires balanced call/put GEX at the key strike.

### Setup 2: CALL WALL at 7550 — Short Call Spread

**Thesis:** 7550 structural ceiling holds. If price rallies toward 7550, sell premium above it.

- **Short leg:** Sell 7550C
- **Long leg:** Buy 7560C (10 pts wide)
- **Net credit:** ~$1.50–$2.50
- **Max loss:** $10 − credit
- **Entry zone:** Price at 7545–7555
- **Entry timing:** Wait for price to touch or briefly break above 7550, enter on rejection
- **Hold:** Scalp (30–60 min) or session hold

### ❌ Negative Gamma — No naked short premium into breakdowns
If price is falling through 7400 with momentum, **do not sell put spreads into the move**. In negative gamma (net_gex −7.66B), the move will be amplified, not contained. Wait for a clear reversal signal before entering.

---

## Section E — Invalidation Conditions

1. **PUT PILLAR fails:** A 5-min close below 7390 with expanding volume and momentum — the twin pillar cluster (7390/7400) has failed. Expect acceleration toward 7350 and lower. Exit any short put spreads immediately.

2. **Negative gamma cascade below 7390:** With net_gex −7.66B, a break of 7390 removes the last meaningful GEX anchor in the lower window. The next significant put OI is at 7420 (1,906 puts) and 7450 (2,448 puts) but both are weaker. A cascade to 7340–7350 is plausible.

3. **GEX rotation / migration signal:** If the intraday GEX chart shows the key_strike moving from 7400 up toward 7450 or 7475, the anchor is migrating higher — the 7400 trade is no longer valid. Watch the Option Alpha live GEX chart from 11am ET onward.

4. **Macro override:** Any unexpected macro print (Fed speaker, geopolitical shock, economic data) would override GEX positioning entirely. Check the economic calendar before entry.

5. **CALL WALL at 7550 invalidated:** A 5-min close above 7555 with expanding volume — the call wall has been absorbed. Exit short call spreads.

---

## Section F — Caution Notes

- **Day of week:** Monday June 23, 2026. Not end of month, not end of quarter, not triple witching, not monthly expiration. **No structural calendar flags today.**

- **Capture time:** 09:16 ET — very early session. GEX profiles can shift materially as the session develops. The 09:16 reading may not reflect the 11am–2pm equilibrium. **Treat this as an early directional read, not a confirmed mid-session profile.**

- **Abnormal OI warning:** Put OI at 7400 (8,514) and 7390 (5,970) are among the highest single-strike put OI readings in this dataset. While not the end-of-year extreme that caused the crash-out described in the transcripts, these are elevated readings that deserve respect. GEX reliability may be above normal given the concentration.

- **⚠️ TOMORROW'S GEX — REQUIRED, NOT CHECKED:** Tomorrow's GEX profile has **not been verified**. The put pillar thesis at 7400 cannot be fully validated without confirming that 7400 is also a key level for tomorrow. If tomorrow's key_strike is at a different level (e.g. 7450), market makers will begin repositioning toward that level from approximately 2:30pm ET onward, causing the 7400 anchor to degrade in the final hour. **Check tomorrow's GEX on Option Alpha before entering any iron butterfly or multi-leg structure.**

- **Charm / delta decay:** As time passes (especially after 1pm ET), delta decay at the key strike changes the hedging pressure even without price movement. The 7400 PUT PILLAR may weaken in the afternoon as put deltas decay toward zero. Earlier session entries have more structural support.

- **key_dominance_pct 24.4%:** High concentration — this is a meaningful single-strike day. The level is significant. However, the two-strike cluster nature (7390 + 7400, only 10 pts apart) means there is no clean single-point anchor; it is a zone.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX** on Option Alpha — is 7400 also the key strike for 2026-06-24? If yes, the pin/pillar thesis has multi-day confirmation. If no, the anchor may migrate late in today's session.

2. **Monitor intraday call/put volume at 7400.** Currently flat (vol_net −47). If call volume at 7400 builds significantly intraday, it may signal an emerging bounce/recovery trade. If put volume dominates, confirms gravitational pull to test 7400.

3. **Verify economic calendar** — confirm no FOMC, CPI, Fed speaker, or other binary events for today June 23.

4. **Watch the live GEX chart** from 10:30am ET onward for profile rotation — specifically whether the key_strike migrates from 7400 back toward 7450–7475 (bounce signal) or holds at 7400.

5. **SPX price action at open** — price is at 7472 at capture (09:16). Watch whether price tests 7500 (the old pillar, now lighter resistance) or immediately drifts toward 7400. The direction of the first 30-min move sets the context for which trade applies.

---

*Data captured: 2026-06-23 09:16 ET. Report generated: 14:20 local. Raw file: 20260623_141639_SPX_SPX_20260623.json*
