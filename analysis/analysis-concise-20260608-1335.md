# SPX Concise GEX Report — 8 June 2026 (v2 — proximity-weighted key strike)

**Captured:** 2026-06-08 13:14 BST (≈ 08:14 ET — early session, ~75 mins after open)
**Report generated:** 2026-06-08 13:35 BST
**SPX Last:** 7383.74
**Script classification:** PUT_PILLAR
**Key strike method:** Proximity-weighted absolute GEX (Gaussian decay, bandwidth = 50 pts)
**History available:** Jun 2, Jun 3, Jun 4, Jun 5, Jun 8 (5 rows total; Jun 8 is today)

> **Note on key strike selection:** The OA chart displays 7450 as the visually tallest bar (~3.1B).
> However 7450 is 66 pts OTM while 7400 is only 16 pts OTM. After proximity weighting:
> 7400 effective score = 3.031B | 7450 effective score = 0.844B.
> 7400 is correctly the dominant actionable anchor. The script now matches physical gamma mechanics.

---

## Section A: Today's Values in Isolation

| Field | Value | Interpretation |
|---|---|---|
| `last` | **7383.74** | SPX at capture. ~200 pt gap-down from Friday close (7584.31). Large weekend move. |
| `sentiment` | **7.5%** | **Extreme bearish.** Only ~3 of 40 strikes carry net positive GEX. Far below the 45% bearish threshold. Most extreme reading in the 5-day dataset. |
| `gex_ratio` | **-3.87** | Put GEX dominates call GEX nearly 4:1 across the window. Most negative ratio in dataset. |
| `net_gex` | **-16.49B** | Strong negative gamma. Second only to Jun 3 (-20.03B). Moves amplified in both directions by market maker hedging. |
| `key_strike` | **7400** | Primary GEX anchor. 16.26 pts *above* current price — price is trading below the key level. |
| `key_absolute` | **3.20B** | Raw absolute GEX at 7400. Mid-range conviction — above Jun 4's weak 1.16B, well below Jun 5's strong 6.24B. |
| `key_net` | **-1.91B** | Strongly net negative at key strike. Put GEX (-2.55B) is 4× call GEX (+0.64B). |
| `key_dominance_pct` | **11.43%** | Moderate concentration — 7400 holds 11.43% of window GEX. In line with prior days (10–15% range). |
| `key_call_gex` | **+0.64B** | Modest call GEX at 7400. |
| `key_put_gex` | **-2.55B** | Large put GEX at 7400. Dominant side. |
| `key_call_oi` | **2,081** | Moderate call OI. |
| `key_put_oi` | **8,279** | Very large put OI — nearly 4× call OI. Largest absolute put OI at any key strike in dataset. |
| `key_net_oi` | **-6,198** | Most strongly put-heavy OI in the dataset. Jun 3's prior worst was -3,478 — today is nearly 2× that. |
| `key_call_vol` | **2,606** | Moderate call volume at 7400. |
| `key_put_vol` | **2,417** | Slightly *less* put volume than call volume despite massive put OI structure. |
| `key_vol_net` | **+189** | **Call volume marginally dominant.** Diverges from the extreme put-heavy OI. Key signal — see Section C. |
| `key2_strike` | **7350** | Second proximity-weighted GEX anchor. 33.74 pts below key_strike; 50 pts below current price. |
| `key2_absolute` | **2.21B** | key2/key ratio = 0.69 — not a tight two-strike tie, but a meaningful secondary level. |

---

## Section B: Today vs Prior Days

