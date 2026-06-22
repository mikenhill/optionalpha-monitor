# Option Alpha Monitor Probe

Local Playwright proof-of-concept for logging into Option Alpha, saving an authenticated browser session, navigating to a target page, and saving screenshot/text artifacts.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edit `.env` with your values:

```text
OPTIONALPHA_EMAIL=your-email@example.com
OPTIONALPHA_PASSWORD=your-password
OPTIONALPHA_LOGIN_URL=https://optionalpha.com/login
OPTIONALPHA_TARGET_URL=https://optionalpha.com/the/page/you/want
HEADLESS=false
```

## First run

```powershell
python optionalpha_probe.py
```

If automatic login does not work, complete login manually in the opened browser, then return to the terminal and press Enter. The script saves `session.json`.

## Later runs

```powershell
python optionalpha_probe.py
```

The saved session is reused automatically.

## Outputs

Artifacts are written to:

```text
screenshots/target.png
screenshots/target.txt
```

Use `target.txt` to check whether the values are available as normal page text. If not, the next step is inspecting network/API calls or using screenshot/OCR.

## Capture API calls manually

Use this when you want to log in manually, navigate to a specific page, and capture the API calls the page makes.

```powershell
python optionalpha_capture.py
```

Flow:

1. A visible browser opens.
2. Log in manually.
3. Navigate to the exact Option Alpha page you want to inspect.
4. Return to the terminal and press Enter to start capture.
5. Refresh the page or click the controls that load the data.
6. Return to the terminal and press Enter to stop capture.

Captured files are written to:

```text
captures/YYYYMMDD_HHMMSS/
```

The most useful files are:

```text
summary.json
*.json
*.response.txt
storage_state.json
cookies_redacted.json
```

Security notes:

- `captures/` is ignored by git.
- Request metadata redacts common sensitive headers such as `Authorization` and `Cookie`.
- `storage_state.json` may still contain sensitive session data and should not be shared.
- HAR/capture-style data can contain personal or financial information.

## Daily API run

After `session.json` exists, run:

```powershell
python optionalpha_daily.py --symbol SPX
```

This calls the captured Option Alpha RPC endpoint for `market.maxpain` and `market.gex` using the saved browser cookies from `session.json`.

Outputs are written to:

```text
results/YYYYMMDD_HHMMSS_SYMBOL_XID.json
```

If the saved session expires or Cloudflare requires a new challenge, refresh `session.json` by running:

```powershell
python optionalpha_capture.py
```

## Schedule daily at 14:30 on Windows

Use Task Scheduler with:

```text
Program/script:
G:\My Drive\Colab Notebooks\optionalpha-monitor\.venv\Scripts\python.exe

Add arguments:
optionalpha_daily.py --symbol SPX

Start in:
G:\My Drive\Colab Notebooks\optionalpha-monitor
```

Set the trigger to run daily at `14:30`.
