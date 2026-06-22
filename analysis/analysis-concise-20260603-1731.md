# SPX Concise GEX Report — 3 June 2026

**Captured:** 2026-06-03 17:31 BST (≈ 12:31 ET — early afternoon US session)
**SPX Last:** 7560.13
**History available:** This is the first row. No prior days to compare against.

---

## Section A: Today's Values in Isolation

| Field | Value | Interpretation |
|---|---|---|
| `last` | **7560.13** | SPX price at capture |
| `sentiment` | **30.0%** | Strongly bearish — only 12 of 40 strikes have net positive GEX. Well below the 45% bearish threshold. |
| `gex_ratio` | **-3.12** | Put GEX dominates call GEX by a 3:1 ratio. Strongly put-side dominated across the window. |
| `net_gex` | **-20.03B** | Very large negative gamma environment. Market maker hedging will amplify moves in both directions. |
| `key_strike` | **7550** | Primary GEX anchor. 10.13 pts below current price — price is slightly above the key level. |
| `key_absolute` | **3.94B** | Large absolute GEX at 7550. A meaningful anchor level. |
| `key_net` | **-3.21B** | Strongly net negative at key strike — put GEX far exceeds call GEX here. |
| `key_dominance_pct` | **10.13%** | Key strike holds 10.1% of total window GEX. Moderate concentration — not a dominant outlier. |
| `key_call_gex` | **+0.37B** | Very small call exposure at 7550. |
| `key_put_gex` | **-3.57B** | Overwhelming put exposure at 7550. Ratio is approximately 10:1 put vs call. |
| `key_call_oi` | **398** | Very low call open interest at 7550. |
| `key_put_oi` | **3,876** | Very large put open interest at 7550. Nearly 10× the call OI. |
| `key_net_oi` | **-3,478** | Strongly put-heavy. One of the most one-sided OI readings possible. |
| `key_call_vol` | **4,818** | Moderate call volume at 7550. |
| `key_put_vol` | **78,432** | Extremely large put volume at 7550. 16× the call volume. |
| `key_vol_net` | **-73,614** | Massive put volume dominance. Intraday flow is strongly selling puts or buying put protection. |
| `key2_strike` | **7580** | Second-highest GEX strike is 30 pts *above* current price. |
| `key2_absolute` | **3.92B** | Almost identical to key_absolute (3.94B). Difference of only 0.02B — essentially a tie. |

### Setup Classification

**Primary: Strong Put Pillar at 7550, within a two-strike contested cluster.**

The 7550 strike is dominated almost entirely by put GEX, put OI, and put volume. With `key_net_oi = -3,478` and `key_vol_net = -73,614`, this is an extreme put-pillar reading. The put volume of 78,432 is exceptional — this is not routine positioning, this is heavy concentrated put activity at one strike.

> **Teaching point — Put Pillar (Identify Bullish 0DTE, GEX Day Trading transcripts):** A GEX pillar occurs when put GEX and put OI are both significantly larger than call equivalents at the key strike. The teaching is that when price falls to or below this level, market maker hedging may create a support effect as they buy back delta. The pillar at 7550 is strongly qualified by volume confirmation (78K put vol).

**However — this is NOT a clean outlier.** Key2 at 7580 has 3.92B absolute GEX, essentially equal to the key at 3.94B. This is a two-point tie, not a single dominant strike.

> **Teaching point — Outlier qualifier (Quick Wins, Zero Risk transcripts):** The strongest setups occur when one strike is a pronounced outlier above all others. When key2 is within ~20% of key (here within 0.5%), this is a two-strike contested structure, not a clean pin or pillar. The 7550 pillar and the 7580 level above must both be treated as active GEX anchors simultaneously.

**7580 character:** Key2 at 7580 is 20 pts above current price. Given the overall bearish context (sentiment 30%, gex_ratio -3.12), 7580 likely represents a **call wall / resistance** level — a ceiling that would be difficult to break through.

**Negative gamma environment — dominant theme:** With net_gex at -20.03B, this is the defining feature of the day. Every move will be amplified by market maker hedging. This is not a stabilising, dampening day.

