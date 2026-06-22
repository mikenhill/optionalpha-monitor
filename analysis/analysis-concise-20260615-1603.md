# Concise SPX GEX Report — Monday 15 June 2026, 15:59 UK / 10:59 US Eastern

## Section A — Today's values in isolation

**Source row:** `SPX,2026-06-15T15:59:47.621432+01:00`

- **last:** `7553.70`
  - SPX was trading almost exactly on top of the `7550` key strike at capture time, only `+3.70` points above it.

- **sentiment:** `100.0%`
  - Every strike in the selected window has net positive GEX. This is an extremely bullish/stabilising reading versus the prior sample.

- **gex_ratio:** `5.89`
  - Signed call/put GEX ratio is strongly positive. Calls dominate puts by nearly 6:1 on the signed GEX measure.

- **net_gex:** `+20.99B`
  - Total signed GEX is strongly positive. This points toward stabilising/mean-reverting hedging rather than negative-gamma acceleration.

- **key_strike:** `7550`
  - The highest absolute GEX strike and the primary intraday anchor.

- **key_absolute:** `5.34B`
  - Very large absolute GEX at the key strike. This is the largest key absolute value since 5 June in the concise history.

- **key_net:** `+2.73B`
  - The key strike is directionally call-dominated on GEX, not balanced.

- **key_dominance_pct:** `18.05%`
  - `7550` contains 18.05% of the selected window's absolute GEX. This is the most concentrated key strike in the available history.

- **key_call_gex / key_put_gex:** `+4.03B / -1.31B`
  - Call GEX is materially larger than put GEX at `7550`.

- **key_call_oi / key_put_oi:** `4,991 / 1,618`
  - Open interest at `7550` is clearly call-heavy.

- **key_net_oi:** `+3,373`
  - Structural OI at the key strike is call-heavy, consistent with the call-dominated GEX.

- **key_call_vol / key_put_vol:** `48,573 / 17,390`
  - Intraday volume at the key strike is also call-dominant.

- **key_vol_net:** `+31,183`
  - Today’s flow at the key strike confirms the call-heavy structural OI rather than diverging from it.

- **key2_strike / key2_absolute:** `7525 / 2.50B`
  - The second-ranked GEX strike is below spot and is materially smaller than the key strike.
  - `key2_absolute / key_absolute = 2.50 / 5.34 = 46.8%`, so this is not a tight two-strike cluster within ~20% of the key. `7550` is the dominant GEX anchor.

- **key2 OI character from raw JSON:** `7525`
  - Call OI: `4,139`
  - Put OI: `800`
  - Total OI: `4,939`
  - Net OI: `+3,339`
  - Character: **CALL WALL**, not balanced and not a put pillar.

- **Top OI strike from raw JSON:** `7625`
  - Call OI: `12,441`
  - Put OI: `391`
  - Total OI: `12,832`
  - Net OI: `+12,050`
  - Distance from current price: `+71.30` points above spot.
  - Character: **major CALL WALL / structural ceiling**.
  - It is not the key GEX strike because it is far from spot and therefore receives a much lower proximity-weighted score.

## Section B — Today vs all prior rows

- **Sentiment:** Today’s `100.0%` is the highest in the concise history. Prior values were `50.0`, `30.0`, `32.5`, `55.0`, `32.5`, and `55.0`. This is an unusually broad positive-gamma day.

- **Net GEX:** Today’s `+20.99B` is also the strongest net GEX reading in the sample. Prior rows ranged from `-20.03B` to `+2.36B`. This is a major regime shift from the negative GEX days on 3, 5, 8, and 9 June.

- **Key absolute:** Today’s `5.34B` is high. It is below 2 June’s `6.52B` and 5 June’s `6.24B`, but much larger than 4 June’s `1.14B`, 8 June’s `3.20B`, and 9 June’s `2.58B`.

- **Key dominance:** Today’s `18.05%` is the highest recorded in the concise history. The key level is more concentrated than the 10-15% cluster seen previously.

