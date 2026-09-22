"""Apply Book B's fixed specification across the wider universe and decide,
with multiple-testing controls, which instruments actually survive.

Run: python src/screen_universe.py --pull     (first time: pulls data + costs)
     python src/screen_universe.py            (re-score from cached data)
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
import src.universe as un  # noqa: E402
from common.financing import financing_return  # noqa: E402
from common.portfolio import (  # noqa: E402
    summarize, effective_sample_size, average_pairwise_correlation,
)
from common.validation import (  # noqa: E402
    sharpe_per_period, expected_max_sharpe, probabilistic_sharpe_ratio,
)

DATA = un.DATA
REPORTS = un.REPORTS

# The specification, unchanged from Book B. Nothing here is re-tuned per
# instrument -- that is the whole point of the exercise.
SLOW_D, FAST_D, VOL_TARGET, MAX_LEV = 60, 10, 0.15, 3.0
DIRECTION = "long_only"

# Selection bar. A candidate must clear ALL of these, not post one good number.
MIN_EXCESS_SHARPE = 0.20     # over costed buy-and-hold of the same instrument
MIN_WINDOW_HIT_RATE = 0.60   # fraction of rolling 2y windows beating the benchmark
MIN_SHARPE = 0.40


def costs_dict(row: pd.Series) -> dict:
    return {"typical_spread_price": float(row["typical_spread_price"]),
            "worst_spread_price": float(row["worst_spread_price"]),
            "swap_long_annual": float(row["swap_long_annual_pct"]) / 100.0,
            "swap_short_annual": float(row["swap_short_annual_pct"]) / 100.0,
            "triple_weekday": int(row["swap_3x_weekday"])}


def cfd_buy_hold(df: pd.DataFrame, costs: dict, target_vol_of: pd.Series,
                 index: pd.DatetimeIndex) -> pd.Series:
    """Vol-matched buy-and-hold of the same CFD, charged the same nightly swap."""
    ret = df["close"].astype(float).pct_change().fillna(0.0).loc[index]
    sv, bv = target_vol_of.std(ddof=1), ret.std(ddof=1)
    k = float(sv / bv) if bv > 0 else 0.0
    w = pd.Series(k, index=index)
    fin = financing_return(w, index, costs["swap_long_annual"],
                           costs["swap_short_annual"], costs["triple_weekday"])
    entry = pd.Series(0.0, index=index)
    if len(index):
        entry.iloc[0] = k * (costs["typical_spread_price"] / 2.0) / float(
            df["close"].loc[index[0]])
    return k * ret + fin - entry


def score_symbol(symbol: str, costs: dict, spread_mult: float = 1.0) -> dict | None:
    df = un.load(symbol)
    if len(df) < un.MIN_BARS:
        return None
    bpd = bb.bars_per_day(df)
    ppy = int(round(bb.periods_per_year(df)))
    r = bb.run(df, costs,
               slow_bars=max(2, int(round(SLOW_D * bpd))),
               fast_bars=max(1, int(round(FAST_D * bpd))),
               mode="blend5050", direction=DIRECTION,
               vol_target=VOL_TARGET, max_leverage=MAX_LEV,
               spread_multiplier=spread_mult)
    net, w = r["returns"], r["weights"]
    bench = cfd_buy_hold(df, costs, net, net.index)
    s = summarize(net, periods_per_year=ppy)
    b = summarize(bench, periods_per_year=ppy)
    years = (net.index[-1] - net.index[0]).days / 365.25
    flips = float((np.sign(w).diff().fillna(0) != 0).sum())

    # rolling 2-year consistency, same parameters throughout
    hits, tot, start = 0, 0, net.index.min()
    while True:
        stop = start + pd.DateOffset(days=int(2 * 365.25))
        if stop > net.index.max():
            break
        seg = net.loc[start:stop]
        if len(seg) > 100:
            bm = cfd_buy_hold(df, costs, seg, seg.index)
            sa = summarize(seg, periods_per_year=ppy).get("sharpe", 0)
            sbm = summarize(bm, periods_per_year=ppy).get("sharpe", 0)
            tot += 1
            hits += int(sa > sbm)
        start = stop

    cagr, dd = s.get("cagr", 0), s.get("max_drawdown", 0)
    return {
        "symbol": symbol, "years": round(years, 2), "bars": len(df),
        "sharpe": round(s.get("sharpe", 0), 3), "cagr": round(cagr, 4),
        "vol": round(s.get("vol", 0), 4), "max_dd": round(dd, 3),
        "calmar": round(cagr / abs(dd), 3) if dd else np.nan,
        "bench_sharpe": round(b.get("sharpe", 0), 3),
        "bench_cagr": round(b.get("cagr", 0), 4),
        "excess_sharpe": round(s.get("sharpe", 0) - b.get("sharpe", 0), 3),
        "beats_bh": bool(s.get("sharpe", 0) > b.get("sharpe", 0)),
        "windows": tot, "window_hits": hits,
        "window_hit_rate": round(hits / tot, 3) if tot else np.nan,
        "trades_per_week": round(flips / years / 52, 2) if years else np.nan,
        "in_market": round(float((w.abs() > 1e-9).mean()), 3),
        "_returns": net,
    }


def screen(meta: pd.DataFrame, costs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cmap = {r["symbol"]: costs_dict(r) for _, r in costs.iterrows()}
    rows, series = [], {}
    for _, m in meta.iterrows():
        sym = m["symbol"]
        if sym not in cmap:
            continue
        try:
            sc = score_symbol(sym, cmap[sym])
        except Exception as e:  # a single bad symbol must not kill the screen
            print(f"  skip {sym}: {e}")
            continue
        if sc is None:
            continue
        series[sym] = sc.pop("_returns")
        sc["group"] = m["group"]
        sc["kind"] = m["kind"]
        rows.append(sc)
        print(f"  {sym:<28} sh {sc['sharpe']:+.2f} vs bh {sc['bench_sharpe']:+.2f} "
              f"excess {sc['excess_sharpe']:+.2f} hits {sc['window_hits']}/{sc['windows']}",
              flush=True)
    res = pd.DataFrame(rows)

    # --- multiple-testing accounting on the REAL instruments only ------------
    real = res[res.kind == "real"]
    rmat = pd.DataFrame({k: v for k, v in series.items()
                         if k in set(real.symbol)}).dropna(how="all")
    rho = average_pairwise_correlation(rmat) if rmat.shape[1] > 1 else 0.0
    n_eff = effective_sample_size(len(real), rho)
    sr_list = [sharpe_per_period(series[s]) for s in real.symbol]
    sr_var = float(np.var(sr_list, ddof=1)) if len(sr_list) > 1 else 0.0

    stats = {
        "n_real_tested": int(len(real)),
        "n_synthetic_controls": int((res.kind == "synthetic").sum()),
        "avg_pairwise_correlation": round(rho, 4),
        "effective_independent_tests": round(n_eff, 2),
        "median_excess_sharpe": round(float(real["excess_sharpe"].median()), 4),
        "mean_excess_sharpe": round(float(real["excess_sharpe"].mean()), 4),
        "pct_beating_bh": round(float(real["beats_bh"].mean()), 4),
        "sharpe_variance_across_instruments": sr_var,
        "expected_max_sharpe_under_null": round(
            expected_max_sharpe(max(2, int(round(n_eff))), sr_var), 6),
    }
    return res, {"stats": stats, "series": series, "sr_list": sr_list}


def select(res: pd.DataFrame) -> pd.DataFrame:
    real = res[res.kind == "real"].copy()
    real["passes"] = ((real["excess_sharpe"] >= MIN_EXCESS_SHARPE) &
                      (real["sharpe"] >= MIN_SHARPE) &
                      (real["window_hit_rate"] >= MIN_WINDOW_HIT_RATE))
    return real.sort_values("excess_sharpe", ascending=False)