> **Teaching point — Captain Condor / condor artifact (Mat Cashman transcript):** The extreme put OI at 7550 (3,876 contracts vs 398 calls) could partly reflect condor structures where 7550 is the lower short put strike. This does not invalidate the GEX reading but means the OI cannot confirm directional intent alone. The exceptional put *volume* (78,432) is harder to dismiss — current-day volume reflects active intraday positioning, not just prior-day OI.

### Price Context

SPX at 7560.13 is **+10.13 pts above** the 7550 key strike. Price is sitting just above the pillar level with a call wall 20 pts above at 7580. The market is sandwiched in a 30-point band: 7550 support below, 7580 resistance above.

---

## Section B: Today vs Prior Days

This is the **first row** in the dataset. No historical comparison is available. All assessments in Section A are based on internal values alone.

Benchmarks established by this row for future comparison:

| Metric | Jun 3 baseline |
|---|---|
| Sentiment range start | 30.0% |
| Net GEX range start | -20.03B |
| Key absolute range start | 3.94B |
| Key dominance range start | 10.13% |
| Key net OI range start | -3,478 |
| Key vol net range start | -73,614 |

---

## Section C: GEX Teaching Point Mapping

| Teaching Point | Applies? | Evidence |
|---|---|---|
| **Pin / Magnet** | ❌ No | Calls at 7550 are only 0.37B vs puts -3.57B. Strongly one-sided, not balanced. |
| **Put Pillar / Support** | ✅ Strong | key_put_gex -3.57B, key_put_oi 3,876, key_vol_net -73,614. Textbook pillar. |
| **Call Wall / Resistance** | ✅ Yes (7580) | Key2 at 7580 is above price. Call GEX at key2 not directly available but structure is above-market resistance. |
| **Negative Gamma Acceleration** | ✅ Extreme | net_gex -20.03B. The largest negative reading in the dataset. Any sustained move amplifies. |
| **GEX Slide** | ⚠️ Partial risk | Two near-equal strikes (7550/7580) creates distributed exposure. A break below 7550 could slide. |
| **Positive Gamma Stabilising** | ❌ No | Sentiment 30%, net_gex -20.03B. Opposite environment. |
| **Volume Divergence** | ❌ No divergence | Vol and OI both strongly put-dominated. Alignment is consistent. |
| **Today/Tomorrow Alignment** | ❌ Not checked — required | Pin/pillar confidence cannot be fully assessed. |

**Dominant setup: Put Pillar at 7550 within a negative gamma environment, with call wall resistance at 7580. Price sandwiched in a 30-point band.**

> **Teaching point — Negative gamma cascade (Mat Cashman, GEX Day Trading transcripts):** At -20.03B net GEX, a decisive break *below* 7550 (the pillar) would remove the main hedging support. Market makers would then need to sell more delta as price falls, reinforcing the downward move. The next GEX level below 7550 is unknown without the full window, but the cascade risk in this environment is high. A break of 7550 with momentum is not a routine stop-out — it may be the start of a fast directional decline.

---

## Section D: Educational Trade Logic

> Educational examples only. Not financial advice.

### Setup 1 — Put Pillar Bounce (if price falls to or through 7550)

**Thesis:** The massive put OI and put volume at 7550 creates a structural support. If price falls to 7548–7552, market maker hedging may produce a rebound.

- **Structure:** Long call spread, e.g. buy 7550C / sell 7560C
- **Entry zone:** Price at or just below 7550 (7545–7552), after a small overshoot below
- **Entry timing:** Per transcripts — do not enter immediately; wait for price to stretch 3–5 pts below 7550 before entering, then look for a reversal signal
- **Target:** Quick revert to 7560–7565
- **Hold time:** Scalp — minutes, not hours
- **Caution:** net_gex is -20.03B. If 7550 breaks with momentum rather than a brief touch, the bounce thesis is immediately invalid. Do not hold through a decisive break.

### Setup 2 — Call Wall Fade at 7580 (if price rallies toward key2)

**Thesis:** Key2 at 7580 (3.92B) above current price in a bearish sentiment (30%) and strongly negative gamma environment. If price rallies to 7578–7582, the call wall may create rejection.

