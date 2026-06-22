# SPX Concise GEX Report — 8 June 2026 (v3 — 14:34 BST capture)

**Captured:** 2026-06-08 14:34 BST (≈ 09:34 ET — ~90 mins after open)
**Report generated:** 2026-06-08 14:35 BST
**SPX Last:** 7438.95
**Script classification:** PUT_PILLAR
**Key strike method:** Proximity-weighted absolute GEX (Gaussian decay, bandwidth = 50 pts)
**History available:** Jun 2, Jun 3, Jun 4, Jun 5, Jun 8 (5 rows; Jun 8 is today)

> **Session context:** This is the third capture of today. The 08:14 ET snapshot showed
> SPX at 7383.74 with an extreme bearish reading (sentiment 7.5%, net_gex -16.49B).
> By 09:34 ET price has rallied ~55 pts to 7438.95. Sentiment has recovered from 7.5% to
> 32.5%. Net_gex has improved from -16.49B to -8.02B. The key_strike has shifted from
> 7400 to 7450 — exactly the proximity-weighted secondary level (key2) from the earlier report.
> The reversion thesis from the morning report has largely played out.

---

## Section A: Today's Values in Isolation

| Field | Value | Interpretation |
|---|---|---|
| `last` | **7438.95** | SPX at capture. Rallied ~55 pts from the 08:14 ET low of 7383.74. Still ~145 pts below Friday's close (7584.31). |
| `sentiment` | **32.5%** | **Bearish lean.** Below the 45% neutral threshold but far above the extreme 7.5% reading from this morning. Recovery underway but not bullish. |
| `gex_ratio` | **-1.69** | Put GEX still dominates but ratio has improved significantly from -3.87 (08:14 ET). Getting closer to Jun 5's -1.70. |
| `net_gex` | **-8.02B** | Negative gamma but substantially improved from -16.49B. Still carries amplification risk but much less extreme. Second mildest negative reading in dataset (Jun 4 was -2.63B). |
| `key_strike` | **7450** | Primary proximity-weighted anchor. 11.05 pts *above* current price. Price is approaching from below. This was key2 in the morning report — it has now become the dominant level as price rallied into it. |
| `key_absolute` | **3.20B** | Same raw magnitude as the morning's 7400 reading (3.20B). Mid-range conviction. |
| `key_net` | **-1.16B** | Net negative at key strike — put GEX (-2.18B) exceeds call GEX (+1.02B) by ~2:1. Less extreme than morning's -1.91B at 7400. |
| `key_dominance_pct` | **10.26%** | Lowest in the dataset. GEX is relatively distributed across the window. Not a strong single-point concentration. |
| `key_call_gex` | **+1.02B** | Meaningful call GEX at 7450 — nearly double the morning's +0.64B at 7400. More balanced structure emerging. |
| `key_put_gex` | **-2.18B** | Large put GEX at 7450. Still dominant but ratio is narrowing vs morning (morning was 4:1, now ~2:1). |
| `key_call_oi` | **2,581** | Moderate call OI. Same contracts as seen in morning data for this strike. |
| `key_put_oi` | **5,523** | Large put OI at 7450. Substantially less than the 8,279 put OI at 7400 this morning. |
| `key_net_oi` | **-2,942** | Put-heavy but improved significantly from -6,198 this morning. More moderate structural positioning. |
| `key_call_vol` | **8,245** | **Very large call volume at 7450.** This is the standout figure — 8,245 call contracts traded intraday at 7450. |
| `key_put_vol` | **2,039** | Moderate put volume. Much lower than call volume. |
| `key_vol_net` | **+6,206** | **Strongly call-dominant intraday flow.** Call volume exceeds put volume by 6,206 contracts at the key strike. This is the largest absolute vol_net divergence in the dataset (prior largest was Jun 2's +17,906 on a bullish day, Jun 3's -73,614 on an extreme bearish day). |
| `key2_strike` | **7400** | Second proximity-weighted anchor — the morning's key_strike. 38.95 pts below current price. |
| `key2_absolute` | **2.44B** | key2/key ratio = 2.44/3.20 = **0.76** — this is a fairly tight two-strike cluster. Key2 is within 24% of key_absolute. |

