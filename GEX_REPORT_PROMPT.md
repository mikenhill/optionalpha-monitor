Please produce today's concise GEX report.

STEP 1 — Read all source teaching transcripts.
Read every .txt file in:
  G:\My Drive\Colab Notebooks\optionalpha-monitor\Gex\
These are the primary source transcripts. Read them all, not just the synopsis.

STEP 2 — Read the concise daily history.
Run the following command in the optionalpha-monitor directory:
  Get-Content "results\daily_gex_summary-concise.csv"
The latest row is today. All prior rows are historical context. Pay attention to the OHLC values at the end and state for yesterday's report, how accurate this report were now that OHLC values are known. So each latest report will have a section for yesterday that relates yesterday's report to what actually happened.

STEP 2B — Fetch full OI table from today's raw JSON.
Run the following in the optionalpha-monitor directory to get the OI breakdown for all key strikes:
  python -c "
import pathlib
from datetime import date
from process_gex_window import load_result, find_api_response, select_strike_window
today = date.today().strftime('%Y%m%d')
files = [f for f in sorted(pathlib.Path('results').glob(today + '_*_SPX_SPX_*.json')) if 'gex_summary' not in f.name]
result = load_result(files[-1])
gex = find_api_response(result, 'market.gex')
gex_data = gex.get('data') or {}
rows = gex_data.get('data') or []
last = gex_data.get('last')
rows, _ = select_strike_window(rows, last)
def v(r,k): return r.get(k) or 0
sorted_rows = sorted(rows, key=lambda r: v(r,'coi')+v(r,'poi'), reverse=True)
print('Strike | Call OI | Put OI | Total OI | Net OI | Abs GEX')
for r in sorted_rows[:10]:
    s=r.get('strike'); c=v(r,'coi'); p=v(r,'poi'); a=round(v(r,'abs')/1e9,3)
    print(s,'|',c,'|',p,'|',c+p,'|',c-p,'|',a,'B')
"
Use this output to identify: (a) the top OI strike and whether it is call-heavy or put-heavy,
(b) the OI character of key2_strike (call-heavy, put-heavy, or balanced),
(c) whether price is sitting between two structural anchors (OI sandwich).
Note: the concise CSV does not carry key2 OI — this step is required every day.

STEP 3 — Produce the report with these six sections.

Section A — Today's values in isolation.
For each field in the latest CSV row, state the value and what it means:
  - last: SPX price at capture time
  - sentiment: % of strikes with net positive GEX (>55% bullish lean, <45% bearish lean)
  - gex_ratio: signed call/put GEX ratio (negative = put-dominated)
  - net_gex: total signed GEX across the window (negative = acceleration risk)
  - key_strike: the highest absolute GEX strike — the primary anchor for the day
  - key_absolute: total GEX magnitude at the key strike
  - key_net: signed net GEX at the key strike (call + put)
  - key_dominance_pct: what % of total window GEX is at the key strike
  - key_call_gex / key_put_gex: call and put GEX at the key strike
  - key_call_oi / key_put_oi: open interest at the key strike
  - key_net_oi: call OI minus put OI (positive = call-heavy, negative = put-heavy)
  - key_call_vol / key_put_vol: intraday volume at the key strike
  - key_vol_net: call vol minus put vol (positive = call flow dominant today)
  - key2_strike / key2_absolute: second-highest GEX strike and its magnitude
  - key2 OI character: from the Step 2B raw JSON lookup — state key2's call OI, put OI,
    net OI, and whether it is a CALL WALL, PUT PILLAR, or balanced
  - top OI strike: the strike with the highest total OI in the window (from Step 2B) —
    state its call OI, put OI, net OI, and distance from current price.
    Note: the top OI strike may differ from the key strike because the proximity-weighted
    GEX algorithm discounts far-from-price strikes. Always identify it explicitly.

Section B — Today vs all prior rows.
Compare today's values against the full history:
  - Is sentiment high, low, or normal versus prior days?
  - Is net_gex more or less negative than prior days?
  - Is key_absolute larger or smaller than prior days (high conviction vs low conviction)?
  - Is key_dominance_pct higher or lower (concentrated vs distributed)?
  - Is key_net_oi more put-heavy or call-heavy than prior days?
  - Is key_vol_net diverging from key_net_oi (intraday flow vs structural positioning)?
  - Has the key_strike changed from yesterday, and what does the shift imply?
  - How close is key2_absolute to key_absolute? Is this a single dominant outlier or a two-strike cluster?

