"""Fetch Binance perp data for the information-edge tests.

Two signals, both genuinely different from price patterns:
  funding rate  -- the cost longs pay shorts (or vice versa) every 8h. A
                   crowding/positioning proxy: extreme positive funding means
                   leveraged longs are paying heavily to stay in.
  order flow    -- taker buy volume as a share of total, carried inside every
                   kline. Whether aggressive buyers or sellers dominated.

8-hour bars, because that is funding's native cadence and aligning them
avoids interpolating a signal that only updates 3x/day.

Costs here are BINANCE costs (taker ~4bp, maker ~2bp), not the Deriv CFD
spreads used elsewhere -- a different venue with materially cheaper
execution, which is itself part of what makes this worth testing.
"""
import sys
import time
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data_binance"
OUT.mkdir(exist_ok=True)

SPOT = "https://api.binance.com/api/v3/klines"
FUT = "https://fapi.binance.com/fapi/v1/fundingRate"

# Liquid USDT perps with long histories. Deliberately broad: the
# cross-section is the test that has decided every question in this project.
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT",
           "DOGEUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT",
           "ATOMUSDT", "ETCUSDT", "XLMUSDT", "TRXUSDT", "FILUSDT", "NEARUSDT",
           "ALGOUSDT", "VETUSDT", "ICPUSDT", "AAVEUSDT", "EOSUSDT", "XMRUSDT"]

S = requests.Session()
S.headers["User-Agent"] = "research/1.0"


def get_klines(symbol, interval="8h"):
    rows, start = [], 0
    while True:
        try:
            r = S.get(SPOT, params={"symbol": symbol, "interval": interval,
                                    "startTime": start, "limit": 1000}, timeout=30)
            if r.status_code != 200:
                break
            d = r.json()
        except Exception:
            time.sleep(2); continue
        if not d:
            break
        rows += d
        nxt = d[-1][0] + 1
        if nxt <= start or len(d) < 1000:
            break
        start = nxt
        time.sleep(0.15)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close",
                                     "volume", "close_time", "quote_volume", "trades",
                                     "taker_buy_base", "taker_buy_quote", "ignore"])
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    for c in ["open", "high", "low", "close", "volume", "quote_volume",
              "taker_buy_base", "trades"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Order-flow imbalance: share of volume that was aggressive buying.
    # 0.5 is balanced; >0.5 means takers were lifting offers.
    df["of_imbalance"] = df["taker_buy_base"] / df["volume"].replace(0, pd.NA)
    return df[["open", "high", "low", "close", "volume", "trades",
               "taker_buy_base", "of_imbalance"]]


def get_funding(symbol):
    # startTime=0 is IGNORED by this endpoint -- it silently returns only the
    # most recent 500 records. An explicit early timestamp is required to
    # page forward from the beginning.
    import datetime as _dt
    rows = []
    start = int(_dt.datetime(2019, 1, 1, tzinfo=_dt.timezone.utc).timestamp() * 1000)
    while True:
        try:
            r = S.get(FUT, params={"symbol": symbol, "startTime": start,
                                   "limit": 1000}, timeout=30)
            if r.status_code != 200:
                break
            d = r.json()
        except Exception:
            time.sleep(2); continue
        if not isinstance(d, list) or not d:
            break
        rows += d
        nxt = int(d[-1]["fundingTime"]) + 1
        # NOTE: this endpoint caps at 500 rows per call regardless of the
        # limit parameter, so a "len(d) < limit" break condition stops after
        # the first page and silently yields ~166 days instead of years.
        # Terminate only when the page fails to advance or returns nothing.
        if nxt <= start or len(d) == 0:
            break
        start = nxt
        time.sleep(0.15)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["funding"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    return df.set_index("timestamp")[["funding"]]


def main():
    ok = []
    for sym in SYMBOLS:
        try:
            k = get_klines(sym)
            f = get_funding(sym)
        except Exception as e:
            print(f"  {sym:10s} error {type(e).__name__}"); continue
        if k is None or len(k) < 1500:
            print(f"  {sym:10s} skip (klines {0 if k is None else len(k)})"); continue
        if f is not None and len(f):
            # funding is 8h and so are the bars; align on the bar containing it,
            # then SHIFT so a bar only ever sees funding already settled.
            k = k.join(f.reindex(k.index, method="ffill"))
            k["funding"] = k["funding"].shift(1)
        else:
            k["funding"] = pd.NA
        k.to_parquet(OUT / f"{sym}_8h.parquet")
        yrs = (k.index[-1] - k.index[0]).days / 365.25
        nf = int(k["funding"].notna().sum())
        print(f"  {sym:10s} {len(k):6d} bars {yrs:5.1f}y  funding rows {nf}", flush=True)
        ok.append(sym)
    (OUT / "universe.json").write_text(json.dumps(ok, indent=2))
    print(f"\n{len(ok)} symbols cached to {OUT}")


if __name__ == "__main__":
    main()
