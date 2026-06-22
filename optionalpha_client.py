import json
from pathlib import Path
from time import time

import requests

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"
API_URL = "https://app.optionalpha.com/api/request"
REFERER = "https://app.optionalpha.com/screener?symbols=SPX%2CXSP"


def load_storage_state(session_file=SESSION_FILE):
    session_path = Path(session_file)
    if not session_path.exists():
        raise FileNotFoundError(f"Missing session file: {session_path}")
    return json.loads(session_path.read_text(encoding="utf-8"))


def session_from_storage_state(storage):
    session = requests.Session()
    for cookie in storage.get("cookies", []):
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def build_rpc_payload(symbol, xid):
    tid_base = int(time() * 1000)
    return [
        {
            "t": "rpc",
            "tid": f"{tid_base}-10070",
            "api": "market.maxpain",
            "args": [{"symbol": symbol, "xid": xid}],
        },
        {
            "t": "rpc",
            "tid": f"{tid_base}-10071",
            "api": "market.gex",
            "args": [symbol, xid],
        },
    ]


def call_optionalpha_api(payload, session_file=SESSION_FILE):
    storage = load_storage_state(session_file)
    session = session_from_storage_state(storage)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://app.optionalpha.com",
        "Referer": REFERER,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    response = session.post(API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_market_data(symbol="SPX", xid="SPX_20260602", session_file=SESSION_FILE):
    payload = build_rpc_payload(symbol, xid)
    return call_optionalpha_api(payload, session_file)
