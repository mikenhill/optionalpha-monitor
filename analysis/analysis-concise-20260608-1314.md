# SPX Concise GEX Report — 8 June 2026

**Captured:** 2026-06-08 13:14 BST (≈ 08:14 ET — early session, ~75 mins after open)
**SPX Last:** 7383.74
**Script classification:** PUT_PILLAR
**History available:** Jun 2, Jun 3, Jun 4, Jun 5 (4 prior days)

---

## Section A: Today's Values in Isolation

| Field | Value | Interpretation |
|---|---|---|
| `last` | **7383.74** | SPX at capture. Down significantly from Friday's close (7584.31 Jun 5). A gap-down weekend move of ~200 pts. |
| `sentiment` | **7.5%** | **Extremely bearish.** Only 3 of ~40 strikes have net positive GEX. This is the most bearish reading in the dataset by a wide margin. The 45% bearish threshold is far exceeded. |
| `gex_ratio` | **-3.87** | Put GEX dominates call GEX by nearly 4:1 across the whole window. Strongly put-dominated. |
| `net_gex` | **-16.49B** | Large negative gamma environment. Second only to Jun 3 (-20.03B). Market maker hedging will amplify moves in both directions. |
| `key_strike` | **7400** | Primary GEX anchor — 16.26 pts *above* current price. Price is currently trading *below* the key level. |
| `key_absolute` | **3.20B** | Meaningful absolute GEX. Mid-range conviction (between Jun 4's weak 1.16B and Jun 5's strong 6.24B). |
| `key_net` | **-1.91B** | Strongly net negative at key strike — put GEX far exceeds call GEX here. |
| `key_dominance_pct` | **11.43%** | Key strike holds 11.43% of window GEX. Moderate concentration — similar to prior days. |
| `key_call_gex` | **+0.64B** | Modest call GEX at 7400. |
| `key_put_gex` | **-2.55B** | Large put GEX at 7400. Put side is 4× the call side. |
| `key_call_oi` | **2,081** | Moderate call OI at 7400. |
| `key_put_oi` | **8,279** | Very large put OI at 7400. Nearly 4× the call OI. |
| `key_net_oi` | **-6,198** | Strongly put-heavy. Largest put-dominant OI reading in the dataset. |
| `key_call_vol` | **2,606** | Moderate call volume at 7400. |
| `key_put_vol` | **2,417** | Moderate put volume at 7400. Notably *slightly below* call volume. |
| `key_vol_net` | **+189** | **Call volume marginally dominant** (+189). This is a divergence from the strongly put-heavy OI structure. |
| `key2_strike` | **7350** | Second-highest GEX strike is 50 pts *below* current price and 33.74 pts below key_strike. |
| `key2_absolute` | **2.21B** | Key2 is 69% of key_absolute (3.20B). Within the 20% proximity threshold? No — key2/key = 0.69, meaning key2 is meaningfully smaller. This is not a tight two-strike tie, but 2.21B is still a substantial secondary level. |

### Setup Classification: **Put Pillar at 7400, above current price — with a volume divergence signal**

Price at 7383.74 is currently **16.26 pts below** the key strike of 7400. The key strike sits above price as a ceiling/resistance, not below as a floor. With key_put_oi at 8,279 and key_net_oi at -6,198, there is a massive concentration of put open interest at 7400 — the largest put-dominant OI reading in the 5-day dataset.

> **Teaching point — Magnet effect (Anticipate 0DTE, GEX Day Trading transcripts):** When price drops $5–$10 below a strike with large put open interest, market makers begin hedging. This can create a gravitational pull back toward the key strike. Jack Slocum explicitly traded this mechanic multiple times in the $1K/day transcript — price drops below the big GEX bar, he enters a long call spread (or here the equivalent short put spread), price rebounds to the strike. At 7383.74, price is ~16 pts below 7400, approaching the zone where hedging-driven reversion may activate.

> **Teaching point — Volume divergence / migration signal (More Informed 0DTE transcript):** `key_vol_net = +189` is *call-dominant*, while `key_net_oi = -6,198` is *strongly put-dominant*. This divergence — intraday call flow accumulating at a strike where structural positioning is overwhelmingly put-heavy — is the transcript's migration signal. It may indicate that buyers are beginning to position for a rebound to 7400, consistent with the magnet thesis. However, it could also reflect hedging activity that does not imply directional intent (per Mat Cashman's caution in the OIC transcript).

---

## Section B: Today vs Prior Days

