# SPX GEX Report — Tuesday 9 June 2026 (Updated Capture)
**Capture time:** 14:31 UK / 09:31 US Eastern  
**Script:** `optionalpha_daily-summary.py` | **Source row:** `daily_gex_summary-concise.csv`  
**Note:** This supersedes the 13:12 report. Price has moved 44 pts since the earlier capture.

---

## Yesterday's Accuracy Review — Monday 8 June 2026

**Yesterday's setup classified as: PUT_PILLAR at 7450 in strongly negative gamma (-8.02B)**

Yesterday's report would have predicted 7450 as put-heavy support with significant downside risk given the dominant negative net GEX and key_net_oi = -2,942.

**What actually happened (OHLC from CSV):**
- Open: 7440.57 | High: 7466.81 | Low: 7395.13 | Close: 7405.73
- The 7450 key strike was never reclaimed — price opened below it at 7440 and declined through the session to close at 7405.73.
- The low of 7395.13 represented a 55pt breach below 7450. The PUT_PILLAR did not hold.
- The -8.02B net GEX was the most extreme in the dataset; negative gamma acceleration was the dominant force, amplifying the decline.
- **Accuracy verdict:** The directional bias (put-heavy, downside risk) was correct. However, the put pillar at 7450 gave false hope of support — a trader using it as a hard floor was badly positioned. The lesson confirmed by the transcripts: in strongly negative net GEX regimes, put pillars are unreliable as support. Negative gamma cascade risk should be the primary thesis, not the pillar.
- **Today's context:** Price has now recovered 44 pts from this morning's open (7405.73 → 7449.76), effectively reclaiming the 7450 level that failed yesterday. This is a significant intraday reversal.

---

## Section A — Today's Values in Isolation

| Field | Value | Interpretation |
|-------|-------|----------------|
| `last` | **7449.76** | SPX price at 14:31 UK / 09:31 ET — 90 mins into the US session |
| `sentiment` | **55.0** | 55% of strikes have net positive GEX — at the bullish threshold (>55% = bullish lean) |
| `gex_ratio` | **-1.04** | Barely put-dominated; call and put GEX are near-balanced across the window |
| `net_gex` | **-0.49B** | Total signed GEX is slightly negative — near-neutral; barely in acceleration territory |
| `key_strike` | **7450** | Primary GEX anchor — price is sitting essentially on the key strike (0.24 pts below) |
| `key_absolute` | **2.58B** | Total GEX magnitude at 7450 — moderate-to-solid conviction |
| `key_net` | **+0.19B** | Signed net at key strike is slightly call-positive — mild call wall character at 7450 |
| `key_dominance_pct` | **10.22%** | Key strike holds ~10% of total window GEX — low-moderate concentration |
| `key_call_gex` | **+1.39B** | Call GEX at 7450 — meaningful call presence |
| `key_put_gex` | **-1.20B** | Put GEX at 7450 — meaningful put presence; closely matched with calls |
| `key_call_oi` | **2,693** | Call open interest at 7450 |
| `key_put_oi` | **2,320** | Put open interest at 7450 |
| `key_net_oi` | **+373** | Call OI marginally exceeds put OI — mildly call-heavy structural positioning |
| `key_call_vol` | **4,069** | Strong call volume at 7450 — more than yesterday's 3,083 |
| `key_put_vol` | **805** | Low put volume at 7450 |
| `key_vol_net` | **+3,264** | Heavy call volume dominance at the key strike — intraday flow strongly confirms call side |
| `key2_strike` | **7460** | Second GEX anchor — only 10 pts above key strike |
| `key2_absolute` | **1.39B** | 54% of key_absolute (1.39 / 2.58) — significant two-strike cluster |
| **key2 OI** | call 1,494 / put 1,341 / net **+153** | *(raw JSON)* Balanced OI at 7460 — mild call lean; neither strong wall nor pillar |
| **Top OI strike** | **7500** — call 7,315 / put 992 / total **8,307** / net **+6,323** | *(raw JSON)* Highest OI in window; massively call-heavy; 50 pts above current price — major structural call ceiling |