---

## Section B: Today vs Prior Days

| Metric | Jun 2 | Jun 3 | Jun 4 | Jun 5 | **Jun 8** | Assessment |
|---|---|---|---|---|---|---|
| `last` | 7595.78 | 7560.13 | 7553.68 | 7584.31 | **7438.95** | Still ~145 pts below Friday. Large gap but rally underway. |
| `sentiment` | 50.0% | 30.0% | 32.5% | 55.0% | **32.5%** | Matches Jun 4 exactly. Moderate bearish — not extreme. |
| `gex_ratio` | +1.11 | -3.12 | -1.78 | -1.70 | **-1.69** | Almost identical to Jun 5 (-1.70) and Jun 4 (-1.78). Mid-range negative. |
| `net_gex` | +2.36B | -20.03B | -2.63B | -13.14B | **-8.02B** | Improved dramatically from morning. Second mildest negative reading. |
| `key_strike` | 7600 | 7550 | 7525 | 7550 | **7450** | Still 100–150 pts below prior week levels. Reflects the gap-down. |
| `key_absolute` | 6.52B | 3.94B | 1.16B | 6.24B | **3.20B** | Mid-range. Matches the range seen on Jun 3 (3.94B). |
| `key_dominance_pct` | 14.91% | 10.13% | 12.17% | 12.27% | **10.26%** | Lowest in dataset. More distributed GEX profile. |
| `key_net_oi` | +487 | -3,478 | -311 | -1,808 | **-2,942** | Moderately put-heavy. Between Jun 5 (-1,808) and Jun 3 (-3,478). |
| `key_vol_net` | +17,906 | -73,614 | +1,901 | +954 | **+6,206** | **Strongly call-dominant.** Second largest positive vol_net in dataset behind Jun 2's exceptional +17,906. A very significant intraday call flow signal on a bearish-lean day. |
| `key2_absolute` | 3.39B | 3.92B | 1.16B | 5.29B | **2.44B** | key2/key = 0.76 — **two-strike cluster.** 7400 and 7450 are both active levels. |

### Key observations vs prior days

**1. The morning's extreme readings have normalised substantially.** Sentiment recovered from 7.5% → 32.5%. net_gex improved from -16.49B → -8.02B. gex_ratio improved from -3.87 → -1.69. The gap-down panic has partially unwound.

**2. key_strike has migrated from 7400 to 7450.** Price rallied ~55 pts from the morning low and the dominant GEX anchor has shifted up to 7450, with 7400 now the secondary level (key2). This migration is exactly what the transcripts describe — the GEX anchor follows price as intraday volume builds at different strikes.

**3. key_vol_net at +6,206 is a strong call flow signal.** 8,245 call contracts vs 2,039 put contracts at 7450 intraday. This is directionally significant — aggressive call buying at the key strike on a day that opened with extreme bearish sentiment. Per the transcripts, intraday call volume accumulating at the key strike reinforces the magnet/reversion thesis upward.

**4. Two-strike cluster at 7400/7450.** key2/key = 0.76 — within the 20% proximity threshold. Per the prompt criteria, this is a two-strike cluster, not a clean single-point pin. Price may oscillate between 7400 and 7450 rather than pinning cleanly at one level.

**5. key_dominance_pct at 10.26% is the lowest in dataset.** GEX is more distributed than prior days. This reduces the strength of any single-level pin thesis.

---

## Section C: GEX Teaching Point Mapping

