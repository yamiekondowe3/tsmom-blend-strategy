"""Cross-instrument screening for Book B's validated specification.

READ-ONLY against MT5: symbol_info, symbol_info_tick, copy_rates_range,
copy_ticks_range only. No order functions.

WHY THIS EXISTS. Book B works on gold and on nothing else in the brief's
four-instrument universe. Time-series momentum is documented across 58 liquid
instruments (Moskowitz, Ooi & Pedersen), so one instrument is a constraint of
this broker list rather than of the method. This module applies the SAME fixed
specification -- no refitting, not one parameter re-tuned -- to a much wider
set and asks which instruments it survives on.

THE TRAP, AND THE CONTROLS. Testing 40 instruments and keeping the best five is
textbook data snooping: with enough candidates the top of any ranking looks
excellent even when nothing works. Four controls are applied, and a candidate
has to pass all of them, not just post a high Sharpe:

  1. **The same fixed spec everywhere.** The only selection happening is across
     instruments, not within them. That keeps the multiple-testing problem
     one-dimensional and countable.
  2. **The whole cross-sectional distribution is reported, not just winners.**
     If the median instrument shows roughly zero excess return over
     buy-and-hold, then the top of the list is the right tail of a noise
     distribution and should be read that way.
  3. **Effective sample size, not raw count.** Forty instruments sharing a
     dominant risk factor are nowhere near forty independent tests. The
     deflated Sharpe is computed against the effective count implied by their
     average pairwise correlation.
  4. **Consistency over rolling windows**, so a result driven by one lucky year
     cannot qualify.

Synthetic instruments (Deriv's Volatility, Crash/Boom, Step and Jump indices)
are deliberately included as a NULL CONTROL. They are random processes with
engineered volatility, not markets, so a momentum signal should NOT work on
them. If it does, the engine has a bug rather than an edge -- which makes them
the most informative rows in the output.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DATA = REPO / "data"
UNIVERSE_DIR = DATA / "universe"
REPORTS = REPO / "reports"

# Exact top-level path names on this broker, confirmed by enumerating all 722
# symbols. They are not the obvious ones -- there is no "Forex" or "Energy"
# group; it is "Forex Major" and "Energies" -- and guessing them silently
# returned an empty universe.
#
# The universe is chosen on liquidity and asset-class grounds BEFORE any result
# is seen, which is the defensible way to do it. Deliberately excluded:
#   Equities (448)   single-name risk, not what time-series momentum is
#                    documented on, and 448 more tests would swamp the
#                    multiple-testing correction for little gain
#   ETFs (31)        equity/metal proxies that duplicate the index and metals
#                    exposures already present
#   Forex Micro (19) the same majors in smaller contract sizes, so they would
#                    enter as near-duplicate tests
REAL_GROUPS = ["Forex Major", "Forex Minor", "Metals", "Crypto",
               "Energies", "Soft Commodities", "Stock Indices"]
SYNTHETIC_GROUPS = ["Volatility Indices", "Crash Boom Indices", "Step Indices",
                    "Jump Indices", "Range Break", "DEX Indices",
                    "Multi Step Indices", "Skewed Step", "Trek Indices",
                    "Hybrid Indices", "Basket Indices"]

MIN_YEARS = 6.0          # enough history for several independent rolling windows
MIN_BARS = 3000          # H4 bars. Soft commodities trade ~10h a day, so six
                         # years of them is ~4,000 bars, not the ~9,000 FX has.

# Crypto is limited to the two liquid majors. The group holds 37 symbols, most of
# them thinly traded altcoins listed in the last few years; probing them made MT5
# download each one's full history and stalled the screen for over an hour. They
# would mostly fail the 6-year history bar anyway, and they would enter as
# near-duplicate tests of one crypto-beta factor. Decided on liquidity grounds
# before any result was seen.
CRYPTO_ALLOW = {"BTCUSD", "ETHUSD"}

# A handful of synthetics kept purely as a null control.
NULL_CONTROLS = ["Volatility 75 Index", "Volatility 100 Index", "Step Index",
                 "Boom 1000 Index", "Crash 1000 Index", "Jump 50 Index"]


def enumerate_universe(max_per_group: int | None = None) -> pd.DataFrame:
    """Every symbol with enough H4 history, tagged real vs synthetic."""
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        rows = []
        for s in mt5.symbols_get():
            top = s.path.split("\\")[0]
            kind = ("real" if top in REAL_GROUPS else
                    "synthetic" if top in SYNTHETIC_GROUPS else "other")
            if kind == "other":
                continue
            if kind == "synthetic" and s.name not in NULL_CONTROLS:
                continue
            if top == "Crypto" and s.name not in CRYPTO_ALLOW:
                continue
            info = mt5.symbol_info(s.name)
            if info is None:
                continue
            if not info.visible:
                mt5.symbol_select(s.name, True)

            # Depth probe: ask for ONE bar at the cutoff date rather than
            # downloading the whole series. Pulling 200,000 bars per symbol just
            # to measure how far back it goes takes hours across a 700-symbol
            # broker list; this takes milliseconds and answers the same
            # question -- does history exist at the cutoff, and where does it
            # actually start.
            cutoff = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(
                days=int(MIN_YEARS * 365.25))
            print(f"  probe {s.name}", flush=True)
            head = mt5.copy_rates_from(s.name, mt5.TIMEFRAME_H4, cutoff, 1)
            if head is None or len(head) == 0:
                continue
            a = dt.datetime.fromtimestamp(head[0]["time"], dt.UTC).replace(tzinfo=None)
            if a > cutoff + dt.timedelta(days=30):
                continue        # no data at the cutoff: series starts later
            last = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_H4, 0, 1)
            if last is None or len(last) == 0:
                continue
            b = dt.datetime.fromtimestamp(last[0]["time"], dt.UTC).replace(tzinfo=None)
            # No `years >= MIN_YEARS` test here. The probe asks for a bar AT the
            # cutoff, so the span it measures sits at almost exactly MIN_YEARS
            # -- 5.999 for gold, which has 15.7 -- and such a test rejected
            # every symbol on the broker. Reaching the cutoff is the test;
            # real depth is measured from the full pull.
            years = (b - a).days / 365.25
            rows.append({"symbol": s.name, "group": top, "kind": kind,
                         "description": s.description, "bars": None,
                         "start": a.date().isoformat(), "end": b.date().isoformat(),
                         "years": round(years, 2)})
        d = pd.DataFrame(rows)
        if d.empty:
            # Fail loudly rather than returning an empty frame that breaks
            # further downstream with an unrelated KeyError.
            raise RuntimeError(
                "no symbols matched. Check REAL_GROUPS against the broker's actual "
                "top-level path names -- they are not the obvious ones."
            )
        if max_per_group:
            d = d.sort_values("years", ascending=False).groupby("group").head(max_per_group)
        return d.sort_values(["kind", "group", "symbol"]).reset_index(drop=True)
    finally:
        mt5.shutdown()


def _safe(name: str) -> str:
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-").replace(".", "_")


def pull(symbols: list[str], start: str = "2010-01-01") -> pd.DataFrame:
    """H4 bars for each symbol into data/universe/. Reports achieved coverage."""
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        lo = pd.Timestamp(start, tz="UTC").to_pydatetime()
        hi = pd.Timestamp.now(tz="UTC").to_pydatetime()
        rows = []
        for name in symbols:
            info = mt5.symbol_info(name)
            if info is None:
                continue
            if not info.visible:
                mt5.symbol_select(name, True)
            print(f"  pull {name}", flush=True)
            r = mt5.copy_rates_range(name, mt5.TIMEFRAME_H4, lo, hi)
            if r is None or len(r) < MIN_BARS:
                rows.append({"symbol": name, "bars": 0, "ok": False})
                continue
            df = pd.DataFrame(r).rename(columns={"tick_volume": "volume"})
            df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
            df.to_csv(UNIVERSE_DIR / f"{_safe(name)}_H4.csv", index_label="timestamp")
            rows.append({"symbol": name, "bars": len(df), "ok": True,
                         "start": str(df.index.min())[:10],
                         "end": str(df.index.max())[:10]})
        return pd.DataFrame(rows)
    finally:
        mt5.shutdown()


def costs_for(symbols: list[str], tick_days: int = 7,
              chunk_days: int = 7, subsample: int = 20) -> pd.DataFrame:
    """Contract specs plus tick-measured spreads for the wider universe.

    A much shorter tick window than `build_costs.py` uses for the core four
    (7 days against 30) and a heavier subsample, because this runs across ~100
    symbols and tick pulls dominate the runtime. It is a screening-grade
    estimate and is labelled as such in the output: any instrument that
    survives the screen must have its costs re-measured on the full 30-day
    window before it is traded. The median spread is stable enough over a week
    to rank candidates; the 95th percentile is the figure that suffers, which
    is why the screen is run on medians and the stress column is not used to
    pass anything.
    """
    import MetaTrader5 as mt5
    from src.build_costs import swap_per_unit_per_night, SWAP_MODE_POINTS, \
        SWAP_MODE_INTEREST_CURRENT  # noqa: F401

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        end = dt.datetime.now(dt.UTC).replace(tzinfo=None)
        start = end - dt.timedelta(days=tick_days)
        rows = []
        for name in symbols:
            info = mt5.symbol_info(name)
            if info is None:
                continue
            if not info.visible:
                mt5.symbol_select(name, True)
                info = mt5.symbol_info(name)
            print(f"  ticks {name}", flush=True)
            spreads = []
            cur = start
            while cur < end:
                stop = min(cur + dt.timedelta(days=chunk_days), end)
                # Retry: a tick request for a symbol whose ticks are not yet
                # cached can fail outright while the terminal syncs. The first
                # run of this screen lost 22 of 52 symbols that way -- every
                # forex major, BTC, ETH and gold itself -- which would have
                # tested only minors and exotics without saying so.
                t = None
                for attempt in range(4):
                    t = mt5.copy_ticks_range(name, cur, stop, mt5.COPY_TICKS_INFO)
                    if t is not None and len(t):
                        break
                    time.sleep(3 + 5 * attempt)
                cur = stop
                if t is None or len(t) == 0:
                    print(f"    no ticks {name} chunk: {mt5.last_error()}", flush=True)
                    continue
                t = t[::subsample]
                bid, ask = t["bid"], t["ask"]
                m = (bid > 0) & (ask > 0)
                if m.any():
                    spreads.append((ask[m] - bid[m]).astype(float))
            if not spreads:
                print(f"  SKIP {name}: no ticks in window", flush=True)
                continue
            sp = np.concatenate(spreads)
            tick = mt5.symbol_info_tick(name)
            price = (tick.bid + tick.ask) / 2.0 if tick and tick.bid else info.bid
            if not price or price <= 0:
                print(f"  SKIP {name}: no price", flush=True)
                continue
            try:
                swl = swap_per_unit_per_night(info, price, info.swap_long)
                sws = swap_per_unit_per_night(info, price, info.swap_short)
            except ValueError:
                # unhandled swap convention -- skip rather than guess, since a
                # wrong financing model would silently decide the verdict
                print(f"  SKIP {name}: unhandled swap_mode {info.swap_mode}", flush=True)
                continue
            rows.append({
                "symbol": name,
                "read_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "typical_spread_price": float(np.median(sp)),
                "worst_spread_price": float(np.quantile(sp, 0.95)),
                "swap_long_annual_pct": round(100 * swl * 365 / price, 4),
                "swap_short_annual_pct": round(100 * sws * 365 / price, 4),
                "swap_mode": info.swap_mode,
                "swap_3x_weekday": info.swap_rollover3days,
                "point": info.point, "digits": info.digits,
                "contract_size": info.trade_contract_size,
                "min_lot": info.volume_min, "lot_step": info.volume_step,
                "price_at_read": round(price, info.digits),
                "n_ticks_sampled": len(sp),
                "tick_window_days": tick_days,
                "spread_grade": f"screening ({tick_days}d)",
            })
        return pd.DataFrame(rows)
    finally:
        mt5.shutdown()


def load(symbol: str) -> pd.DataFrame:
    p = UNIVERSE_DIR / f"{_safe(symbol)}_H4.csv"
    df = pd.read_csv(p, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    return df[~df.index.duplicated(keep="last")]
