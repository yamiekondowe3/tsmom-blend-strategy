"""Section 6 overlay -- combining instrument books into one portfolio.

Two things live here, both prescribed by the brief and neither previously built:

  * **Inverse-volatility combination.** Each book is sized by the inverse of
    its own realised volatility so that a quiet book and a violent one
    contribute comparable risk, rather than the violent one dominating.

  * **One kill switch, not one per book.** The brief is emphatic: both books
    fail on the same event, because a volatility spike breaks cointegration and
    whipsaws trend at the same moment. Scaling each book separately leaves the
    portfolio at its most correlated exactly when that costs money. So the
    trigger is a single portfolio-level one -- aggregate realised volatility
    above its own trailing 95th percentile flattens everything.

The threshold is taken over a TRAILING window, never the whole sample. A kill
switch whose trigger level was computed from data it has not seen yet would
fire with hindsight and look far better than it could ever be live.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402


def align(books: dict[str, dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Line up per-book net returns and weights on a common bar index."""
    rets = pd.DataFrame({k: v["returns"] for k, v in books.items()})
    wts = pd.DataFrame({k: v["weights"] for k, v in books.items()})
    idx = rets.dropna(how="all").index
    return rets.reindex(idx).fillna(0.0), wts.reindex(idx).fillna(0.0)


def inverse_vol_allocation(rets: pd.DataFrame, window: int) -> pd.DataFrame:
    """Per-book allocation proportional to 1/vol, normalised to sum to 1.

    Shifted one bar: the allocation applied to bar t is computed from returns
    through t-1.
    """
    vol = rets.rolling(window).std(ddof=1)
    inv = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
    alloc = inv.div(inv.sum(axis=1), axis=0)
    return alloc.shift(1).fillna(0.0)


def kill_switch(portfolio_ret: pd.Series, window: int, lookback: int,
                pctile: float = 0.95) -> pd.Series:
    """True where aggregate realised vol exceeds its trailing `pctile`.

    Returns a mask to flatten on. Shifted one bar so the decision to go flat
    over bar t is made from information closed at t-1.
    """
    rv = portfolio_ret.rolling(window).std(ddof=1)
    thr = rv.rolling(lookback, min_periods=window * 3).quantile(pctile)
    # shift() on a boolean Series introduces NaN and promotes the dtype, so the
    # cast back to bool is required -- `where` rejects a non-boolean mask.
    return (rv > thr).shift(1).fillna(False).astype(bool)


def build_portfolio(books: dict[str, dict], bars_per_day: float,
                    use_kill_switch: bool = True,
                    equal_weight: bool = False) -> dict:
    """Combine books, optionally apply the kill switch, and report."""
    rets, wts = align(books)
    vol_window = max(2, int(round(20 * bars_per_day)))

    if equal_weight:
        alloc = pd.DataFrame(1.0 / rets.shape[1], index=rets.index, columns=rets.columns)
    else:
        alloc = inverse_vol_allocation(rets, vol_window)

    combined = (rets * alloc).sum(axis=1)

    killed = pd.Series(False, index=combined.index)
    if use_kill_switch:
        killed = kill_switch(combined, vol_window, int(round(252 * 2 * bars_per_day)))
        combined = combined.where(~killed, 0.0)

    gross_exposure = (wts.abs() * alloc).sum(axis=1)
    return {
        "returns": combined,
        "allocation": alloc,
        "book_returns": rets,
        "gross_exposure": gross_exposure,
        "killed": killed,
        "pct_time_killed": float(killed.mean()),
    }


def trade_frequency(books: dict[str, dict]) -> dict:
    """Direction changes per week, per book and combined.

    The brief's section 1.4 target is 2-3 trades a week across the whole
    portfolio, and section 7 item 7 requires reporting the realised figure
    honestly -- including when it falls short, which is the only acceptable
    way to miss it.
    """
    out, total = {}, 0.0
    for name, b in books.items():
        w = b["weights"]
        years = (w.index[-1] - w.index[0]).days / 365.25
        flips = float((np.sign(w).diff().fillna(0) != 0).sum())
        per_week = flips / years / 52 if years > 0 else np.nan
        out[name] = round(per_week, 2)
        total += per_week
    out["COMBINED"] = round(total, 2)
    return out
