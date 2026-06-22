# SPX GEX Concise Report — 2026-06-17
**Capture time:** 2026-06-17 07:51 ET (pre-market)
**SPX last:** 7511.35
**Report generated:** 12:54 BST / 07:54 ET

---

## Yesterday's Report vs What Actually Happened (2026-06-16)

**Yesterday's report thesis (analysis-concise-20260616-1450.md):** CALL WALL at 7600. Price was 7563 at capture. Thesis: 7600 acts as resistance. Short call spread 7600C/7610C on a touch and reject. Call wall was building conviction (key_call_vol 11,850 by 09:36 ET). OI sandwich range: 7500 (floor) to 7600 (ceiling). Expiration week caution active.

**What actually happened (OHLC now available):**
- Open: 7548.78 | High: 7564.96 | Low: 7508.68 | **Close: 7511.35**

**Verdict:** The call wall at 7600 was never tested — price never approached it. Instead the day was a sell-off. High was only 7564.96 (13 pts above capture price), then price fell through the OI sandwich and tested the 7500 put pillar floor — low was 7508.68, stopping 8.68 pts above 7500. The floor held. Price closed at 7511.35 — 37 pts below the open.

**What this tells us:**
- The call wall at 7600 provided no actionable entry — price never got near it. The short call spread thesis was structurally correct but the entry condition (touch at 7600) was never triggered.
- The 7500 put pillar was tested (low 7508.68) and **held as support** — it stopped the decline within 9 pts of the level. Price never reached 7500, so the short put spread entry condition (touch or brief break of 7500) was not triggered. The floor held before entry was possible.
- The expiration week caution proved warranted — the Jun 15 close (7554) to Jun 16 close (7511) was a -43 pt move that GEX did not predict directionally.
- **Key lesson:** In expiration week, identifying the structural floor (7500 put pillar) proved more actionable than the ceiling (7600 call wall). Price found the floor, not the ceiling.

---

## Section A — Today's Values in Isolation

**Today's row:** `SPX, 2026-06-17 07:51, last=7511.35`

| Field | Value | Interpretation |
|-------|-------|----------------|
| **last** | 7511.35 | SPX opens at yesterday's close — the session left price exactly here. Pre-market snapshot. |
| **sentiment** | 45.0% | Below neutral. Borderline bearish lean (threshold <45% = bearish). Exactly at the warning line. |
| **gex_ratio** | 1.01 | Call GEX and put GEX are essentially equal (1.01:1). No directional dominance whatsoever. Near-perfectly balanced aggregate GEX. |
| **net_gex** | +0.08B | Near zero — essentially neutral gamma. This is the lowest net_gex reading in the dataset by a large margin. Market makers have no meaningful net gamma bias. Neither stabilising nor accelerating — the market is at an inflection point. |
| **key_strike** | 7495 | Primary GEX anchor — 16.35 pts **below** current price. Unusually, the key strike is below price, not above. |
| **key_absolute** | 3.01B | Moderate magnitude — mid-range historically. |
| **key_net** | -0.04B | Nearly zero at the key strike — call GEX and put GEX are almost exactly balanced at 7495. This is a PIN / MAGNET structure, not a wall or pillar. |
| **key_dominance_pct** | 12.26% | Low-moderate concentration. GEX is distributed across many strikes. |
| **key_call_gex** | 1.49B | Call GEX at 7495 |
| **key_put_gex** | -1.52B | Put GEX at 7495 — nearly equal to call GEX. |
| **key_call_oi** | 4426 | Call OI at 7495 |
| **key_put_oi** | 4531 | Put OI at 7495 — nearly equal to call OI. |
| **key_net_oi** | -105 | Essentially zero — 4426 calls vs 4531 puts. Balanced to within 1%. Classic pin structure. |
| **key_call_vol** | 322 | Very low call volume at 7495 — pre-market, session has not opened yet. |
| **key_put_vol** | 469 | Low put volume — slightly more put than call volume so far. |
| **key_vol_net** | -147 | Marginally put-dominated intraday flow at the key strike — very small sample (pre-market). Not meaningful yet. |
| **key2_strike** | 7500 | Second GEX strike — only 5 pts from key_strike and 11.35 pts below price. |
| **key2_absolute** | 2.34B | 77.7% of key_absolute — extremely close to key. This is a **two-strike cluster** at 7495/7500, not a single dominant pin. |

