"""
pages/1_Settings.py
Everything configurable lives here. Saved to settings.json, which the
background daemon re-reads every cycle — no restart needed after saving.
"""

import streamlit as st
from shared.settings_store import load_settings, save_settings
from core.dhan_data import fetch_instrument_master, search_underlying
from shared.theme import inject_theme

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
inject_theme()
st.title("⚙️ Settings")

settings = load_settings()

st.subheader("1. Dhan API connection")
st.caption("Get these from web.dhan.co → profile icon → 'Access DhanHQ APIs'.")
c1, c2 = st.columns(2)
client_id = c1.text_input("Dhan Client ID", value=settings["dhan_client_id"])
access_token = c2.text_input("Dhan Access Token", value=settings["dhan_access_token"], type="password")

st.divider()
st.subheader("2. Instrument")
st.caption("Search for your underlying (index or F&O stock) and pick the matching row to auto-fill its Security ID.")

search_query = st.text_input("Search symbol (e.g. NIFTY, BANKNIFTY, RELIANCE)", value="")
if search_query:
    try:
        instrument_df = fetch_instrument_master()
        results = search_underlying(instrument_df, search_query)
        if results.empty:
            st.warning("No matches found - try a shorter search term.")
        else:
            st.dataframe(results, use_container_width=True)
            st.caption("Copy the Security ID from the matching row into the field below.")
    except Exception as e:
        st.error(f"Couldn't fetch instrument list: {e}")

c1, c2, c3, c4 = st.columns(4)
underlying_symbol = c1.text_input("Symbol name (label only)", value=settings["underlying_symbol"])
exchange_segment = c2.selectbox(
    "Exchange segment", options=["IDX_I", "NSE_EQ", "NSE_FNO", "MCX_COMM"],
    index=["IDX_I", "NSE_EQ", "NSE_FNO", "MCX_COMM"].index(settings["exchange_segment"])
    if settings["exchange_segment"] in ["IDX_I", "NSE_EQ", "NSE_FNO", "MCX_COMM"] else 0,
    help="IDX_I = index (NIFTY/BANKNIFTY), NSE_EQ = stock",
)
security_id = c3.text_input("Security ID", value=str(settings["security_id"]))
candle_interval = c4.selectbox(
    "Candle interval (minutes)", options=["1", "5", "15", "25", "60"],
    index=["1", "5", "15", "25", "60"].index(str(settings["candle_interval"]))
    if str(settings["candle_interval"]) in ["1", "5", "15", "25", "60"] else 2,
)

st.divider()
st.subheader("3. Strategy — Supertrend + RSI + UT Bot")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Supertrend**")
    st_period = st.number_input("ATR period", value=int(settings["supertrend_atr_period"]), min_value=2, max_value=100)
    st_mult = st.number_input("Multiplier", value=float(settings["supertrend_multiplier"]), min_value=0.5, max_value=10.0, step=0.5)

    st.markdown("**RSI**")
    rsi_period = st.number_input("RSI period", value=int(settings["rsi_period"]), min_value=2, max_value=100)
    rsi_bull = st.number_input("Bullish threshold (RSI above this = bullish)", value=int(settings["rsi_bull_threshold"]), min_value=0, max_value=100)
    rsi_bear = st.number_input("Bearish threshold (RSI below this = bearish)", value=int(settings["rsi_bear_threshold"]), min_value=0, max_value=100)

with c2:
    st.markdown("**UT Bot Alert**")
    ut_key = st.number_input("Key value (sensitivity)", value=float(settings["ut_bot_key_value"]), min_value=0.1, max_value=10.0, step=0.1)
    ut_atr_period = st.number_input("ATR period ", value=int(settings["ut_bot_atr_period"]), min_value=2, max_value=100)

    st.markdown("**Signal strictness**")
    min_agree = st.select_slider(
        "Indicators required to agree",
        options=[2, 3],
        value=int(settings["min_indicators_agreeing"]),
        help="3 = all must agree (fewer, higher-quality signals). 2 = majority vote (more signals, more noise).",
    )

st.divider()
st.subheader("4. Option strike selection (Greeks-based)")

c1, c2, c3 = st.columns(3)
with c1:
    min_dte = st.number_input("Min days to expiry", value=int(settings["min_dte"]), min_value=0, max_value=60)
    max_dte = st.number_input("Max days to expiry", value=int(settings["max_dte"]), min_value=1, max_value=90)
    preferred_dte = st.number_input("Preferred days to expiry", value=int(settings["preferred_dte"]), min_value=0, max_value=90)
with c2:
    delta_min = st.slider("Min delta", 0.0, 1.0, float(settings["delta_min"]), 0.01)
    delta_max = st.slider("Max delta", 0.0, 1.0, float(settings["delta_max"]), 0.01)
    preferred_delta = st.slider("Preferred delta", 0.0, 1.0, float(settings["preferred_delta"]), 0.01)
with c3:
    min_oi = st.number_input("Minimum open interest", value=int(settings["min_oi"]), min_value=0, step=10000)
    max_spread = st.number_input("Max bid-ask spread (%)", value=float(settings["max_bid_ask_spread_pct"]), min_value=0.1, max_value=20.0, step=0.1)
    gamma_warn = st.number_input("Gamma warning threshold", value=float(settings["gamma_high_warning"]), min_value=0.0001, max_value=0.05, step=0.0001, format="%.4f")

st.divider()
st.subheader("5. Stop-loss / Target (on option premium)")
c1, c2 = st.columns(2)
sl_pct = c1.number_input("Stop-loss (% of entry premium)", value=float(settings["sl_percent"]), min_value=1.0, max_value=90.0, step=1.0)
tp_r = c2.number_input("Target as multiple of risk (R-multiple)", value=float(settings["tp_r_multiple"]), min_value=0.5, max_value=10.0, step=0.1)

st.divider()
st.subheader("6. Optional: Telegram alerts")
st.caption("Leave blank to only see alerts in this dashboard. Create a bot via @BotFather to get a token.")
c1, c2 = st.columns(2)
tg_token = c1.text_input("Telegram bot token", value=settings["telegram_bot_token"], type="password")
tg_chat = c2.text_input("Telegram chat ID", value=settings["telegram_chat_id"])

st.divider()
if st.button("💾 Save settings", type="primary"):
    new_settings = dict(settings)
    new_settings.update({
        "dhan_client_id": client_id,
        "dhan_access_token": access_token,
        "underlying_symbol": underlying_symbol,
        "exchange_segment": exchange_segment,
        "security_id": security_id,
        "candle_interval": candle_interval,
        "supertrend_atr_period": st_period,
        "supertrend_multiplier": st_mult,
        "rsi_period": rsi_period,
        "rsi_bull_threshold": rsi_bull,
        "rsi_bear_threshold": rsi_bear,
        "ut_bot_key_value": ut_key,
        "ut_bot_atr_period": ut_atr_period,
        "min_indicators_agreeing": min_agree,
        "min_dte": min_dte,
        "max_dte": max_dte,
        "preferred_dte": preferred_dte,
        "delta_min": delta_min,
        "delta_max": delta_max,
        "preferred_delta": preferred_delta,
        "min_oi": min_oi,
        "max_bid_ask_spread_pct": max_spread,
        "gamma_high_warning": gamma_warn,
        "sl_percent": sl_pct,
        "tp_r_multiple": tp_r,
        "telegram_bot_token": tg_token,
        "telegram_chat_id": tg_chat,
    })
    save_settings(new_settings)
    st.success("Settings saved. The live bot (if running) will pick these up on its next cycle.")
