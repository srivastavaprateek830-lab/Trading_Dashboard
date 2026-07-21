"""
shared/settings_store.py
Single source of truth for all settings - Dhan credentials + strategy
parameters. The Streamlit dashboard writes here when you click Save.
The background alert daemon re-reads this file every cycle, so changes
take effect within one candle without restarting anything.
"""

import json
import os
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"

DEFAULTS = {
    # --- Dhan credentials ---
    "dhan_client_id": "",
    "dhan_access_token": "",

    # --- Instrument ---
    "underlying_symbol": "NIFTY",
    "exchange_segment": "IDX_I",     # IDX_I for index, NSE_EQ for stock underlying
    "security_id": "13",             # NIFTY = 13, BANKNIFTY = 25 on Dhan; verify for stocks
    "candle_interval": "15",         # minutes

    # --- Supertrend ---
    "supertrend_atr_period": 10,
    "supertrend_multiplier": 3.0,

    # --- RSI ---
    "rsi_period": 14,
    "rsi_bull_threshold": 50,
    "rsi_bear_threshold": 50,

    # --- UT Bot Alert ---
    "ut_bot_key_value": 1.0,
    "ut_bot_atr_period": 10,

    # --- Signal combination ---
    "min_indicators_agreeing": 3,    # 3 = strict, 2 = looser/more signals

    # --- Option strike selection ---
    "min_dte": 2,
    "max_dte": 15,
    "preferred_dte": 7,
    "delta_min": 0.35,
    "delta_max": 0.65,
    "preferred_delta": 0.50,
    "min_oi": 100000,
    "max_bid_ask_spread_pct": 2.0,
    "gamma_high_warning": 0.003,

    # --- SL / TP on option premium ---
    "sl_percent": 30.0,
    "tp_r_multiple": 1.5,

    # --- Alerts ---
    "telegram_bot_token": "",
    "telegram_chat_id": "",

    # --- Daemon control ---
    "daemon_enabled": False,         # dashboard flips this on/off; daemon checks it each cycle
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULTS)
        merged = dict(DEFAULTS)
    else:
        with open(SETTINGS_PATH, "r") as f:
            saved = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(saved)  # keep any new default keys if settings.json is from an older version

    # On Streamlit Community Cloud, local files reset whenever the app wakes
    # from sleep - credentials would need retyping every time. If they're
    # configured in Streamlit's Secrets manager instead, always prefer those
    # so login survives resets. (Locally, with no secrets.toml, this is a
    # harmless no-op and the settings.json value is used as before.)
    try:
        import streamlit as st
        if "dhan_client_id" in st.secrets:
            merged["dhan_client_id"] = st.secrets["dhan_client_id"]
        if "dhan_access_token" in st.secrets:
            merged["dhan_access_token"] = st.secrets["dhan_access_token"]
    except Exception:
        pass  # not running inside Streamlit, or no secrets configured - fine

    return merged


def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    os.chmod(SETTINGS_PATH, 0o600)  # credentials live in here - restrict read to owner