**key2_strike (7500) OI from Step 2B:**
- Call OI 3122 | Put OI 3587 | Total 6709 | Net OI -465
- Character: **Balanced / mild PUT lean** — nearly equal OI, slight put excess. Put pillar character is modest, not dominant.

**Top OI strike (from Step 2B):**
- **7495**: 4426 call / 4531 put | Total 8957 | Net OI -105 | Abs GEX 3.007B
- Top OI and key_strike are the same. Distance: -16 pts below current price of 7511.
- The highest-OI strike is *below* current price — the GEX anchor is pulling from below, not above.

**Full OI structure (top strikes by total OI):**

| Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX | Character | Distance |
|--------|---------|--------|----------|--------|---------|-----------|----------|
| 7495 | 4426 | 4531 | 8,957 | -105 | 3.007B | **PIN (balanced)** | -16 |
| 7600 | 5426 | 2441 | 7,867 | +2985 | 1.022B | CALL WALL | +89 |
| 7500 | 3122 | 3587 | 6,709 | -465 | 2.336B | Balanced/mild put | -11 |
| 7425 | 2204 | 1753 | 3,957 | +451 | 0.561B | Mild call lean | -86 |

**OI Sandwich:** Price at 7511 sits just above the 7495/7500 cluster. The structural ceiling is now 7600 (call wall, +89 pts away). There is no meaningful put pillar below 7495/7500 — 7425 is the next significant level (-86 pts, mild character). This is an asymmetric structure: tight cluster below (+/-16 pts), distant ceiling above (+89 pts), open space below.

**Why 7495 is key_strike despite being below price:** The proximity-weighted algorithm applies a distance discount — the closer a strike is to price, the higher its weight. 7495 is only 16 pts below vs 7600 which is 89 pts above. Even though 7600 has higher raw OI, the proximity weighting means 7495's GEX contribution dominates after the distance discount. 7600 abs GEX is only 1.022B (vs 3.007B at 7495) after the decay is applied — reflecting that its OI-driven hedging flows are relatively less impactful on today's price action.

---

## Section B — Today vs All Prior Rows

**Sentiment (45.0%):**
- Prior range: 30% (Jun 3) to 100% (Jun 15).
- Today is the second-lowest reading, just above Jun 3's crash day (30%) and Jun 4 (32.5%). Approaching bearish territory. Significant deterioration from yesterday's 52.5%.

**net_gex (+0.08B):**
- Prior range: -20.03B (Jun 3) to +20.99B (Jun 15).
- **Today's +0.08B is by far the lowest (closest to zero) reading in the dataset.** This is a fundamental regime change — the market has essentially no gamma bias. The previous two weeks all had net_gex of at least ±2.36B. Today is at the neutral inflection point.
- Near-zero net_gex is the most dangerous reading for directional assumptions — market makers have no net hedging obligation. Price can move freely in either direction without systematic dampening or amplification.

**key_absolute (3.01B):**
- Prior range: 1.14B to 6.52B. Mid-range — not abnormally concentrated.

**key_dominance_pct (12.26%):**
- Near the low end of the historical range. GEX is distributed — no single dominant level.

**key_net_oi (-105):**
- Prior range: -3478 to +7766. Today is essentially zero — the most balanced key strike OI in the dataset. Pure pin structure with no directional bias.

**key_vol_net (-147):**
- Pre-market reading — not meaningful yet. Will need to be monitored once the session opens.

**key_strike shift:** 7600 (Jun 16) → 7495 (Jun 17). The dominant anchor has dropped 105 pts overnight. This is the largest single-day key_strike drop in the dataset and reflects yesterday's -52 pt close. The market has repriced its structural anchor to match the new price level.

