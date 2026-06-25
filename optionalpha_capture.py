import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"
CAPTURE_DIR = BASE_DIR / "captures" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

LOGIN_URL = "https://optionalpha.com/login"

captured_requests = []
request_bodies = {}


def safe_filename(value):
    cleaned = "".join(char if char.isalnum() else "_" for char in value)
    return cleaned[:140].strip("_") or "request"


def should_capture(request):
    resource_type = request.resource_type
    if resource_type in ["xhr", "fetch"]:
        return True

    headers = request.headers
    accept = headers.get("accept", "")
    content_type = headers.get("content-type", "")
    return "application/json" in accept or "application/json" in content_type


def redacted_headers(headers):
    sensitive_names = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-csrf-token",
        "x-xsrf-token",
        "csrf-token",
    }
    return {
        name: "<REDACTED>" if name.lower() in sensitive_names else value
        for name, value in headers.items()
    }


def on_request(request):
    if not should_capture(request):
        return

    try:
        request_bodies[request] = request.post_data
    except Exception:
        request_bodies[request] = None


def on_response(response):
    request = response.request
    if not should_capture(request):
        return

    index = len(captured_requests) + 1
    parsed = urlparse(request.url)
    name = safe_filename(f"{index:04d}_{request.method}_{parsed.netloc}_{parsed.path}")
    body_path = CAPTURE_DIR / f"{name}.response.txt"
    metadata_path = CAPTURE_DIR / f"{name}.json"

    response_body_saved = False
    response_body_error = None

    try:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or "text/" in content_type:
            body = response.text()
            body_path.write_text(body, encoding="utf-8")
            response_body_saved = True
    except Exception as error:
        response_body_error = str(error)

    metadata = {
        "index": index,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "url": request.url,
        "resource_type": request.resource_type,
        "status": response.status,
        "request_headers_redacted": redacted_headers(request.headers),
        "response_headers_redacted": redacted_headers(response.headers),
        "request_post_data": request_bodies.get(request),
        "response_body_saved": response_body_saved,
        "response_body_file": body_path.name if response_body_saved else None,
        "response_body_error": response_body_error,
    }

    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    captured_requests.append(metadata)
    print(f"Captured {index:04d}: {request.method} {request.url} -> {response.status}")


def save_summary(context, page):
    summary_path = CAPTURE_DIR / "summary.json"
    storage_path = CAPTURE_DIR / "storage_state.json"
    cookies_path = CAPTURE_DIR / "cookies_redacted.json"

    context.storage_state(path=str(storage_path))
    storage = json.loads(storage_path.read_text(encoding="utf-8"))

    redacted_cookies = []
    for cookie in storage.get("cookies", []):
        redacted = dict(cookie)
        redacted["value"] = "<REDACTED>"
        redacted_cookies.append(redacted)

    cookies_path.write_text(json.dumps(redacted_cookies, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "final_url": page.url,
        "captured_count": len(captured_requests),
        "capture_dir": str(CAPTURE_DIR),
        "requests": [
            {
                "index": item["index"],
                "method": item["method"],
                "url": item["url"],
                "status": item["status"],
                "resource_type": item["resource_type"],
                "response_body_file": item["response_body_file"],
            }
            for item in captured_requests
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved summary: {summary_path}")
    print(f"Saved storage state: {storage_path}")
    print(f"Saved redacted cookies: {cookies_path}")


def main():
    parser = argparse.ArgumentParser(description="Capture OptionAlpha session or full request/response data")
    parser.add_argument("--session-only", action="store_true", help="Only refresh session cookies, skip interactive capture")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context_kwargs = {}
        if SESSION_FILE.exists():
            context_kwargs["storage_state"] = str(SESSION_FILE)
            print(f"Using existing session: {SESSION_FILE}")

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        print(f"Opening {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        if args.session_only:
            # Session-only mode: wait 20 seconds for login, save cookies, exit
            print("Waiting 20 seconds for you to log in, then saving session cookies...")
            import time
            time.sleep(20)
            context.storage_state(path=str(SESSION_FILE))
            print(f"Saved reusable session: {SESSION_FILE}")
            browser.close()
            return

        # Full capture mode
        input("Log in and navigate manually to the exact page you want to inspect. Press Enter here when ready to START capture...")

        context.storage_state(path=str(SESSION_FILE))
        print(f"Saved reusable session: {SESSION_FILE}")
        print("Capture is now running. Refresh the page or click the controls that load the data you need.")

        page.on("request", on_request)
        page.on("response", on_response)

        input("When you have loaded the target data, press Enter here to STOP capture and save files...")
        save_summary(context, page)
        browser.close()


if __name__ == "__main__":
    main()
