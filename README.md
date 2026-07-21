# Trading Alert Dashboard (Dhan + Supertrend/RSI/UT Bot)

A web dashboard connected to your Dhan account. It watches the market,
generates BUY/SELL alerts with a recommended option strike (chosen by Delta,
Gamma, DTE, and liquidity — not just "nearest ATM"), plus a suggested SL/TP.

**You always execute the trade yourself in the Dhan app.** This system never
places an order on your behalf — it's an alert generator and backtester with
a proper screen to look at, not a script you have to read code to use.

## What you'll have when this is running

- A **web page** (in your browser) with 4 sections: Home, Settings, Backtest, Live Alerts
- A **background bot** that keeps checking the market even if you close the browser tab
- **Alerts** showing up on screen (and optionally on your phone via Telegram)

---

## Part 1 — One-time setup on a cloud server

Since your office laptop can't install software, this runs on a small cloud
server instead — it's actually better anyway, since it runs 24/7 without
depending on your laptop staying on.

### 1a. Get a server
Sign up for **DigitalOcean**, **AWS Lightsail**, or **Linode**. Create the
cheapest Ubuntu 24.04 server (~$5-6/month, sometimes called a "droplet" or
"instance"). You'll get an IP address and a way to log in (usually via a
"Console" button in their website, or SSH).

### 1b. Whitelist that server's IP with Dhan
Dhan requires your server's IP to be whitelisted for placing/viewing orders
via API (this system only reads data and shows alerts, but Dhan still expects
your API IP to be set). Go to **web.dhan.co → profile icon → Access DhanHQ
APIs**, and add your server's static IP there.

### 1c. Install Python and the app
Open your server's terminal (via the provider's web console, or SSH from your
laptop using Windows' built-in `ssh` command — no admin rights needed) and run:

```bash
sudo apt update && sudo apt install python3-pip python3-venv unzip -y
```

Then upload this folder to the server. Easiest way with no local tools: zip
this folder, upload it via your cloud provider's file upload / or use `scp`
from a Windows terminal:

```bash
scp -r trading-system youruser@YOUR_SERVER_IP:~/
```

On the server:

```bash
cd ~/trading-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1d. Start the dashboard

```bash
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Then open `http://YOUR_SERVER_IP:8501` in your browser (any browser, any
computer — including your office laptop, no install needed there at all).

To keep it running permanently (so it survives you closing the terminal),
use the systemd instructions at the bottom of this file instead of running
the command directly.

---

## Part 2 — Using the dashboard (no coding needed from here)

### Settings page
1. Paste your **Dhan Client ID** and **Access Token**.
2. Type your instrument name (e.g. "NIFTY") in the search box — matching rows
   from Dhan's official instrument list appear below. Copy the **Security ID**
   from the row you want into the Security ID field.
3. Adjust the strategy numbers if you want (defaults are reasonable to start).
4. Click **Save settings**.

### Backtest page
1. Pick a date range.
2. Click **Fetch data & run backtest** — this pulls real historical prices
   from Dhan and runs the exact same strategy logic that will run live.
3. Review the win rate, profit factor, and the chart before trusting it.
   If it says "no trades generated," try loosening "Indicators required to
   agree" to 2 on the Settings page, or widen the date range.

### Live Alerts page
1. Click **Start bot**. It now runs in the background — checking the market
   every candle, even if you close this browser tab or restart your laptop.
2. Alerts appear here automatically (the page refreshes itself every 15
   seconds) — each one shows the strike, Delta, Gamma, entry premium, SL, and TP.
3. You take the trade manually in the Dhan app using the numbers shown.
4. Click **Stop bot** any time to pause it.

### Telegram alerts (optional)
On the Settings page, add a Telegram bot token and chat ID to also get
alerts on your phone. Message **@BotFather** on Telegram to create a bot and
get a token in under a minute; search "how to get Telegram chat id" if you're
unsure how to find yours.

---

## Keeping it running permanently (recommended once you trust it)

Running the dashboard directly from a terminal stops if you close that
terminal. For real always-on use, run both the dashboard and the background
bot as **systemd services**, which auto-restart if the server reboots.

`/etc/systemd/system/trading-dashboard.service`:
```ini
[Unit]
Description=Trading Dashboard
After=network.target

[Service]
WorkingDirectory=/home/youruser/trading-system
ExecStart=/home/youruser/trading-system/venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
User=youruser

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/trading-daemon.service`:
```ini
[Unit]
Description=Trading Alert Daemon
After=network.target

[Service]
WorkingDirectory=/home/youruser/trading-system
ExecStart=/home/youruser/trading-system/venv/bin/python alert_daemon.py
Restart=always
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trading-dashboard trading-daemon
```

With this setup, use the Settings page to turn the daemon's alerting on/off
(the "daemon_enabled" toggle via Start/Stop buttons still works — the systemd
service just makes sure the process itself never dies).

---

## Important things to know

- **This never places orders.** Every alert ends with "manual execution" —
  you decide whether to actually take each trade in Dhan.
- **Backtest ≠ guaranteed future results.** It validates entry/exit *timing*
  on historical underlying prices — not exact option premium P&L, which also
  depends on IV changes and time decay.
- **Start with "2 of 3 indicators must agree"** on the Settings page to see
  the system actually produce alerts, then tighten to "3 of 3" once you're
  comfortable, since stricter agreement means fewer but higher-quality signals.
- **Security ID matters.** Double check the one you picked on the Settings
  page search actually matches your intended instrument before backtesting
  or going live.
- Your Dhan Access Token and Telegram token are stored in `settings.json` on
  your own server only — never shared anywhere else. Keep server access
  restricted to yourself.
