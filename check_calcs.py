"""Quick check of GEX calcs vs OptionAlpha for 20260617 11:00."""
import json

path = r"g:\My Drive\Colab Notebooks\optionalpha-monitor\results\histgex\20260617\20260617_1100_SPX_histgex.json"
d = json.load(open(path))
uprice = d["uprice"]
print(f"uprice = {uprice}")

all_rows = sorted(
    [r for r in d["data"] if r.get("strike") is not None],
    key=lambda r: r["strike"]
)

# OptionAlpha method: 20 strikes below, 20 strikes above underlying
below = [r for r in all_rows if r["strike"] < uprice]
above = [r for r in all_rows if r["strike"] >= uprice]
rows = below[-20:] + above[:20]
print(f"Strike count: {len(rows)}, range: {rows[0]['strike']} - {rows[-1]['strike']}")

nets = [r.get("net", 0) or 0 for r in rows]
pos_bars = sum(1 for n in nets if n > 0)
neg_bars = sum(1 for n in nets if n < 0)
zero_bars = sum(1 for n in nets if n == 0)
print(f"Positive bars: {pos_bars}, Negative bars: {neg_bars}, Zero: {zero_bars}")

sentiment = round(pos_bars / len(nets) * 100)
print(f"Sentiment: {sentiment}%  (OA shows 40%)")

sum_pos = sum(n for n in nets if n > 0)
sum_neg = sum(n for n in nets if n < 0)
net_total = sum(nets)
ratio = round(sum_neg / sum_pos, 1) if sum_pos else 0
print(f"Ratio: {ratio}x  (OA shows -1.2x)")
print(f"Net: {net_total/1e9:.2f}B  (OA shows -1.7B)")
print(f"  sum_pos={sum_pos/1e9:.3f}B, sum_neg={sum_neg/1e9:.3f}B")

# OI
total_call_oi = sum(r.get("coi", 0) or 0 for r in rows)
total_put_oi = sum(r.get("poi", 0) or 0 for r in rows)
print(f"\nOI - Calls: {total_call_oi/1000:.1f}K (OA: 46K), Puts: {total_put_oi/1000:.1f}K (OA: 47.1K)")
print(f"  P/C Ratio: {total_put_oi/total_call_oi:.2f}  (OA: 1.02)")

# Volume
total_call_vol = sum(r.get("cvol", 0) or 0 for r in rows)
total_put_vol = sum(r.get("pvol", 0) or 0 for r in rows)
print(f"Vol - Calls: {total_call_vol/1000:.1f}K (OA: 268.1K), Puts: {total_put_vol/1000:.1f}K (OA: 312.9K)")
print(f"  P/C Ratio: {total_put_vol/total_call_vol:.2f}  (OA: 1.17)" if total_call_vol else "")