---

## Section B — Today vs All Prior Rows

**Full history:**

| Date | last | sentiment | net_gex | key_strike | key_absolute | key_dom% | key_net_oi | key_vol_net |
|------|------|-----------|---------|------------|--------------|----------|------------|-------------|
| 02-Jun | 7595.78 | 50.0 | +2.36B | 7600 | 6.52B | 14.91% | +487 | +17906 |
| 03-Jun | 7560.13 | 30.0 | -20.03B | 7550 | 3.94B | 10.13% | -3,478 | -73614 |
| 04-Jun | 7553.68 | 32.5 | -2.63B | 7550 | 1.14B | 12.17% | -311 | +1901 |
| 05-Jun | 7584.31 | 55.0 | -13.14B | 7550 | 6.24B | 12.27% | -1,808 | +954 |
| 08-Jun | 7438.95 | 32.5 | -8.02B | 7450 | 3.20B | 10.26% | -2,942 | +6206 |
| **09-Jun 13:12** | 7405.73 | 35.0 | -2.70B | 7450 | 2.38B | 9.88% | +373 | +2579 |
| **09-Jun 14:31** | **7449.76** | **55.0** | **-0.49B** | **7450** | **2.58B** | **10.22%** | **+373** | **+3264** |

**Comparative observations:**

- **Sentiment (55.0):** Jumped from 35.0 (this morning) to 55.0 — matching 02-Jun and 05-Jun, the only two prior bullish-lean days. A material intraday shift, consistent with the 44pt price recovery.
- **net_gex (-0.49B):** The least negative in the entire dataset by a wide margin. Effectively neutral — this is the closest the market has come to positive gamma territory since 02-Jun. The persistent negative gamma regime of the past four sessions is dissipating.
- **key_absolute (2.58B):** Modestly higher than this morning's 2.38B. Still well below the high-conviction days (02-Jun 6.52B, 05-Jun 6.24B) but solid for the current environment.
- **key_dominance_pct (10.22%):** Marginally higher than this morning — still distributed, but 7450 has slightly more relative weight now.
- **key_net_oi (+373):** Unchanged — OI is a slow-moving structural input; intraday volume is the faster signal.
- **key_vol_net (+3,264):** Increased from +2,579 this morning, confirming continued call volume accumulation at 7450 through the session. This is the highest call-dominant vol_net reading at a key strike since 02-Jun's +17,906.
- **key_strike (7450):** Unchanged for a third session and price is now sitting on it — this is a meaningful pin candidate for the first time since the report began.
- **key2_strike shifted from 7400 → 7460:** This is the most important change since the 13:12 report. The second anchor has moved from 5 pts below to 10 pts above the key strike. The OI sandwich that trapped price this morning (floor at 7400, ceiling at 7450) has partially resolved — price has risen through 7400 and is now between 7450 and 7460.

---

## Section C — GEX Teaching Point Mapping

### Full OI Structure — three levels

| Strike | Call OI | Put OI | Total OI | Net OI | Character | Distance |
|--------|---------|--------|----------|--------|-----------|----------|
| **7500** | 7,315 | 992 | **8,307** | +6,323 | Major CALL CEILING | +50 pts above |
| **7460** | 1,494 | 1,341 | 2,835 | +153 | Balanced (key2) | +10 pts above |
| *7449.76* | — | — | — | — | *current price* | — |
| **7450** | 2,693 | 2,320 | 5,013 | +373 | Mild CALL WALL (key) | at price |
| **7400** | 1,067 | 3,501 | 4,568 | -2,434 | PUT PILLAR | -50 pts below |

**Key structural shift from this morning:** The OI sandwich has changed character. This morning price was 5 pts above the 7400 PUT PILLAR with 7450 as the ceiling. Now price has risen to 7450 (the former ceiling) and the relevant nearby anchors are 7450 (at price) and 7460 (10 pts above). The 7400 PUT PILLAR is now 50 pts below — a potential support level on any pullback but no longer an immediate constraint. The 7500 CALL CEILING remains 50 pts above.