| Metric | Jun 2 | Jun 3 | Jun 4 | Jun 5 | **Jun 8** | Assessment |
|---|---|---|---|---|---|---|
| `last` | 7595.78 | 7560.13 | 7553.68 | 7584.31 | **7383.74** | **Extreme drop** — down ~200 pts from Friday. Largest single-session move in dataset. |
| `sentiment` | 50.0% | 30.0% | 32.5% | 55.0% | **7.5%** | **Extreme low** — by far the most bearish reading. Prior low was 30.0% on Jun 3. |
| `gex_ratio` | +1.11 | -3.12 | -1.78 | -1.70 | **-3.87** | **Most negative in dataset.** More put-dominated than even Jun 3's extreme day. |
| `net_gex` | +2.36B | -20.03B | -2.63B | -13.14B | **-16.49B** | **Second most negative.** Extreme negative gamma. Only Jun 3 (-20.03B) was worse. |
| `key_strike` | 7600 | 7550 | 7525 | 7550 | **7400** | Dropped 150 pts from Friday. Largest single-day key_strike shift in dataset. |
| `key_absolute` | 6.52B | 3.94B | 1.16B | 6.24B | **3.20B** | Mid-range. Lower than the strong Jun 2/5 days but well above Jun 4's weak reading. |
| `key_dominance_pct` | 14.91% | 10.13% | 12.4% | 12.27% | **11.43%** | Normal range. GEX moderately concentrated. |
| `key_net_oi` | +487 | -3,478 | -252 | -1,808 | **-6,198** | **Most put-heavy OI in dataset.** Prior worst was Jun 3 at -3,478. Today is nearly 2× that. |
| `key_vol_net` | +17,906 | -73,614 | -789 | +954 | **+189** | Mildly call-dominant. Diverges from extreme put OI. Notable given the bearish context. |
| `key2_absolute` | 3.39B | 3.92B | 1.14B | 5.29B | **2.21B** | key2/key ratio = 0.69. Not a tight two-strike tie but key2 is still substantial. |

### Key observations vs prior days

**1. Sentiment at 7.5% is unprecedented in the dataset.** The prior floor was 30% (Jun 3). Today is more than 4× more bearish by this measure. This is an extreme reading.

**2. The key_strike dropped 150 pts in one session (7550 → 7400).** This is the largest single-day anchor shift in the dataset and reflects a wholesale repricing of the options market over the weekend. The GEX window has moved decisively lower.

**3. key_net_oi at -6,198 is the most put-heavy structural positioning seen.** 8,279 put contracts vs 2,081 call contracts at 7400. This is not close — put OI is 4× call OI. Even Jun 3's extreme day (-3,478) was half this level.

**4. Volume divergence is the most notable intraday signal.** On Jun 3 the extreme put day had -73,614 key_vol_net (put volume confirming put structure). Today, with nearly as extreme a put structure (-6,198 OI), call volume is slightly dominant (+189). This is atypical and is the most important intraday signal to watch.

**5. Net_gex at -16.49B confirms negative gamma amplification.** This is a high-risk environment for selling premium. Moves away from the key strike will be amplified, not dampened.

---

## Section C: GEX Teaching Point Mapping

| Teaching Point | Applies? | Evidence |
|---|---|---|
| **Pin / Magnet** | ⚠️ Partial | key_absolute is a meaningful level but call/put GEX is 4:1 put-heavy — not balanced. Not a clean pin. However, the magnet-to-key-strike thesis still applies directionally. |
| **Put Pillar / Support at 7400** | ✅ Yes — but above price | key_put_gex -2.55B, key_put_oi 8,279, key_net_oi -6,198. Massive put structure. The pillar is 16 pts *above* current price, meaning it acts as a **magnetic ceiling** that price may gravitate back up toward from below. |
| **Call Wall / Resistance** | ❌ No | No call-side dominance at any strike. |
| **Negative Gamma Acceleration** | ✅ Extreme | net_gex -16.49B. Second only to Jun 3. Any move lower will be amplified by market maker selling. |
| **GEX Slide** | ❌ No | key2 at 7350 is defined. Not a distributed profile. |
| **Positive Gamma Stabilising** | ❌ No | Sentiment 7.5%, net_gex -16.49B. Opposite environment. |
| **Volume Divergence** | ✅ Yes — critical signal | key_vol_net +189 (call-dominant) vs key_net_oi -6,198 (put-dominant). Intraday call flow is accumulating at a structurally put-heavy strike. Possible rebound positioning signal. |
| **Captain Condor / Condor Artifact** | ⚠️ Possible | 8,279 put OI at 7400 is very large. Some of this will be condor short put legs at 7400 (the transcript explicitly identifies this pattern). OI alone cannot confirm directional put buying. The put *volume* today (2,417) is modest, which means most of this OI is *pre-existing* from prior sessions — consistent with condor positioning accumulated before this weekend's drop. |
| **Cascade risk below key2** | ✅ Active | key2 at 7350 is 33.74 pts below key and 50 pts below current price. In -16.49B negative gamma, a decisive break below 7350 would remove both GEX anchors with amplified selling pressure below. |