| Metric | Jun 2 | Jun 3 | Jun 4 | Jun 5 | **Jun 8** | Assessment |
|---|---|---|---|---|---|---|
| `last` | 7595.78 | 7560.13 | 7553.68 | 7584.31 | **7383.74** | Largest single-session drop in dataset (~200 pts). |
| `sentiment` | 50.0% | 30.0% | 32.5% | 55.0% | **7.5%** | Extreme low. Prior floor was 30% (Jun 3). Today is 4× more bearish. |
| `gex_ratio` | +1.11 | -3.12 | -1.78 | -1.70 | **-3.87** | Most negative in dataset. Worse than Jun 3 extreme. |
| `net_gex` | +2.36B | -20.03B | -2.63B | -13.14B | **-16.49B** | Second most negative. High cascade risk. |
| `key_strike` | 7600 | 7550 | 7525 | 7550 | **7400** | Dropped 150 pts from Friday — largest single-day anchor shift in dataset. |
| `key_absolute` | 6.52B | 3.94B | 1.16B | 6.24B | **3.20B** | Mid-range. Adequate conviction but not a dominant outlier. |
| `key_dominance_pct` | 14.91% | 10.13% | 12.4% | 12.27% | **11.43%** | Normal range. No concern. |
| `key_net_oi` | +487 | -3,478 | -252 | -1,808 | **-6,198** | Most put-heavy in dataset — by a wide margin. |
| `key_vol_net` | +17,906 | -73,614 | -789 | +954 | **+189** | Mildly call-dominant. Diverges sharply from OI structure. |
| `key2_absolute` | 3.39B | 3.92B | 1.14B | 5.29B | **2.21B** | key2/key = 0.69. Single dominant strike, not a two-strike tie. |

### Key observations

- **Sentiment at 7.5% is an outlier.** No prior day came close. Entire window is in net negative GEX territory.
- **key_strike dropped 150 pts in one session.** The GEX distribution has repriced the whole window 150 pts lower over the weekend. This is a structural shift, not an intraday move.
- **key_net_oi at -6,198 is unprecedented in this dataset.** 8,279 put contracts vs 2,081 call at 7400. Pre-existing put OI is the dominant structural force.
- **Volume divergence is the key intraday signal.** Put OI -6,198 but call vol slightly dominant (+189). Suggests early rebound positioning or hedging activity from put sellers. Not confirmed directional buying — but worth watching.
- **7450 note:** The OA chart shows 7450 as visually larger than 7400. Raw `abs` at 7450 = 2.053B but it sits 66 pts OTM. After proximity weighting, its effective score = 0.844B vs 7400's 3.031B. The script correctly selects 7400. The 7450 level remains a secondary reference point for the session.

---

## Section C: GEX Teaching Point Mapping

| Teaching Point | Status | Evidence |
|---|---|---|
| **PIN / Magnet** | ⚠️ Weak / partial | key_absolute 3.20B is meaningful but call/put GEX ratio is 4:1 put-heavy. key_net = -1.91B. Not balanced — not a clean pin. Magnet reversion *toward* 7400 from below is the operative mechanism, not oscillation around it. |
| **PUT PILLAR at 7400** | ✅ Primary setup — but above price | key_put_gex -2.55B, key_put_oi 8,279, key_net_oi -6,198. Massive put concentration. Pillar is 16 pts above current price, acting as a ceiling/magnet rather than a floor. |
| **CALL WALL** | ❌ No | No call-dominant strike. |
| **Negative Gamma Acceleration** | ✅ Active — extreme | net_gex -16.49B. Any move lower from current price is amplified. Market makers sell delta as price falls, pushing price lower. |
| **GEX Slide** | ❌ No | key2 at 7350 is defined. Not distributed. |
| **Positive Gamma Stabilising** | ❌ No | Opposite environment. |
| **Volume Divergence** | ✅ Active — critical signal | key_vol_net +189 (call-dominant) vs key_net_oi -6,198 (put-dominant). Per the transcripts, this divergence may indicate early rebound positioning at 7400. However it could also reflect condor delta hedging. Monitor for volume building. |
| **Captain Condor / Condor Artifact** | ⚠️ Probable | 8,279 put OI at 7400 is very large and was accumulated *before* this weekend's gap-down. Much of this is likely condor short put legs struck at 7400 when the market was higher. These holders are now deeply ITM and their hedging behaviour is different from fresh directional put buyers. OI *cannot* confirm directional intent. |
| **Cascade risk below key2** | ✅ Active | key2 at 7350 is 50 pts below current price. In -16.49B negative gamma, a clean break of 7350 removes both structural anchors and triggers amplified selling. This is the primary downside risk level. |

### Dominant classification: **PUT PILLAR above price — magnet reversion candidate to 7400, within extreme negative gamma**

Price (7383.74) is 16 pts below the key strike (7400). This is the exact setup described in the transcripts: price has fallen below a strike with massive put open interest, and market maker delta hedging creates a gravitational pull back toward the key strike. The +189 call vol divergence is a tentative early confirmation of this dynamic.