**Proximity-weighted GEX — why 7450 is KEY (trivially):**
With last = 7449.76, the distance to 7450 is just 0.24 pts. Decay = exp(−0.5 × (0.24/50)²) = 1.000. 7450 is essentially unpenalised by distance — it wins on raw GEX alone (2.58B) by a significant margin over the next contenders.

| Strike | Raw GEX | Dist | Decay | Weighted GEX | Rank |
|--------|---------|------|-------|--------------|------|
| **7450** | 2.5831B | 0.2 | 1.000 | **2.583B** | **KEY** |
| **7460** | 1.3886B | 10.2 | 0.979 | **1.360B** | KEY2 |
| 7425 | 1.3954B | 24.8 | 0.885 | 1.234B | 3 |
| 7500 | 1.6474B | 50.2 | 0.604 | 0.994B | 5 |
| 7400 | 1.4339B | 49.8 | 0.609 | 0.874B | 8 |

Note: 7500 has the highest raw OI (8,307) and raw GEX (1.647B) in the window after 7450, but drops to rank 5 weighted because it is 50 pts from price (40% discount). 7400 drops to rank 8 despite being a significant level.

---

### ✅ PIN / MAGNET — Qualifies (weakly)

- `key_call_gex = +1.39B`, `key_put_gex = -1.20B` — ratio 54%/46%, close to balanced.
- `key_net = +0.19B` — very close to zero, the lightest directional lean in the dataset.
- Price is sitting 0.24 pts below 7450 — essentially at the key strike.
- `key_dominance_pct = 10.22%` — still low, but the key strike is exactly at price, which strengthens the pin thesis.
- `key2_absolute / key_absolute = 54%` — **TWO-STRIKE CLUSTER confirmed.** 7460 at 1.39B is 54% of 7450's 2.58B. This is not a clean single-point pin; price may oscillate between 7450 and 7460 as much as pin to a single level.
- **Verdict:** The PIN / MAGNET setup is the primary classification for this capture. The conditions are better than any prior session in the dataset — price at key strike, near-balanced GEX, neutral net GEX. However the two-strike cluster (7450/7460, only 10 pts apart) means a clean iron butterfly at 7450 may see price drift to 7460 without the trade failing — this should be factored into wing width.

### ⚠️ CALL WALL — Mild, at key strike
- `key_net_oi = +373` and `key_vol_net = +3,264` both call-positive.
- 7500 at net_oi +6,323 is the major structural call ceiling 50 pts above.
- If the pin at 7450 breaks upward, 7460 (10 pts, balanced) offers little resistance, and the next meaningful level is 7500. Any rally through 7460 with momentum targets 7500.

### ✅ POSITIVE GAMMA STABILISING — Newly applicable
- `net_gex = -0.49B` — the least negative in the entire dataset; near-neutral.
- `sentiment = 55.0` — at the bullish threshold.
- Per Matt Cashman (interview) and the transcripts: near-zero net GEX means market maker hedging is dampened. Moves are less likely to be self-reinforcing in either direction. This is a mean-reversion environment — the pin thesis is strengthened by this.
- **This is the first session where positive gamma stabilisation is a viable classification.** The four-session negative gamma streak is effectively over for today.

### ❌ NEGATIVE GAMMA ACCELERATION — No longer dominant
- `net_gex = -0.49B` — well within the noise band of neutral. Cascade risk is minimal at this level.
- Not applicable for today's primary analysis.

### ⚠️ GEX SLIDE — Low-level concern
- `key_dominance_pct = 10.22%` — GEX remains distributed. No single dominant outlier.
- However, price at the key strike partially offsets this — the GEX concentration that matters is the one price is touching.

### ❌ VOLUME DIVERGENCE — Absent
- `key_vol_net = +3,264` is the same direction as `key_net_oi = +373` (both call-positive).
- No migration signal. Call flow is confirming structural OI positioning.