### Dominant Setup: **Put Pillar above price — potential magnet reversion to 7400, within extreme negative gamma**

This is an unusual configuration: the key strike (7400) is *above* current price (7383.74). The massive put structure at 7400 (8,279 put OI) means market makers have large put positions there. With price having fallen below, the charm/delta decay and reversion dynamic from the transcripts may be pulling price back toward 7400.

> **Teaching point — Below the big block (Anticipate 0DTE, GEX Day Trading transcripts):** Jack Slocum's primary setup is exactly this: price drops $5–$10 below the strike with the largest gamma exposure and put OI, then he enters a position expecting a rebound to the key strike. At 7383.74 with 7400 being the key strike, price is 16.26 pts below — in the zone where the transcript says market maker hedging begins driving a reversion. This is the primary tradeable signal today.

> **Teaching point — Negative gamma cascade risk (Mat Cashman OIC transcript):** However, net_gex at -16.49B means if the reversion fails and price continues lower, market makers are *forced to sell more* as price falls, creating a cascade. Key2 at 7350 is the next structural level. A break of 7350 in this environment could be rapid and self-reinforcing.

---

## Section D: Educational Trade Logic

> Educational examples only. Not financial advice. **This is a negative gamma day — all positions carry elevated risk of rapid moves through short strikes. Size accordingly.**

### Setup: Reversion to 7400 — Short Put Spread (credit)

**Thesis:** Price at 7383.74 is below the key strike of 7400 with massive put OI there. The magnet effect may draw price back up toward 7400. Market maker hedging flows (charm + delta decay) support this directional bias. Intraday call volume is already slightly dominant, suggesting early rebound positioning.

- **Structure:** Short put spread (sell put above current price, buy lower put as protection)
- **Short leg:** Sell 7400P (at the key strike, the structural anchor)
- **Long leg:** Buy 7390P (10 pts below, defined risk wing)
- **Net credit:** Collect premium for the spread; max profit = full credit if price closes at or above 7400
- **Max loss:** 10 pts (spread width) minus credit received — always defined
- **Entry zone:** Price at 7378–7390 (stretched slightly below current level, per transcript teaching — wait for the overshoot)
- **Entry timing:** Do not enter immediately at current price. Wait for price to dip a further 3–5 pts toward 7378–7380, then look for a small stabilisation or uptick before entering
- **Target:** Price rebounds to 7395–7405 (key strike zone); close position at 50–70% of max credit
- **Hold time:** Scalp — aim to close within 30–60 minutes of entry
- **Zero-risk iron butterfly qualification:** ❌ Not applicable — key_net is not balanced (-1.91B), and net_gex is -16.49B. The pin condition is not met. Do not attempt zero-risk construction today.

### What NOT to do today

- **Do not sell a short call spread** — price is already below the key strike. Selling calls above 7400 in negative gamma with sentiment at 7.5% risks rapid move upward through your short strike if reversion accelerates.
- **Do not hold overnight** — today is Monday following a large weekend gap-down. Intraday GEX profiles on high-volatility days can rotate significantly.
- **Do not sell iron butterflies** — negative gamma (-16.49B) means price will not pin. The damping effect required for iron butterfly profitability is absent.

---

## Section E: Invalidation Conditions

- **7375 breaks with momentum** — if price falls decisively through 7375 (currently 8.74 pts below price), the magnet reversion thesis is invalidated. The 7400 put pillar has failed to attract price. Exit immediately.
- **7350 breaks (key2 level)** — in -16.49B negative gamma, a break of 7350 could trigger a cascade. Market makers sell more delta as price falls through this level. Do not hold any position through a break of 7350.
- **Vol at 7400 rotates lower intraday** — if the key_vol_net shifts from +189 (call-dominant) to strongly negative (put-dominant accumulating), the reversion thesis is weakening. Monitor the OA GEX chart for volume building at 7350 or lower.
- **Macro shock** — any unexpected news event (Fed commentary, geopolitical, macro data) in a -16.49B net_gex environment will produce amplified moves that override GEX entirely. Today's sentiment (7.5%) already reflects extreme fear — additional negative news could be disproportionately impactful.

---

## Section F: Caution Notes

