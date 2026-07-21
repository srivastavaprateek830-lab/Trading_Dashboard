"""
core/backtester.py
Validates signal TIMING quality on historical underlying price data.
Backtests the underlying's price action, not option premium P&L (premium
also depends on IV changes and theta decay) - this tells you whether the
strategy calls good entries/exits, which is the thing to validate first.
"""

import pandas as pd
from core.signal_engine import generate_signals


def run_backtest(df: pd.DataFrame, settings: dict) -> dict:
    df = generate_signals(df, settings)

    trades = []
    position = None

    for ts, row in df.iterrows():
        sig = row["signal"]

        if position is not None:
            exit_now = (position["side"] == "BUY" and sig == "SELL") or (
                position["side"] == "SELL" and sig == "BUY"
            )
            if exit_now:
                pnl = (
                    row["close"] - position["entry_price"]
                    if position["side"] == "BUY"
                    else position["entry_price"] - row["close"]
                )
                trades.append({
                    "side": position["side"],
                    "entry_time": position["entry_time"],
                    "entry_price": position["entry_price"],
                    "exit_time": ts,
                    "exit_price": row["close"],
                    "pnl_points": pnl,
                })
                position = None

        if position is None and sig in ("BUY", "SELL"):
            position = {"side": sig, "entry_price": row["close"], "entry_time": ts}

    trade_log = pd.DataFrame(trades)

    if trade_log.empty:
        return {
            "trades": trade_log,
            "chart_df": df,
            "summary": None,
            "message": "No trades generated in this period with current settings. "
                       "Try lowering 'Indicators required to agree' to 2, or widen the date range.",
        }

    wins = trade_log[trade_log["pnl_points"] > 0]
    losses = trade_log[trade_log["pnl_points"] <= 0]
    equity = trade_log["pnl_points"].cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    trade_log["cumulative_pnl"] = equity

    summary = {
        "Total trades": len(trade_log),
        "Win rate": f"{100 * len(wins) / len(trade_log):.1f}%",
        "Total points": round(trade_log["pnl_points"].sum(), 2),
        "Avg win (points)": round(wins["pnl_points"].mean(), 2) if not wins.empty else 0,
        "Avg loss (points)": round(losses["pnl_points"].mean(), 2) if not losses.empty else 0,
        "Profit factor": (
            round(wins["pnl_points"].sum() / abs(losses["pnl_points"].sum()), 2)
            if not losses.empty and losses["pnl_points"].sum() != 0 else float("inf")
        ),
        "Max drawdown (points)": round(drawdown.min(), 2),
    }

    return {"trades": trade_log, "chart_df": df, "summary": summary, "message": None}