Section C — GEX teaching point mapping.
Using the source transcripts, classify today's setup. Apply ALL of the following checks:

  PIN / MAGNET: key_absolute is a dominant outlier AND key_call_gex and key_put_gex are
  both large AND roughly balanced (key_net close to zero). Price may oscillate around key_strike.
  Qualifier: if key2_absolute is within ~20% of key_absolute, this is a two-strike cluster,
  not a clean single-point pin — state this explicitly.

  PUT PILLAR: key_put_gex and key_put_oi both significantly exceed call equivalents.
  key_net_oi is strongly negative. key_strike may act as support.

  CALL WALL: key_call_gex and key_call_oi both significantly exceed put equivalents.
  key_net_oi is strongly positive. key_strike may act as resistance.

  NEGATIVE GAMMA ACCELERATION: net_gex is significantly negative. Moves in either direction
  may be amplified by market maker hedging (sell into falls, buy into rallies).
  Flag the cascade risk level: if key2_strike is close below key_strike, a break of both
  levels in negative gamma could produce a rapid move.

  GEX SLIDE: gamma exposure is spread across many strikes rather than concentrated.
  key_dominance_pct is low. No single dominant level. Movement may be fast and disjointed.

  POSITIVE GAMMA STABILISING: net_gex is positive or near zero. Sentiment is high.
  Market maker hedging may dampen moves and cause mean reversion.

  VOLUME DIVERGENCE (migration signal): key_vol_net is opposite in sign to key_net_oi.
  Per the transcripts, this may indicate the intraday GEX anchor is drifting, not just
  a sentiment signal. State whether call or put volume dominance is confirmed at the key
  strike or appears to be accumulating at a different level.

  CAPTAIN CONDOR / CONDOR ARTIFACT WARNING: large balanced OI at a single strike may
  reflect condor or iron butterfly positioning rather than directional flow.
  OI alone cannot confirm direction. State this limitation explicitly.

  FULL OI STRUCTURE: Using the Step 2B output, build a table of the top 3-4 OI strikes
  showing call OI, put OI, net OI, character (CALL WALL / PUT PILLAR / balanced), and
  distance from current price. Identify whether price is sitting inside an OI sandwich
  (put pillar below, call wall above). State which level is the true structural ceiling
  and which is the true structural floor, regardless of GEX proximity ranking.
  Explain why the key strike was ranked as KEY by the proximity-weighted algorithm
  even if a closer or higher-OI strike exists (show the decay calculation if relevant).

Section D — Educational trade logic.
The preferred trade style is SHORT PREMIUM with DEFINED RISK (credit spreads and iron butterflies).
All structures must include a bought wing to cap maximum loss. Never naked short options.

For each applicable setup identified in Section C, describe the SHORT PREMIUM equivalent:

  PIN setup → Short Iron Butterfly (primary) or Short Iron Condor (wider, lower credit):
    - Sell ATM call and ATM put at key_strike, buy OTM call and OTM put as wings
    - Net credit collected upfront; max profit if price pins at key_strike at expiry
    - Zero-risk construction (per transcripts):
        Stage 1: when price dips below key_strike, sell an IN-THE-MONEY short put spread for credit
        Stage 2: when price rebounds to key_strike, sell a short call spread at key_strike for credit
        If combined credit >= wing width, maximum risk is zero
        Only attempt this if tomorrow's GEX confirms the same key_strike
    - Entry zone: price at or within 5 pts of key_strike
    - Entry timing: wait for price to stretch slightly beyond key_strike, then enter on reversion

  PUT PILLAR setup → Short Put Spread (credit):
    - Sell a put AT or just below key_strike, buy a further OTM put as protection
    - Example: sell 7550P / buy 7540P for net credit
    - Thesis: put pillar holds as support; both legs expire worthless; keep full credit
    - Entry zone: price at or just below key_strike (7545–7552), after a small overshoot
    - Entry timing: wait for price to touch or briefly break below key_strike, then enter
    - Max loss: width of spread minus credit received (always defined)

  CALL WALL setup → Short Call Spread (credit):
    - Sell a call AT or just above key_strike, buy a further OTM call as protection
    - Example: sell 7580C / buy 7590C for net credit
    - Thesis: call wall holds as resistance; both legs expire worthless; keep full credit
    - Entry zone: price at or just above key2_strike/key_strike
    - Entry timing: wait for price to touch or briefly break above key_strike, then enter on rejection
    - Max loss: width of spread minus credit received (always defined)

  NEG_GAMMA / LOW_CONV → No trade. Do not sell premium into high negative gamma or weak GEX days.
    Selling premium when net_gex is strongly negative risks rapid moves through short strikes.

For all setups state:
  - Specific strikes for the short leg and the bought wing (based on key_strike / key2_strike)
  - Credit expected vs max loss (width minus credit)
  - Hold time: scalp (minutes) or session hold to expiry
  - Whether the setup qualifies for the zero-risk iron butterfly construction

Section E — Invalidation conditions.
State the specific price levels and signals that would invalidate each thesis:
  - Which price level, if broken with momentum, means the pillar/pin has failed?
  - What would a negative gamma cascade look like below key2_strike?
  - What volume or GEX rotation signal would indicate the level is migrating?
  - What macro event would override the GEX setup entirely?

Section F — Caution notes.
Check and state explicitly:
  - Is today end of month, end of quarter, monthly expiration, triple witching, or FOMC day?
    (These days make GEX less reliable — state clearly if any apply.)
  - Is key_absolute unusually large OI across many strikes? (Abnormal days warning.)
  - TOMORROW'S GEX — THIS IS A REQUIRED STEP, NOT OPTIONAL:
    State that tomorrow's GEX profile has not been checked and that pin and iron butterfly
    theses cannot be fully validated without it. The pin may degrade late in the session
    if tomorrow's key strike is at a different level. Market makers begin repositioning
    toward tomorrow's level in the final hours of the current session.
  - Charm / delta decay: note that hedging flows around the key strike change throughout
    the day from time passage alone, independently of price movement. By mid-afternoon
    US time this effect is most acute.
  - Is the capture time early or late in the US session? State the approximate US Eastern
    time and what this means for remaining pin duration.

Section G — Required actions before trading.
List the steps that are explicitly required by the transcripts but not available from the CSV:
  1. Check tomorrow's GEX profile on Option Alpha — is the key_strike the same?
  2. Confirm whether intraday call/put volume is accumulating at key_strike or migrating
     to a different level.
  3. Verify the economic calendar — confirm no FOMC, CPI, or other binary events today.
  4. Monitor the intraday GEX chart for profile rotation during the session.

STEP 4 — Save the report.
Save as a markdown file at:
  G:\My Drive\Colab Notebooks\optionalpha-monitor\analysis\analysis-concise-YYYYMMDD-HHMM.md
Use today's actual date and the current time in the filename.
Example: analysis-concise-20260607-1430.md
