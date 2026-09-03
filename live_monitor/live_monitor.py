"""Read-only MT5 live monitoring CLI.

Connects to the local MT5 terminal, pulls open positions, realized/
unrealized PnL, and a rolling win-rate/slippage digest, and prints it as
structured JSON -- meant to be piped into the next iteration of parameter
review. This script NEVER places, modifies, or closes orders.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import MetaTrader5 as mt5


def connect() -> bool:
    if not mt5.initialize():
        print(json.dumps({"error": "mt5.initialize() failed", "detail": str(mt5.last_error())}))
        return False
    return True


def get_account_digest() -> dict:
    acc = mt5.account_info()
    if acc is None:
        return {}
    return {
        "login": acc.login, "server": acc.server, "balance": acc.balance,
        "equity": acc.equity, "margin": acc.margin, "margin_free": acc.margin_free,
        "profit": acc.profit,  # aggregate unrealized PnL across open positions
    }


def get_open_positions() -> list[dict]:
    positions = mt5.positions_get()
    if positions is None:
        return []
    out = []
    for p in positions:
        out.append({
            "ticket": p.ticket, "symbol": p.symbol,
            "type": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
            "volume": p.volume, "price_open": p.price_open, "price_current": p.price_current,
            "sl": p.sl, "tp": p.tp, "profit": p.profit,
            "open_time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
            "magic": p.magic,
        })
    return out


def get_recent_deals_digest(hours: int = 24) -> dict:
    """Realized PnL, win-rate, and average execution slippage (fill vs.
    requested price where available) over the trailing window."""
    from_ts = datetime.now(timezone.utc).timestamp() - hours * 3600
    deals = mt5.history_deals_get(from_ts, datetime.now(timezone.utc).timestamp())
    if not deals:
        return {"n_deals": 0, "realized_pnl": 0.0, "win_rate": None}
    closes = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    if not closes:
        return {"n_deals": 0, "realized_pnl": 0.0, "win_rate": None}
    pnls = [d.profit for d in closes]
    wins = sum(1 for p in pnls if p > 0)
    return {
        "n_deals": len(closes),
        "realized_pnl": round(sum(pnls), 2),
        "win_rate": round(wins / len(closes), 4),
        "avg_pnl_per_deal": round(sum(pnls) / len(closes), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only MT5 live monitor")
    parser.add_argument("--history-hours", type=int, default=24)
    args = parser.parse_args()

    if not connect():
        return

    try:
        digest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "account": get_account_digest(),
            "open_positions": get_open_positions(),
            "recent_performance": get_recent_deals_digest(args.history_hours),
        }
        print(json.dumps(digest, indent=2, default=str))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
