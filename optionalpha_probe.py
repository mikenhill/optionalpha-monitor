import os
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

LOGIN_URL = os.getenv("OPTIONALPHA_LOGIN_URL", "https://optionalpha.com/login")
TARGET_URL = os.getenv("OPTIONALPHA_TARGET_URL", "https://optionalpha.com/")
EMAIL = os.getenv("OPTIONALPHA_EMAIL", "")
PASSWORD = os.getenv("OPTIONALPHA_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"


def maybe_fill_login(page):
    if not EMAIL or not PASSWORD:
        return False

    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[name='username']",
        "input[autocomplete='username']",
    ]
    password_selectors = [
        "input[type='password']",
        "input[name='password']",
        "input[autocomplete='current-password']",
    ]

    email_locator = None
    password_locator = None

    for selector in email_selectors:
        locator = page.locator(selector).first
        if locator.count() > 0:
            email_locator = locator
            break

    for selector in password_selectors:
        locator = page.locator(selector).first
        if locator.count() > 0:
            password_locator = locator
            break

    if not email_locator or not password_locator:
        return False

    email_locator.fill(EMAIL)
    password_locator.fill(PASSWORD)

    submit = page.locator("button[type='submit'], input[type='submit']").first
    if submit.count() > 0:
        submit.click()
    else:
        password_locator.press("Enter")

    return True


def save_page_artifacts(page, label):
    safe_label = label.replace("/", "_").replace(":", "_")
    screenshot_path = SCREENSHOT_DIR / f"{safe_label}.png"
    text_path = SCREENSHOT_DIR / f"{safe_label}.txt"
    page.screenshot(path=str(screenshot_path), full_page=True)
    text_path.write_text(page.locator("body").inner_text(timeout=10000), encoding="utf-8")
    print(f"Saved screenshot: {screenshot_path}")
    print(f"Saved page text: {text_path}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context_kwargs = {}
        if SESSION_FILE.exists():
            context_kwargs["storage_state"] = str(SESSION_FILE)
            print(f"Using saved session: {SESSION_FILE}")

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        if not SESSION_FILE.exists():
            print(f"Opening login page: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            filled = maybe_fill_login(page)

            if filled:
                print("Submitted login form. Waiting for navigation/network idle...")
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except PlaywrightTimeoutError:
                    print("Network idle timed out; continuing so you can inspect the browser.")
            else:
                print("Could not identify login fields automatically.")

            if not HEADLESS:
                input("Complete login in the browser if needed, then press Enter here to save the session...")

            context.storage_state(path=str(SESSION_FILE))
            print(f"Saved session: {SESSION_FILE}")

        print(f"Opening target page: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            print("Network idle timed out on target page; continuing.")

        print(f"Final URL: {page.url}")
        save_page_artifacts(page, "target")

        browser.close()


if __name__ == "__main__":
    main()