**key2 proximity (77.7%):** key2_absolute is 2.34B vs key_absolute 3.01B = 77.7%. This is the closest key/key2 ratio in the dataset — well above the ~80% two-strike cluster threshold. **7495 and 7500 must be treated as a single two-strike cluster, not two independent levels.** The effective pin zone is 7495–7500, not a single point.

**gex_ratio (1.01):** The closest to 1.0 (perfectly balanced) in the dataset. Jun 2 was 1.11, Jun 9 was -1.04. Today is essentially neutral aggregate GEX — unprecedented in the current dataset.

---

## Section C — GEX Teaching Point Mapping

### ✅ PIN / MAGNET at 7495–7500 — Primary Setup

- key_net_oi at 7495: -105 (4426 call / 4531 put) — virtually perfectly balanced.
- key_net at 7495: -0.04B (1.49B call / -1.52B put) — virtually perfectly balanced GEX.
- key2 at 7500: net OI -465 (mild put lean), 2.34B abs GEX = 77.7% of key.
- **This is a two-strike cluster PIN zone at 7495–7500**, not a single-point pin.
- Per the transcripts (Jack Slocum, Quick Wins): "the call and the put gamma exposure are both pretty balanced, which means that as the price oscillates above or below that particular strike, there's going to be a lot of action for market makers having to hedge, which ultimately makes that price act as a pin and keeps it there throughout the day."
- Per Kirk's video: "I just found a day where... we have very even distribution of call gamma and then put gamma on the bottom side. My thought was that it would continue to move back down to that level — an attracting point."
- Price at 7511 is 11–16 pts above the cluster. The pin is below current price, pulling from below.
- **Qualifier — two-strike cluster:** Key2 at 77.7% of key means this is a 7495/7500 zone, not a clean single-point. Iron butterfly should be centred on 7495 or 7500 with wider wings to capture both.

### ✅ NEAR-ZERO NET_GEX — Critical Neutral / Inflection Warning

- net_gex +0.08B — effectively zero. No gamma bias.
- Per the transcripts: market makers have no systematic hedging obligation in either direction when net_gex is near zero. This is neither a stabilising positive gamma day nor an accelerating negative gamma day.
- **This means the PIN setup is the dominant — and almost only — structural signal today.** There is no directional GEX backdrop to support a call wall or put pillar trade.
- The pin at 7495/7500 works because of the local balanced OI — not because of aggregate gamma stabilising. Be alert: if the pin fails, there is no aggregate gamma backstop.

### ✅ DISTRIBUTED GEX (mild GEX SLIDE character)

- key_dominance_pct 12.26% — low. GEX spread across many strikes.
- No single dominant wall or pillar anywhere in the window.
- Per the transcripts: "gamma exposure is spread across many strikes rather than concentrated... movement may be fast and disjointed." This reinforces the caution on the pin — if the 7495/7500 cluster breaks, there is no next strong level until 7425 (-86 pts below) or 7600 (+89 pts above).

### ❌ NOT: CALL WALL as primary setup
- 7600 has call wall character (net OI +2985) but is 89 pts above price — too far to be actionable today unless price makes a major rally. It registers in the OI table but plays no role in today's intraday structure given proximity.

### ❌ NOT: PUT PILLAR as primary setup
- No strike has strongly put-dominated OI that would act as a defined floor. 7500 has mild put lean (-465) but is part of the same pin cluster. 7425 is too far (-86 pts) and has mild character only.

### ❌ NOT: NEGATIVE GAMMA ACCELERATION
- net_gex +0.08B — not negative. However the near-zero reading means protection from acceleration is also minimal.

### ❌ NOT: VOLUME DIVERGENCE (pre-market — not yet meaningful)
- key_vol_net -147 at pre-market. Monitor once session opens.

