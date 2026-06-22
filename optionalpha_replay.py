import json
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"


def load_storage_state():
    if not SESSION_FILE.exists():
        raise FileNotFoundError(f"Missing session file: {SESSION_FILE}")
    return json.loads(SESSION_FILE.read_text(encoding="utf-8"))


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


def load_capture(capture_metadata_path):
    capture = json.loads(Path(capture_metadata_path).read_text(encoding="utf-8"))
    post_data = capture.get("request_post_data")
    if not post_data:
        raise ValueError("Capture metadata does not include request_post_data")
    return capture, json.loads(post_data)


def replay(capture_metadata_path):
    storage = load_storage_state()
    session = session_from_storage_state(storage)
    capture, payload = load_capture(capture_metadata_path)

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://app.optionalpha.com",
        "Referer": capture.get("request_headers_redacted", {}).get("referer", "https://app.optionalpha.com/"),
        "User-Agent": capture.get("request_headers_redacted", {}).get("user-agent", "Mozilla/5.0"),
    }

    response = session.post(capture["url"], headers=headers, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")

    output_path = Path(capture_metadata_path).with_name("replay_response.txt")
    output_path.write_text(response.text, encoding="utf-8")
    print(f"Saved response: {output_path}")

    try:
        parsed = response.json()
        print(json.dumps(parsed, indent=2)[:4000])
    except ValueError:
        print(response.text[:4000])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python optionalpha_replay.py captures\\YYYYMMDD_HHMMSS\\0001_POST_app_optionalpha_com__api_request.json")
        raise SystemExit(1)
    replay(sys.argv[1])
