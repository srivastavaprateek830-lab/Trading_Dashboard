"""
pages/3_Live_Alerts.py
Start/stop the background bot and watch alerts come in. The bot keeps
running independent of this page - closing the browser tab does NOT stop it
(only the Stop button, or restarting the machine, does).
"""

import time
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.settings_store import load_settings, save_settings
from shared.alerts_store import read_alerts, read_heartbeat
from shared.process_control import is_running, start_daemon, stop_daemon
from shared.theme import inject_theme, badge

st.set_page_config(page_title="Live Alerts", page_icon="🔔", layout="wide")
inject_theme()
st.title("🔔 Live Alerts")

settings = load_settings()

if not settings["dhan_client_id"] or not settings["dhan_access_token"]:
    st.warning("Add your Dhan credentials on the Settings page first.")
    st.stop()

st_autorefresh(interval=15000, key="live_alerts_refresh")  # refresh every 15s to show new alerts

running = is_running()

c1, c2, c3 = st.columns([1, 1, 3])
with c1:
    if not running:
        if st.button("▶ Start bot", type="primary"):
            settings["daemon_enabled"] = True
            save_settings(settings)
            start_daemon()
            time.sleep(1)
            st.rerun()
    else:
        if st.button("⏸ Stop bot"):
            settings["daemon_enabled"] = False
            save_settings(settings)
            stop_daemon()
            time.sleep(1)
            st.rerun()

with c2:
    st.metric("Status", "Running 🟢" if running else "Stopped 🔴")

with c3:
    heartbeat = read_heartbeat()
    if heartbeat.get("timestamp"):
        age_sec = time.time() - heartbeat["timestamp"]
        st.caption(f"Last check-in: {age_sec:.0f}s ago — {heartbeat.get('status','')}: {heartbeat.get('detail','')}")
    else:
        st.caption("Bot has never run yet.")

st.caption(f"Watching **{settings['underlying_symbol']}** on **{settings['candle_interval']}-minute** "
           f"candles, requiring **{settings['min_indicators_agreeing']}/3** indicators to agree. "
           "Change these on the Settings page any time — no restart needed.")

st.divider()
st.subheader("Alert feed")

alerts = read_alerts(limit=50)
if not alerts:
    st.info("No alerts yet. Once the bot is running, BUY/SELL signals will appear here as they fire.")
else:
    for a in alerts:
        signal = a.get("signal", "")
        kind = "buy" if signal == "BUY" else "sell" if signal == "SELL" else "flat"
        ts = a.get("bar_time", "")

        if a.get("type") == "trade_signal":
            with st.container(border=True):
                st.markdown(f"### {badge(signal, kind)} {a.get('option_type','')} {a.get('strike','')} "
                            f"@ expiry {a.get('expiry','')} (DTE {a.get('dte','')})", unsafe_allow_html=True)
                st.caption(f"{a.get('underlying_symbol','')} spot: {a.get('underlying_price','')} "
                           f"| candle: {ts} | votes: {a.get('votes','')}/3")
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Premium (LTP)", a.get("ltp", ""))
                m2.metric("Delta", round(a.get("delta", 0), 3))
                m3.metric("Gamma", round(a.get("gamma", 0), 5))
                m4.metric("Stop-loss", a.get("sl_price", ""))
                m5.metric("Target", a.get("tp_price", ""))
                if a.get("gamma_warning"):
                    st.warning("High gamma — premium will move fast in both directions.")
                st.caption(f"OI: {a.get('oi', ''):,}  •  IV: {a.get('iv', 0):.1f}%  •  "
                           f"Spread: {a.get('spread_pct', 0):.2f}%  •  "
                           f"Security ID: {a.get('security_id','')}")
                st.caption("⚠️ Manual execution — verify the live chain/price in Dhan before placing this trade.")
        else:
            st.markdown(f"{badge(signal, kind)} signal at {a.get('underlying_price','')} — "
                        f"{a.get('reason','')} — *{ts}*", unsafe_allow_html=True)

st.divider()
st.caption("Tip: for real 24/7 reliability (surviving reboots), run `alert_daemon.py` as a systemd "
           "service instead of the Start/Stop buttons here — see README.md.")