- **Key net OI:** Today’s `+3,373` is much more call-heavy than most prior key strikes. Prior key OI included strongly put-heavy readings such as 3 June `-3,478`, 5 June `-1,808`, and 8 June `-2,942`. The current key is a call wall, not a put support pillar.

- **Intraday flow vs structural OI:** `key_vol_net = +31,183` and `key_net_oi = +3,373` are both positive. There is no bearish volume divergence at the key strike. Intraday flow confirms call accumulation at `7550`.

- **Key strike shift:** The prior row on 9 June had key strike `7450`; today’s key is `7550`. The GEX anchor has shifted `+100` points higher, consistent with SPX trading much higher than the 9 June close and the market rebuilding structure around the 7550 area.

- **Key2 proximity to key:** `7525` has `2.50B` versus `7550` at `5.34B`, or 46.8% of key. This is a secondary lower call-heavy anchor, but not a near-peer two-strike cluster. The primary GEX magnet/wall is `7550`.

### Yesterday / previous report accuracy review

The latest prior concise report in the file is 9 June 2026, because the concise history does not include 10-12 June rows. The 9 June row captured SPX at `7449.76`, key strike `7450`, sentiment `55.0%`, gex_ratio `-1.04`, and net_gex `-0.49B`. Known OHLC for 9 June is:

- **Open:** `7438.66`
- **High:** `7483.15`
- **Low:** `7237.85`
- **Close:** `7386.65`

Assessment:

- **Key-strike pin accuracy:** Poor. Price briefly traded above the `7450` key and reached `7483.15`, but ultimately closed far below the key at `7386.65`.
- **Risk warning accuracy:** The near-flat but slightly negative net GEX correctly warned that the pin was not clean and that downside acceleration risk remained possible. The eventual intraday low of `7237.85` shows a large downside break.
- **Structural lesson:** The 9 June `7450` key did not hold as an end-of-day magnet. The low-conviction/negative-GEX condition mattered more than the nominal key strike.

## Section C — GEX teaching point mapping

### Setup classification

- **Primary classification:** **CALL WALL / POSITIVE GAMMA STABILISING**
- **Secondary classification:** **upper OI sandwich risk**, because the highest OI strikes are above price and strongly call-heavy.
- **Not a clean PIN:** `7550` has dominant absolute GEX, but call GEX and call OI materially exceed put equivalents. The transcripts define pin days as large, balanced call and put GEX/OI at one strike. Today is not balanced enough for a clean pin.
- **Not a PUT PILLAR:** There is no dominant put-heavy support anchor near price in the top OI table.
- **Not NEGATIVE GAMMA acceleration:** Net GEX is strongly positive at `+20.99B`, not negative.
- **Not GEX SLIDE:** Key dominance is high, not low. GEX is not broadly dispersed without a main level.

### Transcript mapping

- **Gamma-rich 0DTE context:** The Mat Cashman interview explains that 0DTE options are highly gamma-sensitive, especially near the money, and that market makers continually hedge delta. Today’s spot price is almost exactly at the `7550` high-GEX strike, so hedging sensitivity is concentrated around the current price.

- **Positive gamma stabilising:** The `More Informed 0DTE Trades` transcript states that negative gamma can amplify moves because hedging follows the trend. Today is the opposite: strongly positive net GEX. This suggests hedging may dampen moves and create mean reversion around major strikes.

- **Call wall:** The `How I Recovered...` and `Using Gamma Exposure to Scalp SPX Intraday` transcripts describe call-heavy strikes acting as resistance when price pushes into or above them. Today `7550`, `7600`, and `7625` all show call-heavy structure.

- **Captain Condor / artifact warning:** The interview cautions that large OI can reflect condors, butterflies, or hedged structures rather than outright directional bets. Today’s OI is heavily call-sided, but direction cannot be inferred from OI alone. It may represent sold call spreads, bought call spreads, hedged inventory, or condor legs.

### Full OI structure from Step 2B