| Factor | Status |
|---|---|
| **End of month** | No — 8 June |
| **End of quarter** | No |
| **Monthly expiration** | No — standard Monday |
| **Triple witching** | No |
| **FOMC / Fed day** | Unknown — **verify the calendar.** In a -16.49B negative gamma environment, any Fed commentary today would be extremely high risk. |
| **Weekend gap-down** | ⚠️ **Yes — ~200 pts.** Monday after a large gap-down is one of the highest-risk days for GEX trading. The option chain has repriced over the weekend; today's GEX profile reflects a new reality that the market has not yet had a chance to trade through. Early session GEX readings on gap days are less reliable. |
| **Sentiment extreme** | ⚠️ **7.5% — unprecedented in dataset.** Per the transcripts (GEX Day Trading, How I Recovered), days with abnormal open interest or extreme readings should prompt reduced size or avoidance. |
| **Negative gamma magnitude** | ⚠️ **-16.49B — second highest in dataset.** Amplification risk is extreme. |
| **Condor artifact at 7400** | ⚠️ Pre-existing put OI of 8,279 at 7400 is likely partly from condor short put legs accumulated at prior price levels. This OI may not represent new bearish positioning — it may be legacy structure. The modest put *volume* today (2,417) supports this interpretation. |
| **Tomorrow's GEX — required check** | ❌ **Not done.** On a gap-down Monday, tomorrow's GEX is especially important. If tomorrow's key strike is significantly below 7400, market makers may not defend 7400 today at all. The magnet/reversion thesis depends entirely on 7400 remaining the dominant anchor through the session. **Do not trade the reversion thesis without first confirming tomorrow's GEX.** |
| **Charm / delta decay** | Capture at 13:14 BST = 08:14 ET. This is **very early session** — only ~75 mins after open. The full day's charm effects have not begun. This is both an opportunity (maximum pin duration remaining) and a risk (GEX profile can rotate significantly as the session progresses). |
| **Capture time** | 08:14 ET — early session. Approximately 5.75 hours of session remaining. The GEX profile captured this early on a high-volatility gap-down day may change materially by mid-morning. Recheck the live GEX chart on OA before entering any position. |

> **Teaching point — Abnormal days (GEX Day Trading, How I Recovered transcripts):** Monday following a large gap-down is explicitly in the category of days where the GEX profile is less reliable. The first Friday of the month with 10,000+ OI caused Jack Slocum's largest losses when he tried to force trades around those levels. Today has 8,279 put OI at 7400 — same class of event. **Reduce position size to the minimum viable size for any trade today.**

> **Teaching point — Emotional discipline (GEX Day Trading transcript):** The transcript describes how a large unexpected loss (the surprise iron condor bot trade) sent Jack into a "tilt" state where subsequent trades were fear-driven rather than logic-driven. A 200-point weekend gap-down is exactly the kind of event that can trigger this state. If you are monitoring your portfolio P&L from Friday's close, be aware that trading today from a position of trying to "get back" Friday losses is the most dangerous mental state described in the transcripts. Trade only if you are in a state of peace and making information-based decisions.

---

## Section G: Required Actions Before Trading

1. **Check tomorrow's GEX profile on Option Alpha** — is 7400 still the key strike? This is the single most important check. The reversion/magnet thesis at 7400 only holds if tomorrow's key strike is also at or near 7400. If tomorrow's key is at 7350 or lower, the 7400 level may not hold today.

2. **Recheck the live GEX chart** — this was captured at 08:14 ET (early session). A gap-down Monday means the option chain is actively being repriced. The GEX profile may have already shifted by 09:30–10:00 ET. Check whether 7400 is still the highest absolute GEX bar or whether new volume has built at a different level.

3. **Verify the economic calendar** — confirm no FOMC meeting, Fed speakers, CPI, or other binary events today. In -16.49B negative gamma, a macro surprise produces cascading amplified moves that no GEX level can contain.

4. **Monitor key_vol_net intraday** — the early-session divergence (call vol +189 vs put OI -6,198) is the primary signal for the reversion thesis. If put volume starts dominating at 7400 (vol rotating negative), the thesis weakens. If call volume builds further, reversion is gaining momentum.

5. **Set a hard stop at 7375 before entering** — in negative gamma, mental stops are insufficient. Decide your exit level before touching the position.

6. **Assess emotional state before trading** — per the GEX Day Trading transcript: only trade from a state of peace and logic, not from fear of missing the rebound or desperation to recover a Friday loss.

---

*Report generated from `daily_gex_summary-concise.csv` (5 rows: Jun 2–8) and all source transcripts in the Gex directory.*
*Script classification: PUT_PILLAR | key_strike: 7400 | net_gex: -16.49B | sentiment: 7.5%*
