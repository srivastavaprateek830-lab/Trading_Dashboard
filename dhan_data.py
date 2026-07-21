"""
core/dhan_data.py
All Dhan-specific API calls live here. Everything else in the app works with
clean pandas DataFrames / dicts, so Dhan's API shape/quirks stay contained
to this one file.
"""

import time
from datetime import datetime, timedelta
import pandas as pd
import requests
from dhanhq import DhanContext, dhanhq

INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"


def get_client(settings: dict):
    ctx = DhanContext(settings["dhan_client_id"], settings["dhan_access_token"])
    return dhanhq(ctx)


# ---------------- Instrument lookup (so you never have to hand-type a security_id) ----------------

def fetch_instrument_master(cache_path: str = "instrument_master_cache.csv", max_age_hours: int = 24) -> pd.DataFrame:
    """
    Downloads Dhan's instrument master (symbol -> security_id mapping) and
    caches it locally for max_age_hours, since it's a large file and doesn't
    change intraday.
    """
    from pathlib import Path
    path = Path(cache_path)
    if path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return pd.read_csv(path, low_memory=False)

    resp = requests.get(INSTRUMENT_MASTER_URL, timeout=60)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    return pd.read_csv(path, low_memory=False)


def search_underlying(instrument_df: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    Search the instrument master for index/equity underlyings matching a name,
    e.g. search_underlying(df, "NIFTY") or search_underlying(df, "RELIANCE").
    Returns candidate rows with symbol, security_id, exchange segment.
    """
    q = query.upper().strip()
    mask = instrument_df["SEM_TRADING_SYMBOL"].astype(str).str.upper().str.contains(q, na=False)
    cols = [c for c in ["SEM_TRADING_SYMBOL", "SEM_SMST_SECURITY_ID", "SEM_EXM_EXCH_ID",
                         "SEM_SEGMENT", "SEM_INSTRUMENT_NAME"] if c in instrument_df.columns]
    return instrument_df.loc[mask, cols].drop_duplicates().head(30)


# ---------------- Historical data ----------------

def fetch_historical(dhan, settings: dict, from_date: str, to_date: str) -> pd.DataFrame:
    """
    Fetch historical intraday OHLC for the underlying between from_date and
    to_date (YYYY-MM-DD strings), chunking into <=90 day windows since that's
    Dhan's per-request limit for intraday data. Returns one combined,
    de-duplicated, sorted DataFrame.
    """
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")

    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=89), end)
        chunks.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cursor = chunk_end + timedelta(days=1)

    frames = []
    for f, t in chunks:
        resp = dhan.intraday_minute_data(
            security_id=str(settings["security_id"]),
            exchange_segment=settings["exchange_segment"],
            instrument_type="INDEX" if settings["exchange_segment"] == "IDX_I" else "EQUITY",
            from_date=f,
            to_date=t,
        )
        data = resp.get("data", resp)
        if not data or not data.get("close"):
            continue
        ts_key = "timestamp" if "timestamp" in data else "start_Time"
        frame = pd.DataFrame({
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data.get("volume", [0] * len(data["close"])),
        })
        frame.index = pd.to_datetime(data[ts_key], unit="s")
        frames.append(frame)
        time.sleep(0.5)  # be polite between chunk requests

    if not frames:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df.index.name = "datetime"
    return df


# ---------------- Option chain ----------------

def fetch_daily_historical(dhan, settings: dict, from_date: str, to_date: str, security_id: str = None, exchange_segment: str = None) -> pd.DataFrame:
    """
    Fetch DAILY (not intraday) historical OHLC - used for things like range/ATR
    screening across many symbols, where daily bars are enough and pulling
    intraday data for 200 stocks would be slow and hit rate limits.
    Pass security_id/exchange_segment explicitly to override settings (useful
    when looping over a watchlist of many different stocks).
    """
    sec_id = security_id or settings["security_id"]
    exch_seg = exchange_segment or settings["exchange_segment"]

    resp = dhan.historical_daily_data(
        security_id=str(sec_id),
        exchange_segment=exch_seg,
        instrument_type="INDEX" if exch_seg == "IDX_I" else "EQUITY",
        from_date=from_date,
        to_date=to_date,
    )
    data = resp.get("data", resp)
    if not data or not data.get("close"):
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    ts_key = "timestamp" if "timestamp" in data else "start_Time"
    df = pd.DataFrame({
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data.get("volume", [0] * len(data["close"])),
    })
    df.index = pd.to_datetime(data[ts_key], unit="s")
    df.index.name = "datetime"
    return df.sort_index()


def resolve_symbol(instrument_df: pd.DataFrame, symbol: str, exchange: str = "NSE") -> dict:
    """
    Resolve a plain symbol name (e.g. "RELIANCE") to its Dhan security_id for
    the equity segment. Returns None if no confident exact match is found -
    caller should skip and report unresolved symbols rather than guess.
    """
    sym = symbol.strip().upper()
    mask = (
        (instrument_df["SEM_TRADING_SYMBOL"].astype(str).str.upper() == sym)
        & (instrument_df["SEM_EXM_EXCH_ID"].astype(str).str.upper() == exchange)
    )
    matches = instrument_df.loc[mask]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return {
        "symbol": sym,
        "security_id": str(row["SEM_SMST_SECURITY_ID"]),
        "exchange_segment": "NSE_EQ",
    }
    resp = dhan.expiry_list(
        under_security_id=int(settings["security_id"]),
        under_exchange_segment=settings["exchange_segment"],
    )
    return resp.get("data", [])


def fetch_option_chain(dhan, settings: dict, expiry: str) -> dict:
    resp = dhan.option_chain(
        under_security_id=int(settings["security_id"]),
        under_exchange_segment=settings["exchange_segment"],
        expiry=expiry,
    )
    return resp.get("data", resp)


_last_chain_call = [0.0]


def polite_option_chain_fetch(dhan, settings: dict, expiry: str, min_gap_sec: float = 3.0) -> dict:
    """Dhan rate-limits option chain calls - never poll faster than this."""
    elapsed = time.time() - _last_chain_call[0]
    if elapsed < min_gap_sec:
        time.sleep(min_gap_sec - elapsed)
    result = fetch_option_chain(dhan, settings, expiry)
    _last_chain_call[0] = time.time()
    return result
