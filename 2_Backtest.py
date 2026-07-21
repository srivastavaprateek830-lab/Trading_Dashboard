"""
pages/2_Backtest.py
Pulls real historical data from Dhan for your configured instrument and
runs the exact same signal logic used live, so you can judge the strategy
honestly before trusting it with alerts.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

from shared.settings_store import load_settings
from core.dhan_data import get_client, fetch_historical
from core.backtester import run_backtest
from shared.theme import inject_theme

st.set_page_config(page_title="Backtest", page_icon="📊", layout="wide")
inject_theme()
st.title("📊 Backtest")

settings = load_settings()

if not settings["dhan_client_id"] or not settings["dhan_access_token"]:
    st.warning("Add your Dhan credentials on the Settings page first.")
    st.stop()

st.caption(f"Instrument: **{settings['underlying_symbol']}** ({settings['exchange_segment']}, "
           f"security ID {settings['security_id']}) — {settings['candle_interval']}-minute candles")

c1, c2, c3 = st.columns(3)
from_date = c1.date_input("From date", value=date.today() - timedelta(days=60))
to_date = c2.date_input("To date", value=date.today())
run_clicked = c3.button("▶ Fetch data & run backtest", type="primary")

st.info("Dhan's intraday history API covers roughly the last 5 years, but returns a max of "
        "90 days per request — longer ranges are automatically fetched in chunks, which takes "
        "a bit longer.")

if run_clicked:
    with st.spinner("Fetching historical data from Dhan..."):
        try:
            dhan = get_client(settings)
            df = fetch_historical(dhan, settings, from_date.isoformat(), to_date.isoformat())
        except Exception as e:
            st.error(f"Couldn't fetch historical data: {e}")
            st.stop()

    if df.empty:
        st.warning("No data returned for this range. Try a different date range or double-check "
                    "the Security ID on the Settings page.")
        st.stop()

    st.success(f"Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}.")

    with st.spinner("Running backtest..."):
        result = run_backtest(df, settings)

    st.session_state["backtest_result"] = result

result = st.session_state.get("backtest_result")

if result is not None:
    if result["message"]:
        st.warning(result["message"])
    else:
        st.subheader("Summary")
        cols = st.columns(len(result["summary"]))
        for col, (k, v) in zip(cols, result["summary"].items()):
            col.metric(k, v)

        st.subheader("Price chart with signals")
        chart_df = result["chart_df"]
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=chart_df.index, open=chart_df["open"], high=chart_df["high"],
            low=chart_df["low"], close=chart_df["close"], name="Price",
        ))
        fig.add_trace(go.Scatter(
            x=chart_df.index, y=chart_df["supertrend"], name="Supertrend",
            line=dict(width=1.5),
        ))
        buys = chart_df[chart_df["signal"] == "BUY"]
        sells = chart_df[chart_df["signal"] == "SELL"]
        fig.add_trace(go.Scatter(
            x=buys.index, y=buys["close"], mode="markers", name="BUY signal",
            marker=dict(symbol="triangle-up", size=12, color="green"),
        ))
        fig.add_trace(go.Scatter(
            x=sells.index, y=sells["close"], mode="markers", name="SELL signal",
            marker=dict(symbol="triangle-down", size=12, color="red"),
        ))
        fig.update_layout(height=550, xaxis_rangeslider_visible=False,
                           margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Equity curve (points on underlying, per trade)")
        eq_fig = go.Figure()
        eq_fig.add_trace(go.Scatter(
            x=result["trades"]["exit_time"], y=result["trades"]["cumulative_pnl"],
            mode="lines+markers", name="Cumulative P&L",
        ))
        eq_fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(eq_fig, use_container_width=True)

        st.subheader("Trade log")
        st.dataframe(result["trades"], use_container_width=True)
        st.download_button(
            "Download trade log as CSV",
            result["trades"].to_csv(index=False),
            file_name="backtest_trades.csv",
            mime="text/csv",
        )

        st.caption("Note: this backtests the underlying's price action, not option premium P&L — "
                   "premium also depends on IV changes and theta decay. This tells you whether the "
                   "strategy's entry/exit TIMING is good, which is the thing to validate first.")
