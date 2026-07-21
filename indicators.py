"""
indicators.py
Pure functions: take an OHLC dataframe, return the dataframe with indicator
columns added. No I/O, no API calls here - keeps this testable and reusable
for both backtest and live.

Expected input df columns: 'open', 'high', 'low', 'close' (volume optional),
indexed by datetime, sorted ascending.
"""

import numpy as np
import pandas as pd


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # neutral until enough data


def calculate_supertrend(
    df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Returns df with 'supertrend' (the trailing stop line) and
    'supertrend_direction' (1 = uptrend/bullish, -1 = downtrend/bearish).
    """
    atr = _atr(df, atr_period)
    hl2 = (df["high"] + df["low"]) / 2

    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    final_upper = upperband.copy()
    final_lower = lowerband.copy()
    direction = pd.Series(1, index=df.index)
    supertrend = pd.Series(0.0, index=df.index)

    for i in range(1, len(df)):
        # carry forward bands unless price breaks them (standard Supertrend rule)
        if upperband.iloc[i] < final_upper.iloc[i - 1] or df["close"].iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = upperband.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if lowerband.iloc[i] > final_lower.iloc[i - 1] or df["close"].iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = lowerband.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        if direction.iloc[i - 1] == 1 and df["close"].iloc[i] < final_lower.iloc[i]:
            direction.iloc[i] = -1
        elif direction.iloc[i - 1] == -1 and df["close"].iloc[i] > final_upper.iloc[i]:
            direction.iloc[i] = 1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]

    out = df.copy()
    out["supertrend"] = supertrend
    out["supertrend_direction"] = direction
    return out


def calculate_ut_bot(
    df: pd.DataFrame, key_value: float = 1.0, atr_period: int = 10
) -> pd.DataFrame:
    """
    UT Bot Alert (ATR trailing-stop indicator, widely used TradingView script).
    Returns df with 'ut_bot_stop' (trailing stop line) and
    'ut_bot_signal' (1 = buy flip this bar, -1 = sell flip this bar, 0 = no flip).
    """
    atr = _atr(df, atr_period)
    n_loss = key_value * atr
    close = df["close"]

    trailing_stop = pd.Series(0.0, index=df.index)
    for i in range(len(df)):
        if i == 0:
            trailing_stop.iloc[i] = close.iloc[i] - n_loss.iloc[i] if not np.isnan(n_loss.iloc[i]) else close.iloc[i]
            continue

        prev_stop = trailing_stop.iloc[i - 1]
        c, c_prev = close.iloc[i], close.iloc[i - 1]
        nl = n_loss.iloc[i] if not np.isnan(n_loss.iloc[i]) else 0

        if c > prev_stop and c_prev > prev_stop:
            trailing_stop.iloc[i] = max(prev_stop, c - nl)
        elif c < prev_stop and c_prev < prev_stop:
            trailing_stop.iloc[i] = min(prev_stop, c + nl)
        elif c > prev_stop:
            trailing_stop.iloc[i] = c - nl
        else:
            trailing_stop.iloc[i] = c + nl

    above = close > trailing_stop
    above_prev = above.shift(1).fillna(False)

    signal = pd.Series(0, index=df.index)
    signal[(above) & (~above_prev)] = 1    # flipped bullish this bar
    signal[(~above) & (above_prev)] = -1   # flipped bearish this bar

    out = df.copy()
    out["ut_bot_stop"] = trailing_stop
    out["ut_bot_signal"] = signal
    out["ut_bot_trend"] = np.where(above, 1, -1)
    return out
