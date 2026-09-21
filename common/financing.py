"""Overnight financing charged the way the broker actually charges it.

The brief (section 5) is explicit that XAUUSD's swap is negative in both
directions and that "multi-day trend holds pay this nightly -- model it per bar
held, not as an average." A trend book holding for weeks pays this many dozens
of times, and averaging it into a constant hides both the weekly triple charge
and the fact that the cost lands on the bars where the position is largest.

So: swap accrues at ONE instant per day, the rollover, and is skipped entirely
on bars that do not cross it. On one weekday a triple charge covers the
weekend, which is why five rollovers a week add up to seven nights of
financing. The triple-swap weekday differs per instrument on this account --
Wednesday for the metals, Friday for the indices -- and is read from
`symbol_info`, not assumed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# MT5 ENUM_DAY_OF_WEEK: Sunday = 0 ... Saturday = 6.
DAY_NAMES = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday",
             4: "Thursday", 5: "Friday", 6: "Saturday"}


def rollover_nights(index: pd.DatetimeIndex, triple_weekday: int) -> pd.Series:
    """Nights of financing accrued ON each bar.

    A night is counted on the bar that carries the position across a date
    boundary -- detected from the change of UTC date between consecutive bars,
    which is robust to the instrument's particular session break and needs no
    hardcoded rollover hour. The bar *before* the boundary is charged, since
    that is the position being carried over.

    `triple_weekday` is MT5's ENUM_DAY_OF_WEEK for the 3x day. It is applied
    instead of, not in addition to, the weekend's extra calendar days -- the
    broker's triple charge IS the weekend, and counting both would bill the
    weekend twice.

    Weekend dates therefore carry no charge at all. That matters more than it
    sounds: these CFDs open for a short Sunday-evening session, so a naive
    "charge on every date boundary" rule finds SIX date changes a week, adds
    the Wednesday triple on top, and bills 412 nights a year against a true
    365 -- a 13% overstatement of the one cost the brief singles out as
    decisive for a multi-day trend hold. Charging only on Monday-to-Friday
    dates gives 1+1+3+1+1 = 7 nights a week, or 364 a year, which is what the
    broker actually takes.
    """
    if len(index) == 0:
        return pd.Series(dtype=float)
    dates = index.normalize()
    # True where the NEXT bar starts a new date, i.e. this bar carries the
    # position over. The final bar is never charged: the backtest closes there.
    crosses = np.zeros(len(index), dtype=bool)
    crosses[:-1] = dates[1:] != dates[:-1]

    # pandas weekday is Monday=0..Sunday=6; convert to MT5's Sunday=0..Saturday=6
    mt5_weekday = (index.weekday + 1) % 7
    is_weekday = (mt5_weekday >= 1) & (mt5_weekday <= 5)   # Monday..Friday
    charge = crosses & is_weekday

    nights = np.where(charge, 1.0, 0.0)
    nights = np.where(charge & (mt5_weekday == triple_weekday), 3.0, nights)
    return pd.Series(nights, index=index)


def financing_return(weights: pd.Series, index: pd.DatetimeIndex,
                     swap_long_annual: float, swap_short_annual: float,
                     triple_weekday: int) -> pd.Series:
    """Financing as a RETURN on equity, per bar, signed (negative is a cost).

    `weights` are exposures as a fraction of equity, so a weight of 1.0 is a
    notional equal to the account. Long exposure accrues the long rate, short
    exposure the short rate; on this account gold pays to hold long and
    receives a little to hold short, and the indices are negative-carry in
    both directions once a hedge is involved.
    """
    nights = rollover_nights(index, triple_weekday)
    w = pd.Series(weights, index=index).fillna(0.0)
    rate = np.where(w >= 0, swap_long_annual, swap_short_annual)
    return pd.Series(np.abs(w.to_numpy()) * rate * nights.to_numpy() / 365.0, index=index)


def load_symbol_costs(costs_csv: str | "pd.DataFrame", symbol: str) -> dict:
    """Pull the fields the backtest needs out of data/costs.csv."""
    c = costs_csv if isinstance(costs_csv, pd.DataFrame) else pd.read_csv(costs_csv)
    row = c[c.symbol == symbol]
    if row.empty:
        raise KeyError(f"{symbol} not in costs table; run src/build_costs.py")
    r = row.iloc[0]
    return {
        "symbol": symbol,
        "swap_long_annual": float(r["swap_long_annual_pct"]) / 100.0,
        "swap_short_annual": float(r["swap_short_annual_pct"]) / 100.0,
        "triple_weekday": int(r["swap_3x_weekday"]),
        "triple_weekday_name": DAY_NAMES.get(int(r["swap_3x_weekday"]), "?"),
        "typical_spread_price": float(r["typical_spread_price"]),
        "worst_spread_price": float(r["worst_spread_price"]),
        "point": float(r["point"]),
        "digits": int(r["digits"]),
        "read_utc": str(r["read_utc"]),
        "account": str(r["account"]),
    }
