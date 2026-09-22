"""Monitor the demo deployment: account, positions, and the EA's own decisions.

READ-ONLY against MT5 -- reads account, positions and history only. It cannot
place, modify or close anything; stopping the EA is a deliberate manual act
(see reports/demo_deployment.md).

Run: python src/demo_monitor.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TERMINAL = (Path(os.environ["APPDATA"]) / "MetaQuotes" / "Terminal"
            / "FB9A56D617EDDDFE29EE54EBEFFE96C1")
MAGIC = 20260922


def main() -> int:
    import MetaTrader5 as mt5
    if not mt5.initialize(timeout=60000):
        print(f"MT5 not reachable: {mt5.last_error()}", file=sys.stderr)
        return 1
    try:
        a = mt5.account_info()
        kind = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(a.trade_mode)
        print(f"{a.login}@{a.server} [{kind}]  balance {a.balance:,.2f} "
              f"equity {a.equity:,.2f} free margin {a.margin_free:,.2f} "
              f"open P/L {a.profit:+,.2f}")
        if a.trade_mode != 0:
            print("  !! NOT a demo account -- the EA blocks trading here by design.")

        pos = mt5.positions_get() or []
        mine = [p for p in pos if p.magic == MAGIC]
        print(f"\npositions (magic {MAGIC}): {len(mine)}  "
              f"[other positions on the account: {len(pos) - len(mine)}]")
        for p in mine:
            cs = mt5.symbol_info(p.symbol).trade_contract_size
            notional = p.volume * cs * p.price_current
            print(f"  {p.symbol:<8} {'BUY ' if p.type == 0 else 'SELL'} {p.volume:>6} lots "
                  f"@ {p.price_open:,.2f}  P/L {p.profit:+8.2f}  "
                  f"notional {notional:,.0f} ({notional / a.equity:5.1%} of equity)  "
                  f"since {dt.datetime.fromtimestamp(p.time, dt.UTC):%Y-%m-%d %H:%M}")

        since = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
        deals = [d for d in (mt5.history_deals_get(since, dt.datetime.now(dt.UTC)) or [])
                 if d.magic == MAGIC]
        print(f"\ndeals in the last 7 days: {len(deals)}")
        for d in deals[-15:]:
            print(f"  {dt.datetime.fromtimestamp(d.time, dt.UTC):%Y-%m-%d %H:%M} "
                  f"{d.symbol:<8} {'buy' if d.type == 0 else 'sell'} {d.volume} @ {d.price:,.2f} "
                  f"profit {d.profit:+.2f}")
    finally:
        mt5.shutdown()

    logs = sorted((TERMINAL / "MQL5" / "Logs").glob("*.log"))
    if logs:
        txt = logs[-1].read_text(encoding="utf-16-le", errors="ignore")
        lines = [l for l in txt.splitlines() if "TSMOM_Blend_EA" in l]
        print(f"\nlast EA decisions ({logs[-1].name}):")
        for l in lines[-12:]:
            print("  " + l.split("\t")[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
