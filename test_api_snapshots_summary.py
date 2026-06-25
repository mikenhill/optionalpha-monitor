"""Test the /api/snapshots/summary endpoint by starting the app in test mode.

Run with: python test_api_snapshots_summary.py
"""
import json

from gex_viewer import app, _db


def get_latest_date():
    with _db() as con:
        row = con.execute(
            "SELECT MAX(ndate) FROM gex_snapshots WHERE symbol='SPX'"
        ).fetchone()
    if not row or not row[0]:
        return None
    s = str(row[0])
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def main():
    date = get_latest_date()
    assert date, "No historical dates found in gex_snapshots"
    print(f"Testing /api/snapshots/summary?date={date}")

    with app.test_client() as client:
        r = client.get(f"/api/snapshots/summary?date={date}")
        assert r.status_code == 200, f"HTTP {r.status_code}"
        data = r.get_json()

    assert data.get("date") == date, "Date mismatch in response"
    rows = data.get("rows", [])
    assert len(rows) > 0, "No rows returned"
    first = rows[0]
    required_keys = {
        "ntime", "spx_last", "sentiment", "gex_ratio", "net_gex", "kcs", "dominance",
        "total_call_gex", "total_put_gex", "key_strike", "key_call_gex", "key_put_gex",
        "total_call_oi", "total_put_oi", "key_call_oi", "key_put_oi",
        "total_call_vol", "total_put_vol", "key_call_vol", "key_put_vol",
        "key2_strike", "key2_abs", "key2_call_vol", "key2_put_vol", "flip",
        "hmm_state", "hmm_label", "is_premarket",
    }
    missing = required_keys - set(first.keys())
    assert not missing, f"Missing keys in first row: {missing}"
    print(f"PASS: /api/snapshots/summary returned {len(rows)} rows with all required keys")


if __name__ == "__main__":
    main()