- **Structure:** Long put spread, e.g. buy 7580P / sell 7570P
- **Entry zone:** Price at 7578–7585
- **Target:** Revert to 7565–7570
- **Caution:** Key2 is equally strong to key (3.92B vs 3.94B). If the call wall at 7580 breaks upward with momentum in negative gamma, the move could accelerate sharply above 7580. The 7580 level is resistance, not an absolute ceiling.

### Setup 3 — Range trade within 7550–7580 band

**Thesis:** With a pillar at 7550 and a wall at 7580, price may oscillate within this 30-point band.

- **Structure:** Iron condor centred on the range, or successive short spreads at each boundary
- **Entry:** Scale into short put spreads near 7550 and short call spreads near 7580
- **Risk:** In negative gamma (-20.03B), the band can break hard in either direction. Keep positions small. A break of either level is a full exit signal.

---

## Section E: Invalidation Conditions

- **7550 breaks decisively lower** — put pillar has failed. In -20.03B negative gamma, expect cascade selling. Exit all long call positions immediately. Do not fade the break.
- **7580 breaks decisively higher** — call wall at key2 has failed. In negative gamma, buying accelerates above the break. Exit short call positions immediately.
- **Put volume at 7550 rotates to a lower strike intraday** — if the 78K put volume migrates to 7530 or 7520, the pillar is moving and the 7550 thesis is stale.
- **Macro event override** — September 5 2025 recording context mentions jobs numbers causing large intraday swings. Any equivalent event today would override GEX entirely in this environment.

---

## Section F: Caution Notes

| Factor | Status |
|---|---|
| **End of month** | No — 3 June is early month |
| **End of quarter** | No |
| **Monthly expiration** | No — standard weekly Friday |
| **Triple witching** | No |
| **FOMC / Fed day** | Unknown — verify calendar |
| **Abnormally large OI** | ⚠️ Put OI at 7550 (3,876) with 78K volume is elevated. Monitor for condor artifact effect. |
| **Negative gamma magnitude** | ⚠️ **Extreme** — -20.03B is the highest magnitude in the dataset. This is not a normal day. |
| **Two-strike tie** | ⚠️ Key and key2 are essentially equal (3.94B vs 3.92B). No single dominant level. |
| **Tomorrow's GEX — required check** | ❌ **Not done.** Pillar thesis cannot be validated without confirming tomorrow's key strike. If tomorrow's level is at 7550, today's pillar may hold all day. If tomorrow's level is elsewhere, expect drift toward it in the final US afternoon hours. |
| **Charm / delta decay** | Active. Capture at 17:31 BST = 12:31 ET. Mid-session. Charm effects will increase through the afternoon as 0DTE options lose delta from time passage. |
| **Capture time** | 12:31 ET — early afternoon. Approximately 3.5 hours of session remaining. Sufficient time for pin/pillar dynamics to play out, but also enough time for the GEX profile to rotate if tomorrow's level differs. |

> **Teaching point — Abnormal day awareness (GEX Day Trading, How I Recovered transcripts):** The extreme net_gex (-20.03B) and extreme put volume (78K) are both unusually large. Days with abnormally large open interest across many strikes can make price action unpredictable. This day has characteristics of an elevated-risk session. Reduce size accordingly.

---

## Section G: Required Actions Before Trading

1. **Check tomorrow's GEX profile** — is 7550 also the key strike tomorrow? If yes, the pillar is reinforced. If no, the pillar may decay late in session as market makers reposition.
2. **Verify whether 78K put volume is accumulating *at* 7550** (confirming the pillar) or spreading to lower strikes (indicating the level is migrating downward).
3. **Confirm the economic calendar** — FOMC, CPI, or other binary events would override GEX entirely in this -20.03B environment.
4. **Monitor the two-strike contest** — if 7580 GEX begins to dominate over 7550, the structure shifts from a pillar play to a resistance play.
5. **Set hard stop below 7550** — in negative gamma, a clean break of 7550 can cascade. Do not use mental stops; decide the exit level before entering.

---

*Report generated from `daily_gex_summary-concise.csv` and all source transcripts in the Gex directory.*