### ⚠️ CAPTAIN CONDOR WARNING
- 7495: 4426 call / 4531 put — near-perfectly balanced OI at a strike. This is a textbook condor/iron butterfly positioning artifact. The balanced OI almost certainly includes significant condor short legs (sell 7495C + 7495P as the body of an iron butterfly or condor). This does not invalidate the pin thesis — it reinforces it, because condor sellers are motivated to keep price near the short strike — but it means the OI balance is structural by design, not an emergent flow signal.

---

## Section D — Educational Trade Logic

### Primary: SHORT IRON BUTTERFLY centred on 7495–7500 (PIN zone)

**Setup:** Balanced pin at 7495/7500 (two-strike cluster). net_gex near zero — no directional backdrop. Price 16 pts above the cluster.

**Structure (defined risk, short premium):**
- **Option 1 — Single centre at 7495:** Sell 7495C + Sell 7495P / Buy 7505C + Buy 7485P
  - $10 wide wings. Max profit if price pins at 7495 at expiry.
- **Option 2 — Single centre at 7500:** Sell 7500C + Sell 7500P / Buy 7510C + Buy 7490P
  - $10 wide wings. Max profit if price pins at 7500.
- **Option 3 — Wider wings to capture the cluster:** Sell 7495C + Sell 7500P / Buy 7515C + Buy 7480P
  - Asymmetric/wider construction to capture the 7495–7500 zone. Higher credit, wider max loss.
- Net credit collected upfront. Max profit if price settles between 7490–7510 at expiry.
- **Entry zone:** Price at or within 10 pts of 7495–7500 (currently 7511, i.e., 11–16 pts above)
- **Entry timing:** Wait for price to pull back to 7495–7505 range, or enter now if comfortable with the ~11–16 pt gap. Per Kirk: "I could have had a better entry — I should have waited a little bit longer."

**Zero-risk construction:**
- Two-strike cluster complicates zero-risk construction — the standard approach requires a single clean pin level.
- If price dips to 7495 (Stage 1): sell ITM put spread (e.g., 7505P/7495P) for credit.
- When price rebounds to 7495–7500 (Stage 2): sell call spread at 7500 for credit.
- Combined credit must exceed $10 wing width for zero risk.
- **Tomorrow's GEX must confirm 7495/7500 as key_strike before attempting zero-risk construction.** Given expiration week (Thursday June 19 is approaching), tomorrow's GEX may shift significantly.

**Max loss:** $10 spread width minus credit (defined risk, always capped).
**Hold time:** Session hold to expiry, or scalp — exit at 50% credit profit if available early.

### What NOT to trade today:

- **Do not sell a short call spread at 7600** — 89 pts OTM. Delta is minimal, credit is negligible, and the level has no actionable relevance today.
- **Do not sell a short put spread on the assumption of a put pillar floor** — no strong put pillar exists today. Below 7495/7500, the next support is 7425 (-86 pts).
- **Do not trade directionally** — net_gex +0.08B provides no gamma backstop. A directional credit spread in either direction carries unhedged exposure if the pin fails.

---

## Section E — Invalidation Conditions

### PIN at 7495–7500:
- **Invalidated if:** SPX breaks below 7485 with momentum, or above 7515 with momentum, and sustains the move for 15+ minutes. A clean break through either side of the pin cluster means the pin has failed for the session.
- **Below 7485:** The next structural level is 7425 (-86 pts). With net_gex near zero, there is no gamma dampening to slow a move. A failed pin to the downside could produce a fast 50–80 pt move.
- **Above 7515:** The distributed GEX zone between 7515–7560 provides some friction, but no strong ceiling until 7600 (+89 pts from 7511). A failed pin to the upside in near-zero gamma could also move quickly.

### Near-zero net_gex inflection:
- **Watch for intraday net_gex shift:** If a mid-session capture shows net_gex moving significantly negative (below -2B), the neutral gamma environment has tipped into acceleration territory — exit the iron butterfly immediately as large moves in either direction become more probable.
- **Watch for net_gex moving significantly positive (above +3B):** This would signal a return to stabilising gamma — the pin thesis strengthens.

