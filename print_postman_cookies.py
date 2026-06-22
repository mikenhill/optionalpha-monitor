import json
from datetime import datetime, timezone
from pathlib import Path

session_file = Path(__file__).resolve().parent / "session.json"
storage = json.loads(session_file.read_text(encoding="utf-8"))
needed = {"a5sid", "a5did", "cf_clearance"}
selected = []

for cookie in storage.get("cookies", []):
    if cookie.get("name") in needed:
        selected.append(cookie)

for index, cookie in enumerate(selected, start=1):
    expires = cookie.get("expires", -1)
    if expires and expires > 0:
        expires_label = datetime.fromtimestamp(expires, timezone.utc).isoformat()
    else:
        expires_label = "session"

    print(f"[{index}] {cookie['name']}")
    print(f"domain={cookie.get('domain')}")
    print(f"path={cookie.get('path')}")
    print(f"expires={expires_label}")
    print(f"value={cookie.get('value')}")
    print()

cookie_header = "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in selected)
output_file = Path(__file__).resolve().parent / "postman_cookie_header.txt"
output_file.write_text(cookie_header, encoding="utf-8")
print(f"Full Cookie header written to: {output_file}")