### ⚠️ CAPTAIN CONDOR / CONDOR ARTIFACT WARNING
- `key_call_oi = 2,693` / `key_put_oi = 2,320` at 7450 — near-balanced OI.
- Per Matt Cashman (interview): balanced OI at a single strike may reflect iron butterfly or condor positioning rather than directional flow. OI alone cannot confirm the direction of intent.
- However, `key_vol_net = +3,264` (call volume 5× put volume today) is the more actionable signal — the intraday flow is clearly call-biased at 7450.

---

## Section D — Educational Trade Logic

### Primary setup: PIN at 7450 → Short Iron Butterfly

**The conditions today are the closest to a clean PIN setup in this dataset.** Price is at the key strike, net GEX is near-neutral, and the GEX balance at 7450 is 54%/46% call/put.

**Short Iron Butterfly:**
- Sell the **7450C** and **7450P** (ATM straddle at key strike)
- Buy the **7470C** and **7430P** as wings (20-pt wings)
- Net credit collected upfront; max profit if price pins exactly at 7450 at expiry
- Max loss: wing width minus credit (20 – credit; always defined, capped)
- Entry zone: price within 5 pts of 7450 — **currently met** (price = 7449.76)
- Entry timing: per the transcripts (Jack Slocum), wait for a slight stretch away from 7450 and enter on the reversion back — do not enter at the exact top or bottom

**Two-strike cluster adjustment:** With 7460 as key2 (54% of key, 10 pts above), consider shifting the call wing to 7480 (wider) or accepting that the call side of the butterfly may be tested. A 7430P/7450C/7470C with a bought 7430P wing is more conservative than going symmetric at ±20.

**Zero-risk iron butterfly construction (per Jack Slocum transcripts):**
- Stage 1: if price dips below 7450, sell an **ITM short put spread** (e.g. sell 7455P / buy 7445P) for credit when price is at ~7445
- Stage 2: when price rebounds to 7450, sell a **short call spread** at 7450 (e.g. sell 7450C / buy 7460C) for credit
- If combined credit from both legs ≥ wing width, maximum risk is zero
- **Qualification:** Only attempt the zero-risk construction if tomorrow's GEX confirms 7450 as the key strike. Do not stage into this if tomorrow's profile shifts to a different level.

**Hold time:** Session hold to expiry (0DTE). The pin thesis is most valid in the first 2–3 hours of the US session when gamma hedging is most active.

### Secondary setup: CALL WALL at 7500 → Short Call Spread (for rally attempts)

If price rallies through 7460 toward 7500:
- Sell the **7500C**, buy the **7510C** for net credit
- Thesis: 7500 is the major structural call ceiling (8,307 total OI, net_oi +6,323); market makers with heavy call exposure at 7500 will aggressively sell futures as price approaches, capping the rally
- Entry zone: 7498–7505 on a rally attempt
- Entry timing: wait for price to touch or briefly breach 7500, enter on rejection
- Max loss: spread width minus credit (always defined)
- **Note:** This is a secondary, opportunistic trade — price is currently 50 pts away. Do not enter prematurely.

### ❌ Iron Butterfly — Partial qualification only
- `key_dominance_pct = 10.22%` is still below the ideal threshold for a high-conviction pin.
- The two-strike cluster (7450/7460, 54%) means a symmetric iron butterfly is riskier than usual on the call side.
- Use wider wings or asymmetric structure; do not treat this as a textbook clean pin.

---

## Section E — Invalidation Conditions

**PIN thesis (7450):**
- Invalidated if: SPX closes a 5-minute bar **above 7462** with rising volume (break above key2 with momentum means the pin has shifted upward to 7460 or higher) — exit short call leg.
- Invalidated if: SPX closes a 5-minute bar **below 7438** with rising volume (break below the pin and through the prior morning range) — exit short put leg.
- Migration signal: if `key_vol_net` turns negative intraday (put volume starts dominating at 7450), the anchor is drifting downward. Monitor this actively.

**7500 CALL WALL thesis:**
- Invalidated if: SPX closes a 5-minute bar **above 7508** with rising volume. The 7500 call ceiling has been absorbed and market makers have re-hedged. At that point the structural call pressure above 7500 is reduced and the trade fails.

