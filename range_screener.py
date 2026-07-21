"""
range_screener.py
Ranks stocks in your F&O watchlist by average DAILY RANGE (high - low, in
points) over a lookback period - so you can build a consistent, small
watchlist of stocks that reliably move a meaningful number of points per day,
instead of guessing from memory or a one-off web search.

Usage:
    python range_screener.py --watchlist fno_watchlist.txt --days 20 --top 20

Requires your Dhan credentials in settings.json (same file the dashboard
uses) or pass --client-id / --access-token directly.
"""

import argparse
import time
import sys
from datetime import date, timedelta

import pandas as pd

from shared.settings_store import load_settings
from core.dhan_data import get_client, fetch_instrument_master, resolve_symbol, fetch_daily_historical


def compute_range_stats(df: pd.DataFrame, lookback_days: int) -> dict:
    """Given daily OHLC, compute average range in points, as % of price, and ATR(14)."""
    recent = df.tail(lookback_days)
    if recent.empty:
        return None

    daily_range = recent["high"] - recent["low"]
    avg_range_points = daily_range.mean()
    last_close = recent["close"].iloc[-1]
    avg_range_pct = (avg_range_points / last_close) * 100 if last_close else float("nan")

    # ATR(14) - smoothed true range, accounts for gaps (not just high-low)
    prev_close = recent["close"].shift(1)
    tr = pd.concat([
        recent["high"] - recent["low"],
        (recent["high"] - prev_close).abs(),
        (recent["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.tail(14).mean()

    return {
        "avg_range_points": round(avg_range_points, 1),
        "avg_range_pct": round(avg_range_pct, 2),
        "atr14_points": round(atr14, 1),
        "last_close": round(last_close, 2),
        "days_used": len(recent),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default="fno_watchlist.txt", help="Text file, one symbol per line")
    parser.add_argument("--days", type=int, default=20, help="Lookback period in trading days")
    parser.add_argument("--top", type=int, default=20, help="How many top results to show")
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--access-token", default=None)
    args = parser.parse_args()

    settings = load_settings()
    client_id = args.client_id or settings.get("dhan_client_id")
    access_token = args.access_token or settings.get("dhan_access_token")
    if not client_id or not access_token:
        print("ERROR: Dhan credentials not found. Set them in settings.json or pass --client-id/--access-token.")
        sys.exit(1)

    dhan = get_client({"dhan_client_id": client_id, "dhan_access_token": access_token})

    with open(args.watchlist) as f:
        symbols = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    print(f"Loaded {len(symbols)} symbols from {args.watchlist}")
    print("Fetching instrument master (cached after first run)...")
    instrument_df = fetch_instrument_master()

    to_date = date.today().strftime("%Y-%m-%d")
    from_date = (date.today() - timedelta(days=int(args.days * 1.6) + 10)).strftime("%Y-%m-%d")
    # 1.6x buffer + 10 days accounts for weekends/holidays so we get enough trading days

    results = []
    unresolved = []
    errors = []

    for i, symbol in enumerate(symbols):
        resolved = resolve_symbol(instrument_df, symbol)
        if resolved is None:
            unresolved.append(symbol)
            continue

        try:
            df = fetch_daily_historical(
                dhan, settings, from_date, to_date,
                security_id=resolved["security_id"],
                exchange_segment=resolved["exchange_segment"],
            )
            stats = compute_range_stats(df, args.days)
            if stats is None:
                errors.append((symbol, "no data returned"))
                continue
            results.append({"symbol": symbol, **stats})
        except Exception as e:
            errors.append((symbol, str(e)))

        time.sleep(0.3)  # be polite to the API across ~100-200 symbols
        if (i + 1) % 20 == 0:
            print(f"  ...processed {i + 1}/{len(symbols)}")

    if not results:
        print("No results - check your credentials, watchlist symbols, and date range.")
        sys.exit(1)

    result_df = pd.DataFrame(results).sort_values("avg_range_points", ascending=False)

    print(f"\n=== Top {args.top} by average daily range (last {args.days} trading days) ===")
    print(result_df.head(args.top).to_string(index=False))

    out_path = "range_screener_results.csv"
    result_df.to_csv(out_path, index=False)
    print(f"\nFull results ({len(result_df)} symbols) saved to {out_path}")

    if unresolved:
        print(f"\n{len(unresolved)} symbols could not be matched to a security_id "
              f"(check spelling / verify still listed on NSE): {', '.join(unresolved)}")
    if errors:
        print(f"\n{len(errors)} symbols had fetch errors:")
        for sym, err in errors:
            print(f"  {sym}: {err}")


if __name__ == "__main__":
    main()
