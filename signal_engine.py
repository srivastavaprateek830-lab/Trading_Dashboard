"""
core/signal_engine.py
Combines Supertrend + RSI + UT Bot into a single BUY/SELL/HOLD signal per bar.
This is used identically by the backtester and the live daemon - both call
generate_signals(df, settings) with the SAME settings dict, so what you see
in a backtest is exactly the logic that runs live.
"""

import pandas as pd
from core.indicators import calculate_supertrend, calculate_rsi, calculate_ut_bot


def build_indicators(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = calculate_supertrend(
        df, settings["supertrend_atr_period"], settings["supertrend_multiplier"]
    )
    df["rsi"] = calculate_rsi(df, settings["rsi_period"])
    df = calculate_ut_bot(df, settings["ut_bot_key_value"], settings["ut_bot_atr_period"])
    return df


def generate_signals(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = build_indicators(df, settings)

    bull_votes = pd.DataFrame({
        "supertrend": df["supertrend_direction"] == 1,
        "rsi": df["rsi"] > settings["rsi_bull_threshold"],
        "ut_bot": df["ut_bot_trend"] == 1,
    })
    bear_votes = pd.DataFrame({
        "supertrend": df["supertrend_direction"] == -1,
        "rsi": df["rsi"] < settings["rsi_bear_threshold"],
        "ut_bot": df["ut_bot_trend"] == -1,
    })

    bull_count = bull_votes.sum(axis=1)
    bear_count = bear_votes.sum(axis=1)

    ut_flip_up = df["ut_bot_signal"] == 1
    ut_flip_down = df["ut_bot_signal"] == -1

    min_agree = settings["min_indicators_agreeing"]
    signal = pd.Series(None, index=df.index, dtype=object)
    signal[ut_flip_up & (bull_count >= min_agree)] = "BUY"
    signal[ut_flip_down & (bear_count >= min_agree)] = "SELL"

    df["signal"] = signal
    df["bull_votes"] = bull_count
    df["bear_votes"] = bear_count
    return df