**7400 PUT PILLAR (secondary, on a pullback):**
- Invalidated if: price breaks below **7388** with momentum. Yesterday showed this level can fail in negative gamma — but today's net GEX is near-neutral (-0.49B), so a cascade is less likely than yesterday.

**What a cascade looks like today:**
- With `net_gex = -0.49B` (near-neutral), a cascade is not the base case. However, if net GEX rotates more negative intraday (which can happen as the session progresses), the risk re-emerges. Any intraday re-check showing net_gex below -3B would restore cascade caution.

**Macro override:**
- Any binary event overrides GEX mechanics entirely. See Section G.

---

## Section F — Caution Notes

**Calendar:**
- Today is Tuesday 9 June 2026. Not end of month, end of quarter, monthly expiration, triple witching, or FOMC. No elevated calendar caution — but **verify the economic calendar** (Section G step 3).

**Abnormal OI:**
- 7500 has 8,307 total OI — elevated but not extreme. The elevated call OI at 7500 is structurally significant but does not constitute an "abnormal day" warning by itself.

**TOMORROW'S GEX — REQUIRED, NOT OPTIONAL:**
- Tomorrow's GEX profile has **not been checked**. The PIN thesis at 7450 and any iron butterfly construction **cannot be fully validated without it**. Per the transcripts (Jack Slocum, Zero Risk video): market makers begin repositioning toward tomorrow's key strike after approximately 14:00 ET. If tomorrow's key strike is different from 7450, the pin thesis may degrade in the final 90 minutes of today's session. **This is the single most important step before entering a PIN trade today.**

**Charm / delta decay:**
- Per Matt Cashman (interview): charm (delta decay from time passage alone) means OTM options lose delta throughout the day. By 14:00 ET, market maker delta hedging at the key strike changes independently of price movement. In a PIN setup, this typically means a natural drift toward the short strike as the day progresses — reinforcing the pin. However, it also means that if price has drifted away from 7450 by 14:00 ET, the pin is unlikely to recover.

**Capture time:**
- Data captured at **14:31 UK = 09:31 US Eastern** — approximately 90 minutes into the US session. Roughly 4.5 hours remain until close. This is a good time window for a PIN trade — enough session left for the pin to operate, but enough time has passed for the morning volatility to settle.

**Key intraday development:**
- Price has moved from 7405 at the open to 7449.76 at capture — a 44pt rally. The morning's earlier report identified a potential CALL WALL at 7450 that price needed to rally to. Price has now reached that level. The setup has changed from "rally target" to "pin candidate" within 80 minutes of the US open.

---

## Section G — Required Actions Before Trading

1. **Check tomorrow's GEX profile on Option Alpha** — is tomorrow's key strike also 7450? This is the single most critical step before entering any PIN or iron butterfly trade today. If tomorrow's key strike is at 7500 or 7400, do not hold a 7450 butterfly into the close.

2. **Confirm intraday call/put volume at 7450** — `key_vol_net = +3,264` (calls 5× puts) was captured at 09:31 ET. Monitor whether this ratio is maintaining or reversing. Sustained call dominance at 7450 supports the pin. Any shift to put dominance means the anchor is migrating.

3. **Verify the economic calendar** — confirm no Fed speakers, FOMC minutes release, CPI, or other binary macro events today. A scheduled event in the next 4.5 hours overrides the GEX setup.

4. **Monitor the intraday GEX chart for profile rotation** — with `key_dominance_pct = 10.22%` and a two-strike cluster at 7450/7460, the GEX profile can shift. If 7460 overtakes 7450 as the key strike intraday, adjust the butterfly center accordingly or stand aside.

5. **Check whether the 44pt morning rally has changed put/call skew** — a fast rally of this magnitude can shift the GEX profile materially as dealers re-hedge. The 14:31 capture reflects this new state, but another update after 11:00 ET would confirm whether the profile has stabilised at 7450.

---

*Report generated: 09 Jun 2026, 14:31 UK / 09:31 ET*  
*Source: `daily_gex_summary-concise.csv` + raw JSON OI table | Transcripts: `Gex/*.txt`*  
*Supersedes: `analysis-concise-20260609-1311.md`*