| Strike | Call OI | Put OI | Total OI | Net OI | Character | Distance from spot |
|---:|---:|---:|---:|---:|---|---:|
| 7625 | 12,441 | 391 | 12,832 | +12,050 | CALL WALL | +71.30 |
| 7600 | 8,889 | 298 | 9,187 | +8,591 | CALL WALL | +46.30 |
| 7500 | 7,516 | 1,486 | 9,002 | +6,030 | CALL WALL | -53.70 |
| 7550 | 4,991 | 1,618 | 6,609 | +3,373 | CALL WALL / GEX key | -3.70 |

### OI sandwich / structural anchors

- **Ceiling:** The true structural ceiling is likely the `7600-7625` call-wall stack, not merely the `7550` key strike. `7625` is the top OI strike with `12,832` total OI and `+12,050` net call OI.
- **Floor:** The nearest major lower structural level is `7500`, but it is also call-heavy, not a put pillar. This is not a classic put-below / call-above sandwich. Instead, price is sitting in a **call-heavy corridor** from `7500` through `7625`.
- **Current anchor:** `7550` is the key because it is closest to spot and has the largest absolute GEX after proximity weighting.

### Why 7550 ranks as KEY despite 7625 having higher OI

The proximity-weighted algorithm uses approximately:

`weighted_abs = raw_abs * exp(-0.5 * (distance / 50)^2)`

Using today’s values:

- **7550:** raw abs `5.341B`, distance `3.70`
  - Decay factor ≈ `exp(-0.5 * (3.7 / 50)^2) = 0.997`
  - Weighted ≈ `5.341B * 0.997 = 5.325B`

- **7625:** raw abs `0.849B`, distance `71.30`
  - Decay factor ≈ `exp(-0.5 * (71.3 / 50)^2) = 0.362`
  - Weighted ≈ `0.849B * 0.362 = 0.307B`

So `7625` is structurally important by OI, but its GEX is both smaller and further from price. `7550` is the real immediate hedging anchor.

## Section D — Educational trade logic

Preferred style: **short premium with defined risk only**. No naked short options.

### CALL WALL setup — short call spread candidate

- **Thesis:** `7550` is a call-heavy key strike and `7600-7625` is a larger structural call wall above. Positive GEX may dampen price and create rejection/mean reversion if SPX stretches above the wall.

- **Primary short premium expression:** Short call spread.

- **Example at the key strike:**
  - Sell `7555C` or `7560C`
  - Buy `7565C` or `7570C`
  - Width: `10` points if using 10-wide wings
  - Max loss: spread width minus credit received

- **More conservative structural-ceiling expression:**
  - Sell `7600C`
  - Buy `7610C` or `7620C`
  - Thesis: `7600` is the first major OI call wall above spot.

- **Aggressive upper-ceiling expression:**
  - Sell `7625C`
  - Buy `7635C` or `7640C`
  - Thesis: `7625` is the top OI strike and the strongest structural call wall, but it is far above spot and may offer lower credit unless price rallies.

- **Entry zone:** Wait for SPX to trade into or above `7550-7560` and show rejection, or wait for a stretch toward `7600` if the market rallies.

- **Entry timing:** The transcripts repeatedly warn not to assume the level is a hard wall. Let price stretch slightly beyond the level, then enter on rejection/failed continuation.

- **Hold time:** Scalp to short intraday hold. The teaching examples often take profit in minutes to an hour around GEX levels rather than blindly holding all day.

- **Credit vs max loss:** For a 10-wide spread, any credit collected reduces max loss point-for-point. Example: if credit is `2.00`, max loss is `8.00`.

### PIN / iron butterfly logic — conditional only

Today has high key dominance and spot near `7550`, but the key is call-heavy, not balanced. Therefore, a classic pin trade is lower quality than on a balanced call/put GEX day.

- **Conditional structure:** Short iron butterfly centered at `7550`.
  - Sell `7550C` and `7550P`
  - Buy upper call wing, e.g. `7560C` or `7570C`
  - Buy lower put wing, e.g. `7540P` or `7530P`

- **Qualification:** This does **not** fully qualify for the zero-risk iron butterfly construction unless tomorrow’s GEX also confirms `7550` as a major anchor and the combined credits can equal or exceed the wing width.

