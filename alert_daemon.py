"""
alert_daemon.py
Runs continuously (started from the dashboard or via systemd) and:
  1. Re-reads settings.json every cycle - so changes you make in the
     Settings page take effect within one candle, no restart needed
  2. Checks daemon_enabled - if you flip it off from the dashboard, this
     process idles instead of exiting, so starting again is instant
  3. On a new closed candle, runs the same signal engine as the backtester
  4. On a BUY/SELL signal, fetches the live option chain, picks the best
     strike, computes SL/TP, and writes an alert (+ optional Telegram)

This file NEVER calls place_order() - alerts only, execution stays manual.
"""

import time
import logging
import sys
from datetime import datetime, timedelta

import requests

from shared.settings_store import load_settings
from shared.alerts_store import append_alert, write_heartbeat
from core.dhan_data import get_client, fetch_historical, fetch_expiry_list, polite_option_chain_fetch
from core.signal_engine import generate_signals
from core.option_selector import select_best_strike, pick_expiry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("alert_daemon")


def send_telegram(settings: dict, text: str):
    if not settings.get("telegram_bot_token") or not settings.get("telegram_chat_id"):
        return
    url = f"https://api.telegram.org/bot{settings['telegram_bot_token']}/sendMessage"
    try:
        requests.post(url, data={"chat_id": settings["telegram_chat_id"], "text": text}, timeout=10)
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def run_once(dhan, settings: dict, last_seen_bar_time):
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

    df = fetch_historical(dhan, settings, from_date, to_date)
    if df.empty:
        write_heartbeat("warning", "No data returned from Dhan this cycle")
        return last_seen_bar_time

    latest_bar_time = df.index[-1]
    if last_seen_bar_time is not None and latest_bar_time <= last_seen_bar_time:
        write_heartbeat("ok", f"Watching {settings['underlying_symbol']} - no new candle yet")
        return last_seen_bar_time

    df = generate_signals(df, settings)
    last_row = df.iloc[-1]
    signal = last_row["signal"]

    if signal in ("BUY", "SELL"):
        log.info(f"Signal fired: {signal} at {latest_bar_time}, price {last_row['close']:.2f}")

        expiries = fetch_expiry_list(dhan, settings)
        expiry = pick_expiry(expiries, settings)

        if expiry is None:
            alert = {
                "type": "no_strike", "signal": signal, "underlying_price": float(last_row["close"]),
                "bar_time": str(latest_bar_time),
                "reason": f"No expiry within DTE window [{settings['min_dte']},{settings['max_dte']}]",
            }
            append_alert(alert)
        else:
            chain = polite_option_chain_fetch(dhan, settings, expiry)
            rec = select_best_strike(signal, chain, expiry, settings)

            if rec is None:
                alert = {
                    "type": "no_strike", "signal": signal, "underlying_price": float(last_row["close"]),
                    "bar_time": str(latest_bar_time),
                    "reason": "No strike passed delta/OI/spread filters",
                }
                append_alert(alert)
            else:
                alert = {
                    "type": "trade_signal", "signal": signal,
                    "underlying_symbol": settings["underlying_symbol"],
                    "underlying_price": float(last_row["close"]),
                    "bar_time": str(latest_bar_time),
                    "votes": int(last_row["bull_votes"] if signal == "BUY" else last_row["bear_votes"]),
                    **rec.as_dict(),
                }
                append_alert(alert)
                send_telegram(settings, f"{signal} SIGNAL - {settings['underlying_symbol']} "
                                         f"@ {last_row['close']:.2f}\n\n{rec.as_alert_text()}")

    write_heartbeat("ok", f"Watching {settings['underlying_symbol']} - last checked candle {latest_bar_time}")
    return latest_bar_time


def main():
    last_seen_bar_time = None
    dhan = None
    log.info("alert_daemon process started")
    write_heartbeat("starting", "Daemon process started")

    while True:
        settings = load_settings()

        if not settings.get("daemon_enabled"):
            write_heartbeat("paused", "Daemon is idle - enable it from the Live Alerts page")
            time.sleep(5)
            continue

        if not settings.get("dhan_client_id") or not settings.get("dhan_access_token"):
            write_heartbeat("error", "Dhan credentials missing - fill them in on the Settings page")
            time.sleep(5)
            continue

        try:
            if dhan is None:
                dhan = get_client(settings)
            last_seen_bar_time = run_once(dhan, settings, last_seen_bar_time)
        except Exception as e:
            log.error(f"Cycle error: {e}", exc_info=True)
            write_heartbeat("error", f"{type(e).__name__}: {e}")
            dhan = None  # rebuild client next cycle in case it's an auth/connection issue

        poll_seconds = min(int(settings.get("candle_interval", 15)) * 60, 60)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