> **Teaching point (Anticipate 0DTE, GEX Day Trading):** Jack Slocum's core setup: "price drops $5–$10 below the biggest GEX bar, then I enter expecting a quick rebound." At 7383.74 with the key bar at 7400, price is 16 pts below — in the rebound zone. He entered long call spreads in this scenario; the short premium equivalent is a short put spread.

> **Teaching point (OIC transcript — Mat Cashman):** In negative gamma (-16.49B), market makers hedge by *going with the trend* — selling when price falls, buying when it rises. This creates a self-reinforcing dynamic in both directions. The reversion to 7400 is plausible, but a failure of 7400 to attract price could accelerate into a cascade.

> **Teaching point (More Informed 0DTE):** Tomorrow's GEX confirmation is essential before committing to a pin or magnet thesis. If tomorrow's key strike is below 7400, market makers may begin repositioning away from 7400 during today's session — weakening the magnet effect.

---

## Section D: Educational Trade Logic

> **Educational examples only. Not financial advice.**
> **This is a high-risk day: net_gex -16.49B, sentiment 7.5%, Monday gap-down. Reduce size to minimum viable.**

### Setup: Reversion to 7400 — Short Put Spread (credit, defined risk)

**Thesis:** Price below the largest proximity-weighted GEX strike. Massive put OI at 7400 creates market maker hedging pressure pulling price toward 7400. Early call volume divergence supports rebound positioning.

| Parameter | Detail |
|---|---|
| **Structure** | Short put spread |
| **Short leg** | Sell 7400P (at key strike) |
| **Long leg** | Buy 7390P (10 pts below — defined risk wing) |
| **Net credit** | Collect spread premium upfront |
| **Max profit** | Full credit — if price closes at or above 7400 |
| **Max loss** | 10 pts (spread width) minus credit received |
| **Entry zone** | 7376–7388 — wait for price to stretch slightly further below current level |
| **Entry timing** | Do NOT enter at market open. Wait for price to dip 3–5 pts further (toward 7378–7380), stabilise or tick up, then enter. Per transcripts: "wait for the overshoot, then enter on the reversion." |
| **Target** | Price retraces to 7395–7405. Close at 50–70% of max credit. |
| **Hold time** | Scalp — 20–60 minutes. Do not hold into afternoon charm decay. |
| **Zero-risk iron butterfly** | ❌ Not applicable. key_net = -1.91B (not balanced). net_gex = -16.49B. Pin condition not met. |

### What NOT to do today

- **No short call spreads.** Price is below key_strike. Selling calls at or above 7400 in -16.49B negative gamma risks a rapid squeeze through your short strike if reversion accelerates.
- **No iron butterflies.** Negative gamma amplifies moves — price will not pin around 7400 with the conviction required for iron butterfly profitability.
- **No holding through cascade triggers.** If 7375 breaks, exit. If 7350 breaks, do not add.

---

## Section E: Invalidation Conditions

- **7375 breaks with momentum** — 8.74 pts below current price. If price moves decisively through 7375 on volume without pause, the magnet/reversion thesis is invalidated. The 7400 put pillar has failed to attract. Exit immediately. Do not average down.
- **7350 breaks (key2_strike)** — in -16.49B negative gamma, a break of 7350 is a cascade signal. Both structural anchors (7400, 7350) have failed. Market maker selling accelerates below this level. No new positions below 7350.
- **key_vol_net turns strongly negative intraday** — if put volume at 7400 begins significantly outpacing call volume, the early rebound signal (vol divergence) is reversing. The structural put OI is being reinforced by new put buying, not rebound hedging. Exit or do not enter.
- **New volume building at 7350 rather than 7400** — per the transcripts, intraday volume migration to a lower strike signals the GEX anchor is shifting. If the OA live chart shows a growing bar at 7350, that level is becoming the new magnet, not 7400.
- **Any macro event** — in -16.49B negative gamma, a surprise Fed statement, geopolitical event, or data release will produce amplified moves that override all GEX structure. Today's extreme sentiment (7.5%) indicates the market is already pricing fear — additional negative catalysts will have outsized impact.

---

## Section F: Caution Notes

