"""Step 1 -- resolve canonical instrument names to this broker's spelling, and
measure the server clock offset.

READ-ONLY. Calls only initialize / account_info / symbols_get / symbol_info /
symbol_info_tick / symbol_select. It never calls order_send, order_check or any
other function that can place, modify or close a position -- see the project
brief, section 2, which forbids that outright until build step 8.

Why this script exists at all: Deriv does not use standard tickers. The
NASDAQ-100 CFD is named "US Tech 100" and the S&P 500 CFD is "US SP 500".
Passing "US100" straight to MT5 returns None, and a None that is not checked
for looks identical to "no data" further downstream. Resolving once, writing
the answer to disk, and failing loudly here keeps that ambiguity out of every
later stage.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import MetaTrader5 as mt5

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

# Canonical name -> the candidate spellings to try, best first. The exact
# strings came from enumerating all 722 symbols on this account; the fallbacks
# are kept so the script still resolves if the broker renames something.
CANDIDATES = {
    "US100": ["US Tech 100", "US100", "USTEC", "NAS100"],
    "US500": ["US SP 500", "US500", "SPX500", "US 500"],
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
}

# A synthetic index, chosen because it ticks every ~2 seconds around the clock
# including weekends. Measuring the server offset against a real instrument is
# unreliable: if gold's last tick was 30 minutes ago the "offset" you compute
# is really just quote staleness. This symbol has no such gap.
CLOCK_SYMBOL = "Volatility 75 Index"


def resolve_one(canonical: str, candidates: list[str]) -> dict:
    for name in candidates:
        info = mt5.symbol_info(name)
        if info is None:
            continue
        if not info.visible:
            mt5.symbol_select(name, True)
            info = mt5.symbol_info(name)
        return {
            "canonical": canonical,
            "broker_symbol": name,
            "description": info.description,
            "path": info.path,
            "digits": info.digits,
            "point": info.point,
            "contract_size": info.trade_contract_size,
            "resolved_from": candidates.index(name),
        }
    return {"canonical": canonical, "broker_symbol": None,
            "tried": candidates, "description": None}


def server_offset_hours() -> dict:
    """Server clock minus UTC, in hours, measured off a 24/7 synthetic index."""
    info = mt5.symbol_info(CLOCK_SYMBOL)
    if info is None:
        return {"method": "unavailable", "clock_symbol": CLOCK_SYMBOL,
                "offset_hours": None,
                "note": "clock symbol not on this account; offset NOT measured"}
    # A symbol that has just been made visible has no tick cached yet, and MT5
    # reports that as time=0 rather than as an error. Taken at face value it
    # dates the server to 1970 and yields an "offset" of about -497,000 hours.
    # Select first, then poll briefly for a tick that actually has a timestamp.
    if not info.visible:
        mt5.symbol_select(CLOCK_SYMBOL, True)
    tick = None
    for _ in range(20):
        t = mt5.symbol_info_tick(CLOCK_SYMBOL)
        if t is not None and t.time:
            tick = t
            break
        time.sleep(0.25)
    if tick is None:
        return {"method": "unavailable", "clock_symbol": CLOCK_SYMBOL,
                "offset_hours": None,
                "note": "no timestamped tick arrived; offset NOT measured"}

    server = dt.datetime.fromtimestamp(tick.time, dt.UTC).replace(tzinfo=None)
    utc = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    raw = (server - utc).total_seconds() / 3600.0
    # Brokers run whole- or half-hour offsets; snap to the nearest half hour so
    # a couple of seconds of tick latency doesn't show up as a fake offset.
    return {
        "method": f"tick time of {CLOCK_SYMBOL!r} vs UTC now",
        "clock_symbol": CLOCK_SYMBOL,
        "offset_hours": round(raw * 2) / 2,
        "raw_offset_hours": round(raw, 4),
        "server_time_observed": server.isoformat(),
        "utc_time_observed": utc.isoformat(),
    }


def main() -> int:
    if not mt5.initialize():
        print(f"FATAL: MT5 initialize failed: {mt5.last_error()}", file=sys.stderr)
        return 1
    try:
        acc = mt5.account_info()
        resolved = {c: resolve_one(c, cands) for c, cands in CANDIDATES.items()}

        missing = [c for c, r in resolved.items() if r["broker_symbol"] is None]

        payload = {
            "read_utc": dt.datetime.now(dt.UTC).isoformat(),
            "account": {
                "login": acc.login,
                "server": acc.server,
                "currency": acc.currency,
                "trade_mode": acc.trade_mode,
                "trade_mode_label": {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(acc.trade_mode),
            },
            "provisional": acc.trade_mode != 2,
            "provisional_note": (
                "Costs read from a DEMO account. Demo spreads and swaps can differ "
                "from live. Every figure derived from this file must be re-read on "
                "the live account before capital is committed."
            ),
            "symbols": resolved,
            "server_clock": server_offset_hours(),
            "total_symbols_on_account": len(mt5.symbols_get()),
        }

        DATA.mkdir(parents=True, exist_ok=True)
        for name in ("symbol_map.json", "broker_config.json"):
            (DATA / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

        for c, r in resolved.items():
            if r["broker_symbol"]:
                print(f"OK   {c:<7} -> {r['broker_symbol']!r:<16} ({r['description']})")
            else:
                print(f"FAIL {c:<7} -> not found; tried {r['tried']}")
        print(f"\nserver clock offset: {payload['server_clock']['offset_hours']} h vs UTC")
        print(f"account: {acc.login}@{acc.server} "
              f"({payload['account']['trade_mode_label']})")

        if missing:
            # Hard stop, per the brief: pair A1 is defined on these specific
            # instruments. Silently substituting a similar-looking index would
            # produce a cost screen for a pair nobody intends to trade.
            print(f"\nFATAL: unresolved symbols {missing}. Stopping -- do NOT "
                  f"substitute a similar index.", file=sys.stderr)
            return 2
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