| Teaching Point | Status | Evidence |
|---|---|---|
| **PIN / Magnet at 7450** | ⚠️ Partial — two-strike cluster | key_absolute 3.20B, key_net -1.16B. Not balanced (put still dominant 2:1) but improving from morning. key2_absolute = 2.44B (76% of key) — **this is a two-strike cluster, not a clean pin.** Price may oscillate between 7400 and 7450 rather than pinning at one level. |
| **PUT PILLAR at 7450** | ✅ Primary — price approaching from below | key_put_gex -2.18B, key_put_oi 5,523, key_net_oi -2,942. Put structure dominates. 7450 is 11 pts above current price — acting as a ceiling that may cap or attract price. |
| **CALL WALL** | ❌ No | No call-dominant strike in window. |
| **Negative Gamma Acceleration** | ⚠️ Active but reduced | net_gex -8.02B. Amplification risk persists but significantly improved from -16.49B. Moves are still directionally reinforced by MM hedging but less violently so. |
| **GEX Slide** | ⚠️ Mild risk | key_dominance_pct 10.26% is the lowest in dataset. GEX is more spread out than prior days. No single overwhelming concentration. The two-strike cluster (7400/7450) means movement between them may be choppy rather than directional. |
| **Positive Gamma Stabilising** | ❌ No | net_gex still negative at -8.02B. |
| **Volume Divergence** | ✅ Strong bullish signal | key_vol_net +6,206. 8,245 call contracts at 7450 vs 2,039 puts. Per the transcripts: large intraday call volume accumulating at the key strike when structural OI is put-heavy (key_net_oi -2,942) is a migration signal — fresh money is buying calls at 7450, suggesting the level is the upside magnet for the session. |
| **Captain Condor / Condor Artifact** | ⚠️ Probable at both strikes | 5,523 put OI at 7450 and 2,044+ at 7400 likely contains condor short put legs accumulated when price was higher. Particularly relevant at 7400 where the morning's 8,279 put OI was largely pre-existing. OI cannot confirm directional intent — the large call *volume* (+6,206) is more informative as fresh intraday flow. |
| **Cascade risk below 7400** | ✅ Active | In -8.02B negative gamma, a break of 7400 (key2) would remove both cluster anchors. Amplified selling below 7400. However, the morning's test of 7383 and recovery suggests 7400 has held as support. |

### Dominant classification: **Two-strike cluster (7400/7450) — approaching key strike from below with strong call volume signal**

Price at 7438.95 is 11 pts below 7450 with 8,245 call contracts traded intraday there — the strongest call volume signal in the dataset relative to a bearish structural backdrop. The 7400 level acted as support during the morning gap-down (low ~7383) and price has rallied back into the 7400–7450 range. The two-strike cluster means 7450 is the near-term ceiling/magnet and 7400 is the floor.

> **Teaching point (Quick Wins, Using GEX to Scalp):** The two-strike oscillation pattern is explicitly described — price bounces between the two GEX bars, creating entry opportunities at each extreme. Short put spreads when price touches the lower anchor (7400), short call spreads when it touches the upper anchor (7450). The session becomes a range-fade strategy.

> **Teaching point (Zero Risk 0DTE):** The zero-risk iron butterfly construction is now relevant if call GEX balance continues improving. Stage 1 (ITM short put spread) may already be executable near 7400; Stage 2 (short call spread at 7450) would complete the butterfly when price reaches 7450.

> **Teaching point (More Informed 0DTE):** The large intraday call volume at 7450 (+6,206 net) is precisely the "intraday volume spike at a strike" signal that the transcript uses to identify the session's gravitational centre. This is a high-conviction signal that 7450 is today's primary magnet.

---

## Section D: Educational Trade Logic

> **Educational examples only. Not financial advice.**
> **net_gex -8.02B: negative gamma is still active — size conservatively.**

### Setup 1: Range fade — Short Call Spread at 7450 (credit, defined risk)

**Thesis:** Price is 11 pts below 7450 and rallying toward it. 8,245 call contracts traded at 7450 today — the key strike is the session's upside magnet. In -8.02B negative gamma, if price reaches and stalls at 7450, market maker hedging reverses and sells into the move. A short call spread at 7450 collects premium on the expectation that 7450 caps the move.

