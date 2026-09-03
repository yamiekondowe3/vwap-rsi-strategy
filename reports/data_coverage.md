# Data coverage status

**As of this build: no real market data has been ingested yet.** The
proof-of-concept pipeline (`backtest/run_poc.py`) runs on synthetic
random-walk OHLCV purely to validate that the backtest → metrics →
Monte Carlo → WFO wiring works end to end without look-ahead bugs.

## MT5 connectivity

The MT5 terminal (`C:\Program Files\MetaTrader 5 Terminal`) is installed
and was confirmed connected to a demo account, but the Python API
(`MetaTrader5.initialize()`) returned `(-6, 'Terminal: Authorization
failed')` during this build and was not resolved in this session (the
terminal was not restarted after enabling API/algo-trading access, which
MT5 typically requires). **Next step:** fully close and relaunch the MT5
terminal, confirm Tools → Options → Expert Advisors → "Allow algorithmic
trading" is checked, log back into the demo account, then re-run
`scripts_check_mt5.py` (in the `trading-systems/` root) to confirm symbol
names and real available history depth per instrument before any real
backtest is trusted.

## External backfill sources (not yet implemented)

Per the project plan, once MT5 connectivity is restored the achieved MT5
history should be backfilled with:
- **XAUUSD / XAGUSD:** Dukascopy tick data aggregated to OHLCV.
- **BTCUSD / ETHUSD:** a single fixed reputable exchange's API (e.g.
  Coinbase or Kraken) — never an aggregated/CoinMarketCap-style volume
  source (see the research docs' wash-trading warning).
- **USOIL:** a public commodities data source.

None of this has been built yet — `common/data_fetch.py` currently only
implements the MT5 leg (`fetch_mt5`) plus the generic Parquet cache/report
helpers. Whatever real date range is achieved per symbol MUST be reported
here (via `common.data_fetch.report_coverage`) instead of assuming 16
years — do not backfill this section with aspirational numbers.