| Factor | Status |
|---|---|
| **End of month** | No — 8 June |
| **End of quarter** | No |
| **Monthly expiration** | No |
| **Triple witching** | No |
| **FOMC / binary event** | ⚠️ **Unknown — verify before trading.** In -16.49B net_gex, any Fed commentary produces extreme amplified moves. |
| **Weekend gap-down (~200 pts)** | ⚠️ **Yes.** Monday after a large gap-down is one of the least reliable days for GEX per the transcripts. The option chain repriced over the weekend. The GEX window has shifted 150 pts lower. Early session GEX on gap days is less stable. |
| **Sentiment extreme** | ⚠️ **7.5%** — unprecedented in this dataset. Per transcripts (GEX Day Trading, How I Recovered): abnormal open interest days or extreme readings warrant reduced size or avoidance. |
| **Negative gamma magnitude** | ⚠️ **-16.49B** — second highest in dataset. Amplification risk is severe. |
| **Captain Condor artifact at 7400** | ⚠️ Put OI of 8,279 at 7400 is largely pre-existing from when price was higher. Much is likely condor short put legs now ITM. These holders behave differently from fresh directional put buyers. OI does not confirm direction. |
| **7450 visual dominance on OA chart** | ℹ️ The OA chart shows 7450 as visually larger than 7400. This is because the chart does not apply proximity discounting. After weighting by distance from price (66 pts vs 16 pts), 7400 remains the dominant actionable anchor. 7450 is a secondary structural reference only. |
| **Tomorrow's GEX — REQUIRED, NOT DONE** | ❌ **Not checked.** The magnet/reversion thesis at 7400 depends entirely on 7400 remaining the dominant anchor through the session. If tomorrow's key strike is at 7350 or lower, market makers will begin repositioning away from 7400 during today's afternoon session — weakening the magnet. **Do not trade the reversion thesis without first checking tomorrow's GEX on Option Alpha.** |
| **Charm / delta decay** | Capture at 08:14 ET — very early session. Charm effects are minimal now but build significantly through the day. By 13:00–14:00 ET, delta decay at 7400 will be accelerating, changing hedging flow dynamics independently of price movement. Early entries have the most time before charm undermines the thesis. |
| **Capture time** | **08:14 ET — early session.** ~5.75 hours of trading remain. Positive: maximum pin duration still available. Risk: gap-down Monday GEX profiles can rotate significantly in the first 60–90 minutes. Recheck the live OA GEX chart before entering any position. |

> **Teaching point — Emotional discipline (GEX Day Trading transcript):** A 200-point weekend gap-down is exactly the trigger that sent Jack into a "tilt" state in the transcript — making increasingly large, fear-driven trades to recover losses. If you are seeing a P&L drawdown from Friday, trade only from a state of peace and logic. The transcript explicitly states: the decisions made while trying to "get back" losses are compromised decisions that compound the problem.

---

## Section G: Required Actions Before Trading

1. **Check tomorrow's GEX on Option Alpha** — is 7400 still the dominant strike for 9 June? This is mandatory. The reversion thesis fails if tomorrow's key is at 7350 or lower.

2. **Recheck the live OA GEX chart** — captured at 08:14 ET on a volatile gap-down Monday. The profile may already have shifted. Confirm 7400 is still the largest proximity-weighted bar before entering.

3. **Verify the economic calendar** — confirm no FOMC, Fed speakers, CPI, NFP, or other binary events today. In -16.49B net_gex, a macro surprise is unmanageable.

4. **Watch key_vol_net intraday** — the early call vol divergence (+189) is the reversion signal. If put volume starts dominating at 7400, the thesis is reversing. If call volume builds further toward 7400, reversion has momentum.

5. **Set a hard stop at 7375 before touching any position.** In negative gamma, mental stops fail. Decide and enter the stop level before you enter the spread.

6. **Size to minimum viable.** Today meets at least three of the transcript's "reduce or avoid" criteria: gap-down Monday, sentiment extreme (7.5%), net_gex extreme (-16.49B). If you trade, trade small.

---

*Report generated from `daily_gex_summary-concise.csv` (5 rows: Jun 2–8) and all source transcripts in `Gex/`.*
*Script classification: PUT_PILLAR | key_strike: 7400 (proximity-weighted) | net_gex: -16.49B | sentiment: 7.5%*
*Key strike selection method updated this session: Gaussian proximity decay, bandwidth 50 pts.*
