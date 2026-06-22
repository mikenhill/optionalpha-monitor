import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
    _US_EASTERN = ZoneInfo("America/New_York")
except Exception:
    _US_EASTERN = None

# Bandwidth (in index points) for proximity-weighted GEX key strike selection.
# Gaussian decay: effective_abs = raw_abs * exp(-0.5 * (dist/PROX_BANDWIDTH)^2)
# At PROX_BANDWIDTH pts away, a strike retains ~60% of its raw weight.
# At 2x bandwidth, ~14%. Calibrated for SPX intraday range (~50 pts).
PROX_BANDWIDTH = 50.0


def load_result(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_api_response(result, api_name):
    for item in result.get("data", []):
        if item.get("api") == api_name:
            return item
    raise ValueError(f"Could not find API response: {api_name}")


def value(row, key):
    return row.get(key) or 0


def select_strike_window(rows, last, below=20, above=20):
    filtered = sorted(
        (row for row in rows if row.get("strike") is not None),
        key=lambda row: row["strike"],
    )
    if not filtered:
        raise ValueError("No strike rows found")

    below_rows = [row for row in filtered if row["strike"] < last]
    above_rows = [row for row in filtered if row["strike"] >= last]

    selected_below = below_rows[-below:]
    selected_above = above_rows[:above]

    window = selected_below + selected_above
    if not window:
        raise ValueError("No strikes in window")

    nearest = min(window, key=lambda row: (abs(row["strike"] - last), row["strike"]))
    return window, nearest["strike"]


def summarize_gex(result):
    gex = find_api_response(result, "market.gex")
    gex_data = gex.get("data") or {}
    rows = gex_data.get("data") or []
    last = gex_data.get("last")

    if not rows:
        raise ValueError("market.gex response does not include data.data rows")
    if last is None:
        raise ValueError("market.gex response does not include data.last")

    rows, nearest_strike = select_strike_window(rows, last)

    positive_rows = [row for row in rows if value(row, "total") > 0]
    negative_rows = [row for row in rows if value(row, "total") < 0]
    non_zero_rows = positive_rows + negative_rows

    def proximity_weighted_abs(row):
        """Scale raw abs GEX by Gaussian proximity to last price.

        Strikes near the current price exert more real-world gamma pressure
        than equidistant raw GEX at a far OTM strike. A strike 50 pts away
        retains ~60% weight; 100 pts away retains ~14%.
        """
        dist = abs(value(row, "strike") - last)
        decay = math.exp(-0.5 * (dist / PROX_BANDWIDTH) ** 2)
        return abs(value(row, "abs")) * decay

    highest_abs_row = max(rows, key=proximity_weighted_abs)

    # Key strike balance: signed measure of call vs put GEX at the key strike
    # +100% = pure call wall, 0% = perfect pin, -100% = pure put pillar
    cg_abs = abs(value(highest_abs_row, "cg"))
    pg_abs = abs(value(highest_abs_row, "pg"))
    total = cg_abs + pg_abs
    key_strike_balance = round((cg_abs - pg_abs) / total * 100, 2) if total else None

    # Key strike dominance: what % of total window absolute GEX is at the key strike
    total_abs_gex = sum(abs(value(row, "abs")) for row in rows)
    key_abs = abs(value(highest_abs_row, "abs"))
    key_strike_dominance_pct = round(key_abs / total_abs_gex * 100, 2) if total_abs_gex else None

    # Second-highest absolute GEX strike (also proximity-weighted)
    sorted_by_abs = sorted(rows, key=proximity_weighted_abs, reverse=True)
    second_highest_row = sorted_by_abs[1] if len(sorted_by_abs) > 1 else None
    second_highest_gex_strike = second_highest_row.get("strike") if second_highest_row else None
    second_highest_gex_absolute = abs(value(second_highest_row, "abs")) if second_highest_row else None

    # Key strike OI balance: signed call vs put OI at key strike
    # +100% = all calls, -100% = all puts, 0% = balanced
    ks_coi = value(highest_abs_row, "coi")
    ks_poi = value(highest_abs_row, "poi")
    ks_oi_total = ks_coi + ks_poi
    key_strike_oi_balance = round((ks_coi - ks_poi) / ks_oi_total * 100, 2) if ks_oi_total else None

    # Key strike volume balance: signed call vs put volume at key strike
    ks_cvol = value(highest_abs_row, "cvol")
    ks_pvol = value(highest_abs_row, "pvol")
    ks_vol_total = ks_cvol + ks_pvol
    key_strike_vol_balance = round((ks_cvol - ks_pvol) / ks_vol_total * 100, 2) if ks_vol_total else None

    # Top strike by total OI (call OI + put OI)
    top_oi_row = max(rows, key=lambda row: value(row, "coi") + value(row, "poi"))
    top_oi_strike = top_oi_row.get("strike")
    top_oi_total = value(top_oi_row, "coi") + value(top_oi_row, "poi")

    # Top strike by total volume (call vol + put vol)
    top_vol_row = max(rows, key=lambda row: value(row, "cvol") + value(row, "pvol"))
    top_vol_strike = top_vol_row.get("strike")
    top_vol_total = value(top_vol_row, "cvol") + value(top_vol_row, "pvol")

    positive_count = len(positive_rows)
    negative_count = len(negative_rows)
    non_zero_count = len(non_zero_rows)
    positive_net_value = sum(value(row, "net") for row in positive_rows)
    negative_net_value = sum(value(row, "net") for row in negative_rows)

    # Sum cg and pg across the 40-strike window — consistent with OA's 40-strike chart view.
    # Note: OA's displayed Net GEX value applies additional scaling not documented in the API;
    # our windowed sum is self-consistent across all days and is the correct basis for comparison.
    total_call_gex = sum(value(row, "cg") for row in rows)
    total_put_gex = sum(value(row, "pg") for row in rows)
    net_gex = total_call_gex + total_put_gex
    if abs(total_call_gex) >= abs(total_put_gex):
        gex_ratio = abs(total_call_gex) / abs(total_put_gex) if total_put_gex else None
    else:
        gex_ratio = -(abs(total_put_gex) / abs(total_call_gex)) if total_call_gex else None

    # Weighted mean put strike (gamma-weighted center of put exposure)
    put_gex_weights = [(value(row, "strike"), abs(value(row, "pg"))) for row in rows if value(row, "pg") != 0]
    total_put_gex_weight = sum(w for _, w in put_gex_weights)
    weighted_mean_put_strike_gex = round(sum(s * w for s, w in put_gex_weights) / total_put_gex_weight, 2) if total_put_gex_weight else None

    # OI-weighted mean put strike
    put_oi_weights = [(value(row, "strike"), value(row, "poi")) for row in rows if value(row, "poi") > 0]
    total_put_oi_weight = sum(w for _, w in put_oi_weights)
    weighted_mean_put_strike_oi = round(sum(s * w for s, w in put_oi_weights) / total_put_oi_weight, 2) if total_put_oi_weight else None

    # Volume-weighted mean put strike
    put_vol_weights = [(value(row, "strike"), value(row, "pvol")) for row in rows if value(row, "pvol") > 0]
    total_put_vol_weight = sum(w for _, w in put_vol_weights)
    weighted_mean_put_strike_vol = round(sum(s * w for s, w in put_vol_weights) / total_put_vol_weight, 2) if total_put_vol_weight else None

    # Weighted mean call strike (gamma-weighted center of call exposure)
    call_gex_weights = [(value(row, "strike"), abs(value(row, "cg"))) for row in rows if value(row, "cg") != 0]
    total_call_gex_weight = sum(w for _, w in call_gex_weights)
    weighted_mean_call_strike_gex = round(sum(s * w for s, w in call_gex_weights) / total_call_gex_weight, 2) if total_call_gex_weight else None

    # OI-weighted mean call strike
    call_oi_weights = [(value(row, "strike"), value(row, "coi")) for row in rows if value(row, "coi") > 0]
    total_call_oi_weight = sum(w for _, w in call_oi_weights)
    weighted_mean_call_strike_oi = round(sum(s * w for s, w in call_oi_weights) / total_call_oi_weight, 2) if total_call_oi_weight else None

    # Volume-weighted mean call strike
    call_vol_weights = [(value(row, "strike"), value(row, "cvol")) for row in rows if value(row, "cvol") > 0]
    total_call_vol_weight = sum(w for _, w in call_vol_weights)
    weighted_mean_call_strike_vol = round(sum(s * w for s, w in call_vol_weights) / total_call_vol_weight, 2) if total_call_vol_weight else None

    # Spread between call and put weighted means (skew indicator)
    def _spread(call, put):
        if call is not None and put is not None:
            return round(call - put, 2)
        return None

    call_put_gex_strike_spread = _spread(weighted_mean_call_strike_gex, weighted_mean_put_strike_gex)
    call_put_oi_strike_spread = _spread(weighted_mean_call_strike_oi, weighted_mean_put_strike_oi)
    call_put_vol_strike_spread = _spread(weighted_mean_call_strike_vol, weighted_mean_put_strike_vol)

    return {
        "symbol": gex_data.get("symbol"),
        "last": last,
        "nearest_strike": nearest_strike,
        "positive_gex_bars": positive_count,
        "negative_gex_bars": negative_count,
        "sentiment": round((positive_count / len(rows)) * 100, 4) if rows else 0,
        "gex_ratio": round(gex_ratio, 4) if gex_ratio is not None else None,
        "positive_gex_net_value": round(positive_net_value, 4),
        "negative_gex_net_value": round(negative_net_value, 4),
        "total_call_gex": round(total_call_gex, 4),
        "total_put_gex": round(total_put_gex, 4),
        "net_gex": round(net_gex, 4),
        "highest_absolute_gex_strike": highest_abs_row.get("strike"),
        "highest_absolute_gex_net_gex": value(highest_abs_row, "net"),
        "highest_absolute_gex_absolute_gex": value(highest_abs_row, "abs"),
        "highest_absolute_gex_calls_gex": value(highest_abs_row, "cg"),
        "highest_absolute_gex_puts_gex": value(highest_abs_row, "pg"),
        "highest_absolute_gex_oi_call": value(highest_abs_row, "coi"),
        "highest_absolute_gex_oi_put": value(highest_abs_row, "poi"),
        "highest_absolute_gex_call_vol": value(highest_abs_row, "cvol"),
        "highest_absolute_gex_put_vol": value(highest_abs_row, "pvol"),
        "key_strike_balance": key_strike_balance,
        "key_strike_dominance_pct": key_strike_dominance_pct,
        "key_strike_oi_balance": key_strike_oi_balance,
        "key_strike_vol_balance": key_strike_vol_balance,
        "second_highest_gex_strike": second_highest_gex_strike,
        "second_highest_gex_absolute": second_highest_gex_absolute,
        "top_oi_strike": top_oi_strike,
        "top_oi_total": top_oi_total,
        "top_vol_strike": top_vol_strike,
        "top_vol_total": top_vol_total,
        "weighted_mean_put_strike_gex": weighted_mean_put_strike_gex,
        "weighted_mean_put_strike_oi": weighted_mean_put_strike_oi,
        "weighted_mean_put_strike_vol": weighted_mean_put_strike_vol,
        "weighted_mean_call_strike_gex": weighted_mean_call_strike_gex,
        "weighted_mean_call_strike_oi": weighted_mean_call_strike_oi,
        "weighted_mean_call_strike_vol": weighted_mean_call_strike_vol,
        "call_put_gex_strike_spread": call_put_gex_strike_spread,
        "call_put_oi_strike_spread": call_put_oi_strike_spread,
        "call_put_vol_strike_spread": call_put_vol_strike_spread,
        "ohlc_open": "",
        "ohlc_high": "",
        "ohlc_low": "",
        "ohlc_close": "",
    }


def write_csv(output_path, summary):
    with Path(output_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def append_csv(output_path, summary):
    output_path = Path(output_path)
    fieldnames = list(summary.keys())
    new_date = summary.get("date", "")[:10]

    existing_rows = []
    if output_path.exists():
        with output_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "captured_at" in row and "date" not in row:
                    row["date"] = row.pop("captured_at")
                row_date = row.get("date", "")[:10]
                if row_date != new_date:
                    existing_rows.append(row)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        writer.writerow(summary)


def write_summary_files(input_path, output, include_csv=False, append_path=None):
    input_path = Path(input_path)
    output_path = input_path.with_name(f"{input_path.stem}_gex_summary.json")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    csv_path = None
    if include_csv:
        csv_path = input_path.with_name(f"{input_path.stem}_gex_summary.csv")
        write_csv(csv_path, output)

    if append_path:
        append_csv(append_path, output)

    return output_path, csv_path


def summarize_file(input_path):
    result = load_result(input_path)
    output = summarize_gex(result)
    raw_ts = result.get("captured_at", "")
    try:
        dt = datetime.fromisoformat(raw_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if _US_EASTERN:
            dt = dt.astimezone(_US_EASTERN)
        date_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        date_str = raw_ts
    ordered = {"symbol": output.pop("symbol"), "date": date_str}
    ordered.update(output)
    ordered["source_file"] = str(Path(input_path))
    return ordered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--append-csv")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    output = summarize_file(input_path)

    output_path, csv_path = write_summary_files(
        input_path,
        output,
        include_csv=args.csv,
        append_path=args.append_csv,
    )
    print(f"Sentiment: {output['sentiment']}")
    print(f"GEX ratio: {output['gex_ratio']}")
    print(f"Highest absolute GEX strike: {output['highest_absolute_gex_strike']}")
    print(f"Key strike balance: {output['key_strike_balance']}%")
    print(f"Weighted mean put strike (GEX): {output['weighted_mean_put_strike_gex']}")
    print(f"Weighted mean put strike (OI):  {output['weighted_mean_put_strike_oi']}")
    print(f"Weighted mean put strike (Vol): {output['weighted_mean_put_strike_vol']}")
    print(f"Weighted mean call strike (GEX): {output['weighted_mean_call_strike_gex']}")
    print(f"Weighted mean call strike (OI):  {output['weighted_mean_call_strike_oi']}")
    print(f"Weighted mean call strike (Vol): {output['weighted_mean_call_strike_vol']}")
    print(f"Call/put GEX strike spread: {output['call_put_gex_strike_spread']}")
    print(f"Call/put OI strike spread:  {output['call_put_oi_strike_spread']}")
    print(f"Call/put Vol strike spread: {output['call_put_vol_strike_spread']}")
    print(f"Saved: {output_path}")

    if csv_path:
        print(f"Saved: {csv_path}")
    if args.append_csv:
        print(f"Appended: {args.append_csv}")


if __name__ == "__main__":
    main()