| Parameter | Detail |
|---|---|
| **Structure** | Short call spread |
| **Short leg** | Sell 7450C (at key strike) |
| **Long leg** | Buy 7460C (10 pts above — defined risk wing) |
| **Net credit** | Collect spread premium |
| **Max profit** | Full credit — if price closes at or below 7450 |
| **Max loss** | 10 pts minus credit received |
| **Entry zone** | 7448–7455 — wait for price to reach or briefly pierce 7450 |
| **Entry timing** | Do not enter early. Wait for price to touch or slightly overshoot 7450, then enter on the first sign of stall or rejection. Per transcripts: "wait for the stretch, then enter on the reversion." |
| **Target** | Price fades back to 7435–7445. Close at 50–70% of max credit. |
| **Hold time** | Scalp — 20–45 minutes. |
| **Stop** | Hard stop if price closes above 7460. |

### Setup 2: Range support — Short Put Spread at 7400 (credit, defined risk)

**Thesis:** 7400 has acted as support today (morning low ~7383, recovered). In the two-strike cluster, 7400 is the floor. A short put spread at 7400 profits if 7400 continues to hold.

| Parameter | Detail |
|---|---|
| **Structure** | Short put spread |
| **Short leg** | Sell 7400P (at key2 strike / morning support) |
| **Long leg** | Buy 7390P (10 pts below — defined risk wing) |
| **Net credit** | Collect spread premium |
| **Max profit** | Full credit — if price closes at or above 7400 |
| **Max loss** | 10 pts minus credit received |
| **Entry zone** | 7395–7405 — if price pulls back toward 7400 |
| **Entry timing** | Only if price revisits 7400 zone. Do not chase downward. |
| **Target** | Price holds above 7400 and reverts toward 7430–7450. Close at 50–70% of max credit. |
| **Hold time** | Scalp to session. |
| **Stop** | Hard stop at 7385. Do not hold through a break of 7385. |

### Setup 3: Zero-risk Iron Butterfly (conditional — requires tomorrow's GEX confirmation)

**Thesis:** If price oscillates between 7400 and 7450, a staged iron butterfly can be constructed at near-zero risk.

- **Stage 1 (already possible if price revisits 7400):** Sell ITM put spread — sell 7450P / buy 7440P for credit. Enter when price dips toward 7400.
- **Stage 2:** When price rebounds to 7450, sell 7450C / buy 7460C for additional credit.
- **If combined credit ≥ 10 pts (spread width):** maximum risk = zero.
- **Qualification check:** key_net at 7450 = -1.16B. Not yet balanced enough for a high-confidence pin. Proceed only if tomorrow's GEX confirms 7450 as the key strike. **This check is mandatory.**

---

## Section E: Invalidation Conditions

- **7460 breaks with momentum (Setup 1 — call spread):** The 7450 cap has failed. Market maker hedging is buying the rally (negative gamma), amplifying the move higher. Exit the short call spread immediately. Do not hold above 7460.
- **7385 breaks (Setup 2 — put spread):** The morning's support low (~7383) has failed. The 7400 put pillar is not holding. Exit immediately. In -8.02B negative gamma, a break of 7385 can accelerate toward 7350 rapidly.
- **7350 breaks (cascade level):** Below key2 with no remaining structural anchor. In negative gamma, selling accelerates. No new positions below 7350.
- **key_vol_net turns negative at 7450:** If put volume at 7450 starts accumulating (vol_net reverses from +6,206 toward negative), the call flow signal is unwinding. The 7450 magnet thesis is weakening. Do not enter Setup 1 if this occurs.
- **Volume migrating to 7500+:** If the OA live GEX chart shows a growing bar above 7450 (especially at 7475–7500), the session's magnet is shifting upward. The 7400–7450 range fade is no longer valid — price has broken structure.
- **Any macro event:** In -8.02B negative gamma, surprise news still produces amplified moves. Confirm economic calendar before entering (see Section G).

---

## Section F: Caution Notes

