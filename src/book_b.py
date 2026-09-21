"""Book B -- time-series momentum on XAUUSD (primary) and US100 (secondary).

Signal follows Goulding, Harvey & Mazzoleni (JFE 2023), which the brief adopts
as Book B's baseline in place of a plain 12-month signal: cross a slow and a
fast trailing-return sign to get four states -- Bull (both +), Bear (both -),
Correction (slow +, fast -), Rebound (slow -, fast +) -- because a single slow
signal is weak precisely at turning points.

Everything here is a POSITION series, not a trade list. A trend book holds a
continuously vol-sized exposure and flips it; there are no stops and no
per-trade risk budget, so the stop-based engine in common/backtest_core.py
(built for the intraday VWAP/ORB strategies) is the wrong shape and is
deliberately not used. Costs are charged on turnover and financing on nights
held, which is how this kind of book actually pays.

NO LOOK-AHEAD. Every signal, filter and volatility estimate is shifted one bar
before it is applied, so the weight held over bar t uses only information
closed by t-1. The brief insists on this for the volatility estimate
(section 6) and it applies just as much to the signal.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from common.financing import financing_return, load_symbol_costs  # noqa: E402

DATA = REPO / "data"

STATE_NAMES = {0: "Bull", 1: "Correction", 2: "Rebound", 3: "Bear"}


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def load(symbol: str, timeframe: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{symbol}_{timeframe}.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def bars_per_day(df: pd.DataFrame) -> float:
    return len(df) / df.index.normalize().nunique()


def periods_per_year(df: pd.DataFrame) -> float:
    years = (df.index[-1] - df.index[0]).days / 365.25
    return len(df) / years if years > 0 else 252.0


# --------------------------------------------------------------------------
# signals
# --------------------------------------------------------------------------

def trailing_sign(close: pd.Series, lookback_bars: int) -> pd.Series:
    """Sign of the trailing return over `lookback_bars`. Zero until it fills."""
    ret = close / close.shift(lookback_bars) - 1.0
    return np.sign(ret).fillna(0.0)


def four_state(slow_sig: pd.Series, fast_sig: pd.Series) -> pd.Series:
    """0 Bull, 1 Correction, 2 Rebound, 3 Bear. Zero signs count as agreement
    with the slow signal, since a flat trailing return is not a turning point."""
    s = np.where(slow_sig >= 0, 1, -1)
    f = np.where(fast_sig >= 0, 1, -1)
    state = np.where((s > 0) & (f > 0), 0,
             np.where((s > 0) & (f < 0), 1,
             np.where((s < 0) & (f > 0), 2, 3)))
    return pd.Series(state, index=slow_sig.index)


def blend_position(close: pd.Series, slow_bars: int, fast_bars: int,
                   mode: str = "blend5050", dynamic_weights: pd.DataFrame | None = None
                   ) -> pd.Series:
    """Raw position in [-1, 1] before filters and vol targeting.

    modes:
      blend5050  static 50/50 of the slow and fast positions -- the brief's
                 baseline. In Bull it is +1, in Bear -1, and in the two turning
                 states the signals cancel to 0, which is the whole point: the
                 blend steps aside when slow and fast disagree instead of
                 backing the slow signal into a reversal.
      slow_only  the pure slow signal (the published 12-month specification at D1)
      fast_only  the pure fast signal
      dma        dual moving-average crossover, kept as a simple comparison
      dynamic    state-conditional tilt; `dynamic_weights` must be supplied and
                 must have been estimated on prior data only
    """
    slow_sig = trailing_sign(close, slow_bars)
    fast_sig = trailing_sign(close, fast_bars)

    if mode == "slow_only":
        pos = slow_sig
    elif mode == "fast_only":
        pos = fast_sig
    elif mode == "blend5050":
        pos = 0.5 * slow_sig + 0.5 * fast_sig
    elif mode == "dma":
        ma_f = close.rolling(fast_bars).mean()
        ma_s = close.rolling(slow_bars).mean()
        pos = np.sign(ma_f - ma_s).fillna(0.0)
    elif mode == "dynamic":
        if dynamic_weights is None:
            raise ValueError("dynamic mode needs walk-forward state weights")
        state = four_state(slow_sig, fast_sig)
        pos = pd.Series(
            [dynamic_weights.get(STATE_NAMES[s], 0.0) if isinstance(dynamic_weights, dict)
             else dynamic_weights.loc[t, STATE_NAMES[s]]
             for t, s in zip(close.index, state)],
            index=close.index)
    else:
        raise ValueError(f"unknown signal mode {mode!r}")

    # Never let a lookback that has not filled masquerade as a flat view.
    warmup = max(slow_bars, fast_bars)
    pos.iloc[:warmup] = 0.0
    return pos.astype(float)


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------

def directional_filter(close: pd.Series, ma_bars: int) -> pd.Series:
    """+1 allows longs only, -1 allows shorts only (brief section 5)."""
    ma = close.rolling(ma_bars).mean()
    return np.sign(close - ma).fillna(0.0)


def vol_regime_flat(returns: pd.Series, vol_window: int, lookback_bars: int,
                    decile: float = 0.90) -> pd.Series:
    """True where trailing realised vol sits in its own top decile.

    The percentile is taken over a TRAILING window, never the full sample. Using
    the whole sample's 90th percentile would leak the future into a filter whose
    entire job is to react to conditions as they arrive.
    """
    rv = returns.rolling(vol_window).std(ddof=1)
    thresh = rv.rolling(lookback_bars, min_periods=vol_window * 3).quantile(decile)
    return (rv > thresh).fillna(False)


def _apply_band(w: pd.Series, band: float) -> pd.Series:
    """Hold the existing weight until the target moves by more than `band`.

    Without this the book is rebalanced on every bar by small drift in the
    volatility scale, paying the spread for adjustments too small to matter.
    A direction change always goes through regardless of size -- the band is
    meant to damp noise, not to delay a genuine signal flip.
    """
    target = w.to_numpy()
    held = np.empty_like(target)
    current = 0.0
    for i, t in enumerate(target):
        if np.sign(t) != np.sign(current) or abs(t - current) > band:
            current = t
        held[i] = current
    return pd.Series(held, index=w.index)


# --------------------------------------------------------------------------
# the backtest
# --------------------------------------------------------------------------

def run(df: pd.DataFrame, costs: dict, *,
        slow_bars: int, fast_bars: int, mode: str = "blend5050",
        use_directional: bool = True, ma_bars: int | None = None,
        use_vol_regime: bool = True, vol_window: int | None = None,
        vol_target: float | None = 0.15, max_leverage: float = 3.0,
        spread_multiplier: float = 1.0, direction: str = "both",
        rebalance_band: float = 0.0,
        dynamic_weights=None) -> dict:
    """Run one configuration and return returns, weights and a summary.

    `spread_multiplier` re-runs the same configuration at 1.5x or 2x the
    measured spread for the brief's section 7 cost-sensitivity test.

    `direction` is "both" or "long_only". It is a TESTED VARIANT, not a
    judgement call: gold rose through most of this sample, so a long-only rule
    will flatter itself here, and the only way to tell whether that is skill or
    hindsight is to put it through the same walk-forward and count it in the
    trial total like any other parameter.

    `rebalance_band` suppresses weight changes smaller than this fraction,
    so the book is not nudged on every bar by small volatility-scale drift.
    """
    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0.0)
    bpd = bars_per_day(df)
    ppy = periods_per_year(df)

    if vol_window is None:
        vol_window = max(2, int(round(20 * bpd)))          # 20-day equivalent
    if ma_bars is None:
        ma_bars = slow_bars

    pos = blend_position(close, slow_bars, fast_bars, mode, dynamic_weights)

    if use_directional:
        allow = directional_filter(close, ma_bars)
        # Keep only the component of the position the filter permits.
        pos = pd.Series(np.where(np.sign(pos) == allow, pos, 0.0), index=pos.index)

    if use_vol_regime:
        # Two years of trailing history for the decile, as the brief specifies
        # for the leg-level gate; same idea applied to the book's own vol.
        flat = vol_regime_flat(ret, vol_window, int(round(252 * 2 * bpd)))
        pos = pos.where(~flat, 0.0)

    # Volatility targeting (overlay, brief section 6). Crude and identical
    # across instruments by design -- the published TSMOM work uses a
    # deliberately simple model and the brief says to resist sophistication.
    if vol_target is not None:
        rv_ann = ret.rolling(vol_window).std(ddof=1) * np.sqrt(ppy)
        scale = (vol_target / rv_ann).replace([np.inf, -np.inf], np.nan)
        scale = scale.clip(upper=max_leverage).fillna(0.0)
        pos = pos * scale

    if direction == "long_only":
        pos = pos.clip(lower=0.0)
    elif direction == "short_only":
        pos = pos.clip(upper=0.0)

    # THE no-look-ahead step: the weight held over bar t is decided at t-1.
    w = pos.shift(1).fillna(0.0).clip(-max_leverage, max_leverage)

    if rebalance_band > 0:
        w = _apply_band(w, rebalance_band)

    # Costs, halved because a change of one unit of weight crosses half the
    # spread, and expressed as a fraction of price so it applies directly to a
    # weight-based return.
    #
    # The spread is the TICK-MEASURED constant from data/costs.csv, not the
    # broker's recorded per-bar `spread` column. That column is not a usable
    # historical cost series on these symbols: XAUUSD reports a median of
    # exactly 0.000 through much of 2019-2023 and XAGUSD records 3.0 price
    # units in 2011 (a 10% spread on $30 silver) with a maximum of 125.0.
    # Using the measured constant keeps this consistent with the cost screen
    # and with the brief's section 3.2; the cost-sensitivity multiples bound
    # the fact that spreads were genuinely wider in the early history.
    spread = pd.Series(costs["typical_spread_price"], index=w.index)
    cost_per_turnover = (spread * spread_multiplier / 2.0) / close
    turnover = w.diff().abs().fillna(w.abs())
    cost = turnover * cost_per_turnover

    fin = financing_return(w, w.index, costs["swap_long_annual"],
                           costs["swap_short_annual"], costs["triple_weekday"])

    gross = w * ret
    net = gross - cost + fin

    return {
        "returns": net, "gross": gross, "cost": cost, "financing": fin,
        "weights": w, "bars_per_day": bpd, "periods_per_year": ppy,
        "buy_hold": ret,
    }