- **Zero-risk construction from transcripts:**
  - Stage 1: if price dips below `7550`, sell an in-the-money short put spread for credit.
  - Stage 2: if price rebounds to `7550`, sell a short call spread at `7550` for credit.
  - Only if combined credit >= wing width does risk become zero or near-zero.

### PUT PILLAR setup

No clean put-pillar trade is present. The nearest meaningful lower strikes in the OI table are call-heavy, not put-heavy. A short put spread based solely on `7525` or `7500` would lack the transcript-confirmed put OI support condition.

### NEG_GAMMA / LOW_CONV setup

Not applicable today. Net GEX is strongly positive and key dominance is high.

## Section E — Invalidation conditions

- **7550 call-wall / stabilising thesis invalidation:**
  - A sustained break and hold above `7560-7565` with expanding call volume above `7550` would suggest the key is migrating upward rather than rejecting price.

- **7600 / 7625 structural ceiling invalidation:**
  - A momentum break above `7600`, followed by acceptance above `7625`, invalidates the upper call-wall thesis. If price trades above the top OI wall without rejection, the wall is not functioning as resistance.

- **Pin thesis invalidation:**
  - A clean move away from `7550` that does not revert within the next few candles weakens any `7550` iron butterfly thesis.
  - A shift in intraday GEX chart concentration away from `7550` to `7600` or higher also invalidates the pin.

- **Downside invalidation / cascade watch:**
  - Today is not negative gamma, so a classic negative gamma cascade is not the base case.
  - However, if SPX loses `7525` and then `7500` with momentum while net GEX rotates negative intraday, the setup changes. That would create a potential slide through the lower call-heavy corridor rather than a stable support test.

- **Volume/GEX migration signal:**
  - If new volume accumulates heavily at `7600` or `7625` while `7550` volume fades, the anchor may be migrating upward.
  - If put volume suddenly dominates at `7525`/`7500`, the day’s call-wall interpretation becomes stale.

- **Macro override:**
  - FOMC, CPI, major jobs data, Fed speakers, geopolitical shock, or any binary event can override the GEX structure entirely.

## Section F — Caution notes

- **Calendar risk:** 15 June 2026 is not end of month, end of quarter, or triple witching itself. It is, however, the Monday of monthly expiration week, so OI can build and rotate rapidly into Friday’s expiration.

- **FOMC / macro:** This report has not independently verified today’s economic calendar. Any FOMC/CPI/binary event would reduce reliability of the GEX setup.

- **Abnormal OI warning:** OI is high and call-heavy across several strikes, especially `7625`, `7600`, `7500`, and `7550`. The transcripts warn that abnormal OI across many strikes can make price action less predictable and may reflect condors, spreads, or hedged inventory rather than clean directional intent.

- **Tomorrow’s GEX required:** Tomorrow’s GEX profile has not been checked. Pin and iron butterfly theses cannot be fully validated without it. The transcripts specifically note that late in the session, market makers may begin repositioning toward tomorrow’s key strike if it differs from today’s.

- **Charm / delta decay:** As the Mat Cashman interview explains, charm is delta decay over time. By mid-afternoon US time, hedges tied to expiring 0DTE positions can change rapidly even without price moving. Today’s capture at about `10:59 ET` is still relatively early/mid-session, so there is meaningful time for the profile to rotate before the close.

- **Capture time:** `15:59 UK / 10:59 ET`. This is not a late-day capture. Remaining pin duration is long enough that today’s anchor can migrate materially; do not treat the 10:59 ET snapshot as a closing pin guarantee.

## Section G — Required actions before trading

1. **Check tomorrow’s GEX profile on Option Alpha.** Confirm whether tomorrow also anchors around `7550`, or whether market makers may reposition toward another strike later today.

2. **Confirm intraday volume location.** Verify whether call/put volume is still accumulating at `7550`, or migrating toward `7600` / `7625`.

3. **Verify the economic calendar.** Confirm no FOMC, CPI, jobs, Fed speaker, or other binary event is scheduled today.

4. **Monitor intraday GEX rotation.** If `7550` loses dominance or if the profile shifts upward/downward, adjust or cancel the trade thesis.

5. **Use defined risk only.** Any short premium trade must include a bought wing. No naked short calls or puts.