| Factor | Status |
|---|---|
| **End of month** | No — 8 June |
| **End of quarter** | No |
| **Monthly expiration** | No |
| **Triple witching** | No |
| **FOMC / binary event** | ⚠️ **Unverified — check before trading.** Negative gamma amplifies macro-driven moves. |
| **Weekend gap-down** | ⚠️ Monday following ~145 pt gap-down. Option chain repriced. Intraday GEX profiles on gap days remain less stable through the full session — not just the open. |
| **key_dominance_pct** | ⚠️ **10.26% — lowest in dataset.** GEX is more distributed than prior days. The two-strike cluster reduces single-point pin confidence. |
| **Two-strike cluster** | ⚠️ key2/key = 0.76. 7400 and 7450 are both significant. Price may oscillate between them rather than pinning at one. Range-fade is more appropriate than a single directional thesis. |
| **Captain Condor at 7400/7450** | ⚠️ Large put OI at both strikes likely contains condor short put legs. Intraday call *volume* (+6,206 at 7450) is more reliable as a directional signal than OI. |
| **Tomorrow's GEX — REQUIRED, NOT DONE** | ❌ **Not checked.** Pin and iron butterfly theses cannot be validated without tomorrow's GEX. If tomorrow's key strike is below 7450, market makers will begin repositioning away from 7450 during the afternoon session (typically 13:00–14:30 ET). The two-strike range trade may lose its anchors. **Do not attempt the zero-risk iron butterfly without this check.** |
| **Charm / delta decay** | Capture at 09:34 ET. ~5.25 hours of session remaining. Charm effects will intensify significantly after 13:00 ET. By 14:00–14:30 ET, delta decay at 7450 will meaningfully change market maker hedging flows. Early entries in the 09:30–11:00 ET window carry the most pin duration. |
| **Capture time** | **09:34 ET — early-to-mid morning session.** Good remaining pin duration if tomorrow's GEX confirms. However this is still a gap-down Monday — profiles can continue rotating through the morning. |

> **Teaching point — Two-strike range (Quick Wins, Using GEX to Scalp):** Kirk explicitly describes the two-bar oscillation setup — "price bounces between the two big GEX bars." The key discipline is fading each extreme rather than trying to predict which bar will win. Short call spreads at 7450, short put spreads at 7400. Neither position held through the opposite extreme.

> **Teaching point — Gap-down Monday (How I Recovered, GEX Day Trading):** The transcripts warn about "abnormal" days where GEX is less reliable. A 145-pt gap-down that has partially recovered by 09:34 ET is not a normal session. The morning's extreme readings (sentiment 7.5%, net_gex -16.49B) have normalised but the session is still structurally different from the prior week. Reduce size from normal levels.

---

## Section G: Required Actions Before Trading

1. **Check tomorrow's (9 June) GEX on Option Alpha** — is 7450 still the dominant strike? Is 7400 still the secondary? If tomorrow's key is below 7400, the range-fade thesis weakens materially. The zero-risk iron butterfly (Stage 1 + Stage 2) requires tomorrow's GEX to confirm the same anchor. **This is mandatory before any position.**

2. **Confirm intraday volume distribution on the live OA GEX chart** — the +6,206 call vol_net at 7450 is a strong signal but was captured at 09:34 ET. Verify it has held or increased. If put volume has reversed the net to negative, the call-magnet thesis is weakening. If a new bar has grown above 7450, the upper bound has shifted.

3. **Verify the economic calendar** — confirm no FOMC, Fed speakers, CPI, NFP, or other binary events today. At -8.02B net_gex, a macro surprise still produces amplified moves.

4. **Monitor the 7400/7450 range intraday** — the two-strike cluster means the actionable levels are clear. Watch for:
   - Price approaching 7450 → potential short call spread entry (Setup 1)
   - Price pulling back toward 7400 → potential short put spread entry (Setup 2)
   - A decisive break of either level with volume → exit and stand aside

5. **Note capture time vs current time** — this report was captured at 09:34 ET. If you are reading this significantly later in the session (e.g. 12:00+ ET), charm decay is already accelerating at 7450. Rerun `optionalpha_daily.py` to get a fresh snapshot before acting.

---

*Report generated from `daily_gex_summary-concise.csv` (5 rows: Jun 2–8, latest capture 14:34 BST / 09:34 ET) and all source transcripts in `Gex/`.*
*Script classification: PUT_PILLAR | key_strike: 7450 (proximity-weighted) | net_gex: -8.02B | sentiment: 32.5%*
*Morning v2 report (7383.74 / 7400 key): reversion thesis has largely played out — price rallied ~55 pts.*
