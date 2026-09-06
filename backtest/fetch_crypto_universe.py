"""Fetch H1 and M15 for the crypto universe, for cross-sectional replication."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common.data_fetch import save_parquet

EXCLUDE_SUBSTR = ["RSI", "Index"]
EXCLUDE_EXACT = {"BTCETH", "BTCLTC"}
MIN_BARS = {"H1": 3 * 365 * 20, "M15": 3 * 365 * 60}


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(mt5.last_error())
    try:
        names = sorted(s.name for s in mt5.symbols_get()
                       if s.path.lower().startswith("crypto")
                       and not any(x.lower() in s.name.lower() for x in EXCLUDE_SUBSTR)
                       and s.name not in EXCLUDE_EXACT)
        print(f"{len(names)} crypto symbols")
        for tf_name, tf_const, cap in [("H1", mt5.TIMEFRAME_H1, 60000),
                                       ("M15", mt5.TIMEFRAME_M15, 150000)]:
            print(f"\n--- {tf_name} ---")
            for name in names:
                mt5.symbol_select(name, True)
                info = mt5.symbol_info(name)
                rates = mt5.copy_rates_from(name, tf_const, datetime.now(timezone.utc), cap)
                if rates is None or len(rates) < MIN_BARS[tf_name] * 0.5:
                    print(f"  {name:10s} skip ({0 if rates is None else len(rates)} bars)")
                    continue
                df = pd.DataFrame(rates)
                df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
                df = df.set_index("timestamp")
                df["spread"] = df["spread"] * (info.point if info else 0.0)
                df = df.rename(columns={"tick_volume": "volume"})[
                    ["open", "high", "low", "close", "volume", "spread"]]
                save_parquet(df, name, tf_name)
                yrs = (df.index[-1] - df.index[0]).days / 365.25
                print(f"  {name:10s} {len(df):7d} bars  {yrs:4.1f}y", flush=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
