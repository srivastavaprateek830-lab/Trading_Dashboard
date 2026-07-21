"""
streamlit_app.py
Home page of the dashboard. Run with: streamlit run streamlit_app.py
Use the sidebar to navigate to Settings, Backtest, and Live Alerts.
"""

import time
import streamlit as st
from shared.settings_store import load_settings
from shared.alerts_store import read_heartbeat, read_alerts
from shared.process_control import is_running
from shared.theme import inject_theme, badge

st.set_page_config(page_title="Trading Alert System", page_icon="📈", layout="wide")
inject_theme()

st.title("📈 Signal Matrix — Trading Alert System")
st.caption("Connected to your Dhan account. Generates BUY/SELL alerts with a recommended "
           "option strike, SL and TP. Execution is always manual — you place the trade in Dhan yourself.")

settings = load_settings()

col1, col2, col3 = st.columns(3)

with col1:
    creds_ok = bool(settings["dhan_client_id"] and settings["dhan_access_token"])
    st.metric("Dhan connection", "Configured ✅" if creds_ok else "Not set up ⚠️")
    if not creds_ok:
        st.caption("Go to Settings to add your Client ID and Access Token.")

with col2:
    running = is_running()
    st.metric("Background bot", "Running 🟢" if running else "Stopped 🔴")

with col3:
    heartbeat = read_heartbeat()
    hb_status = heartbeat.get("status", "never_started")
    st.metric("Last check-in", hb_status)
    if heartbeat.get("timestamp"):
        age_min = (time.time() - heartbeat["timestamp"]) / 60
        st.caption(f"{age_min:.1f} minutes ago — {heartbeat.get('detail', '')}")

st.divider()

st.subheader("What to do next")
st.markdown("""
1. **Settings** — enter your Dhan Client ID / Access Token, pick your instrument, and tune the strategy.
2. **Backtest** — pull real historical data from Dhan and check the strategy's track record before trusting it.
3. **Live Alerts** — start the background bot; it watches the market and shows alerts here, even if you close this browser tab.
""")

st.divider()
st.subheader("Most recent alerts")
alerts = read_alerts(limit=5)
if not alerts:
    st.info("No alerts yet. Start the bot from the Live Alerts page once your settings are configured.")
else:
    for a in alerts:
        kind = "buy" if a.get("signal") == "BUY" else "sell" if a.get("signal") == "SELL" else "flat"
        if a.get("type") == "trade_signal":
            st.markdown(f"{badge(a['signal'], kind)} {a.get('option_type','')} {a.get('strike','')} "
                        f"— {a.get('underlying_symbol','')} @ {a.get('underlying_price','')} "
                        f"— *{a.get('bar_time','')}*", unsafe_allow_html=True)
        else:
            st.markdown(f"{badge(a.get('signal',''), kind)} signal at {a.get('underlying_price','')} — "
                        f"{a.get('reason','')} — *{a.get('bar_time','')}*", unsafe_allow_html=True)