### Macro override:
- Any Fed speaker, economic release, or unexpected news event would override the GEX setup. With net_gex near zero, GEX provides minimal protection against macro-driven moves today — the threshold for macro override is lower than on high-gamma days.

---

## Section F — Caution Notes

**⚠️ EXPIRATION WEEK — CRITICAL DAY:**
Today is **Tuesday June 17** — three days before June monthly expiration (Friday June 20). Expiration week GEX unreliability is at its peak from Wednesday through Friday. Today is still somewhat reliable, but tomorrow (Wednesday) and especially Thursday/Friday carry significantly elevated noise.

Per Jack Slocum's crash-out lesson: "on the last trading day of the month, the quarter, the year, a triple witching day or FOMC or binary event days... the gamma exposure profile doesn't hold as strong. So I always try to remember that and ensure on those days I'm either not trading or I'm trading with an increased level of caution."

**Friday June 20 = June monthly + quarterly options expiration (triple witching).** Thursday June 19 will already see abnormal positioning. **Consider reducing or stopping 0DTE GEX trades from Thursday onward this week.**

**⚠️ NET_GEX NEAR ZERO — MOST IMPORTANT FLAG TODAY:**
+0.08B is essentially zero. This is unprecedented in the current dataset. The near-zero reading means:
1. No systematic gamma dampening — the market can move freely
2. No gamma acceleration — but also no cushion
3. The PIN setup is the only structural signal. If it fails, there is no fallback.
4. Trade smaller than usual. The iron butterfly is still the appropriate structure, but size down.

**key_absolute (3.01B):** Mid-range — not an abnormal day by OI magnitude alone.

**⚠️ TOMORROW'S GEX — NOT CHECKED (REQUIRED):**
Tomorrow's GEX profile has not been checked. The pin thesis at 7495/7500 **cannot be validated for end-of-day holds** without it. With expiration on Friday, tomorrow's key_strike may shift significantly as positions roll and market makers reposition. Check Option Alpha for tomorrow's key strike before any end-of-day iron butterfly hold.

**Charm / delta decay:**
Capture at 07:51 ET — pre-market. Full session (~6.5 hours) remains. Charm effects are minimal now but will become significant by 13:00–15:00 ET. With a balanced pin at 7495/7500 only 16 pts below price, charm decay on both the call and put OI is symmetric — the pin should remain well-defined throughout the morning. Monitor in the afternoon.

**Capture time = 07:51 ET (pre-market):** This is a pre-open snapshot. The opening print may gap significantly away from 7511 (futures may indicate direction). Refresh with `optionalpha_daily.py` at 10:00–10:30 ET once the opening range establishes.

---

## Section G — Required Actions Before Trading

1. **Re-run `optionalpha_daily.py` at 10:00–10:30 ET** once the US market opening range is established. Today's capture was pre-market (07:51 ET) — the OI and volume picture will change materially in the first 30 minutes of trading. Key question: does key_vol_net at 7495 confirm balanced flow, or is it shifting put-heavy (bearish signal) or call-heavy (bullish signal)?

2. **Check tomorrow's GEX on Option Alpha.** With expiration on Friday, tomorrow's key_strike is critical. If tomorrow shows a different key_strike (e.g., 7450 or 7550), the 7495/7500 pin may degrade in the afternoon as MM flows reposition. Only hold the iron butterfly to expiry if tomorrow confirms the same zone.

3. **Verify the economic calendar.** Check for any Fed speakers, housing data, or other macro events Tuesday June 17. Also note: FOMC minutes or any surprise Fed communication this week would override GEX entirely.

4. **Monitor the intraday GEX chart for net_gex shift.** Today's +0.08B is at the neutral inflection. If it tips negative intraday, the entire setup framework changes — exit open positions and do not enter new ones.

5. **Expiration week — size down.** With Friday being triple witching, treat this week with maximum caution. Reduce contract size. Consider stopping new 0DTE entries from Thursday morning.

---

*Report generated: 2026-06-17 12:54 BST / 07:54 ET*
