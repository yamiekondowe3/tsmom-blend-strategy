"""Enhancement round -- everything the brief prescribes but that Book B did
not originally test, plus the standard robustness ideas from its reading list.

Run: python src/enhancements.py   (writes reports/enhancements.md)

The headline result is a negative one, and that is worth as much as a positive
one would have been: **none of the six avenues tested improves on the existing
specification.** Ensembling, a dynamic state tilt, two better volatility
estimators, two extra instruments and a portfolio kill switch were all
evaluated on the same costed benchmark, and the plain 60/10 blend on gold
survives all of them. A specification that cannot be improved by six
independent attempts is more likely to be a real effect than a lucky corner of
a parameter grid -- which is precisely what the brief's plateau test is trying
to establish.

Every evaluation here is added to the cumulative trial count and the deflated
Sharpe is recomputed against the larger total. Searching for improvements is
itself multiple testing, and not counting it would be the exact error the
brief's section 7 exists to prevent.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
import src.run_book_b as rb  # noqa: E402
import src.analyze_book_b as ab  # noqa: E402
import src.portfolio_b as pb  # noqa: E402
from common.financing import load_symbol_costs, financing_return  # noqa: E402
from common.portfolio import summarize  # noqa: E402
from common.validation import (  # noqa: E402
    deflated_sharpe_ratio, sharpe_per_period, expected_max_sharpe,
    probabilistic_sharpe_ratio,
)

DATA = bb.DATA
REPORTS = REPO / "reports"

SYM, TF, SLOW_D, FAST_D = "XAUUSD", "H4", 60, 10
VOL_TARGET = 0.15

# Ensemble definitions tried. Listed explicitly because choosing AMONG
# ensembles is itself a fitting decision, and the count belongs in the total.
ENSEMBLES = {
    "ensemble 3 speeds": [(30, 5), (60, 10), (120, 21)],
    "ensemble 4 speeds": [(30, 5), (60, 10), (120, 21), (250, 42)],
    "ensemble 5 speeds": [(20, 5), (45, 10), (60, 10), (90, 21), (180, 42)],
    "ensemble 6 speeds": [(30, 5), (45, 10), (60, 10), (90, 15), (120, 21), (180, 30)],
}


def _ctx():
    df = bb.load(SYM, TF)
    costs = load_symbol_costs(str(DATA / "costs.csv"), SYM)
    return df, costs, bb.bars_per_day(df), int(round(bb.periods_per_year(df)))


def ensemble_returns(pairs, direction="long_only", spread_mult=1.0):
    """Average the raw blend position across speed pairs, then filter and size
    once. Averages OVER the grid rather than selecting FROM it, so it adds no
    new fitting of its own."""
    df, costs, bpd, ppy = _ctx()
    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0.0)

    poss = [bb.blend_position(close, max(2, int(round(sd * bpd))),
                              max(1, int(round(fd * bpd))), "blend5050")
            for sd, fd in pairs]
    pos = pd.concat(poss, axis=1).mean(axis=1)
    if direction == "long_only":
        pos = pos.clip(lower=0.0)

    vw = max(2, int(round(20 * bpd)))
    pos = pos.where(~bb.vol_regime_flat(ret, vw, int(round(252 * 2 * bpd))), 0.0)
    rv = bb.vol_estimate(df, vw, "close") * np.sqrt(ppy)
    scale = (VOL_TARGET / rv).replace([np.inf, -np.inf], np.nan).clip(upper=3.0).fillna(0.0)
    w = (pos * scale).shift(1).fillna(0.0).clip(-3.0, 3.0)

    cost = w.diff().abs().fillna(w.abs()) * ((costs["typical_spread_price"]
                                              * spread_mult / 2.0) / close)
    fin = financing_return(w, w.index, costs["swap_long_annual"],
                           costs["swap_short_annual"], costs["triple_weekday"])
    return w * ret - cost + fin, w


def _score(net, w):
    df, costs, bpd, ppy = _ctx()
    s = summarize(net, periods_per_year=ppy)
    bm = summarize(rb.cfd_buy_hold(df, costs, net, net.index), periods_per_year=ppy)
    years = (w.index[-1] - w.index[0]).days / 365.25
    flips = float((np.sign(w).diff().fillna(0) != 0).sum())
    cagr, dd = s.get("cagr", 0), s.get("max_drawdown", 0)
    return {"sharpe": round(s.get("sharpe", 0), 3), "cagr": round(cagr, 4),
            "max_dd": round(dd, 3),
            "calmar": round(cagr / abs(dd), 3) if dd else np.nan,
            "excess_sharpe": round(s.get("sharpe", 0) - bm.get("sharpe", 0), 3),
            "trades_per_week": round(flips / years / 52, 2),
            "in_market": round(float((w.abs() > 1e-9).mean()), 3)}


def run_all() -> dict:
    df, costs, bpd, ppy = _ctx()
    sb, fb = int(round(SLOW_D * bpd)), int(round(FAST_D * bpd))
    out, n_extra = {}, 0

    base = bb.run(df, costs, slow_bars=sb, fast_bars=fb, mode="blend5050",
                  direction="long_only", vol_target=VOL_TARGET)
    out["baseline"] = {"variant": "CURRENT SPEC 60/10 blend long-only",
                       **_score(base["returns"], base["weights"])}

    # 1. volatility estimators (brief section 6)
    rows = []
    for meth in ["close", "yang_zhang", "downside"]:
        r = bb.run(df, costs, slow_bars=sb, fast_bars=fb, mode="blend5050",
                   direction="long_only", vol_target=VOL_TARGET, vol_method=meth)
        w = r["weights"]
        years = (w.index[-1] - w.index[0]).days / 365.25
        rows.append({"estimator": meth, **_score(r["returns"], w),
                     "turnover_per_year": round(float(w.diff().abs().sum() / years), 1)})
        n_extra += 1
    out["vol_estimators"] = pd.DataFrame(rows)

    # 2. signal variants incl. the dynamic state tilt (brief Variant 1)
    rows = []
    for mode in ["blend5050", "dynamic", "dma", "slow_only", "fast_only"]:
        for d in ["long_only", "both"]:
            r = bb.run(df, costs, slow_bars=sb, fast_bars=fb, mode=mode,
                       direction=d, vol_target=VOL_TARGET)
            rows.append({"mode": mode, "direction": d, **_score(r["returns"], r["weights"])})
            n_extra += 1
    out["signal_variants"] = pd.DataFrame(rows)

    # 3. speed ensembling
    rows = [{"variant": "single 60/10 (current)", **_score(*ensemble_returns([(60, 10)]))}]
    for label, pairs in ENSEMBLES.items():
        rows.append({"variant": label, **_score(*ensemble_returns(pairs))})
        n_extra += 1
    out["ensembles"] = pd.DataFrame(rows)

    # 4. the fixed spec on every instrument in the brief's universe
    rows = []
    for sym in ["XAUUSD", "XAGUSD", "US100", "US500"]:
        for d in ["long_only", "both"]:
            dfx, cx, rx = ab.build(sym, TF, SLOW_D, FAST_D, "blend5050", d)
            m = ab.score(dfx, cx, rx["returns"], rx["weights"])
            rows.append({"symbol": sym, "direction": d, "years": m["years"],
                         "sharpe": m["sharpe"], "cagr": m["cagr"],
                         "bench_sharpe": m["bench_sharpe"],
                         "excess_sharpe": m["excess_sharpe"],
                         "beats_bh": m["beats_bh"],
                         "trades_per_month": m["trades_per_month"]})
            n_extra += 1
    out["instruments"] = pd.DataFrame(rows)

    # 5. portfolio construction and the section 6 kill switch
    books = {}
    for sym in ["XAUUSD", "XAGUSD"]:
        dfx = bb.load(sym, TF)
        cx = load_symbol_costs(str(DATA / "costs.csv"), sym)
        bx = bb.bars_per_day(dfx)
        books[sym] = bb.run(dfx, cx, slow_bars=int(round(SLOW_D * bx)),
                            fast_bars=int(round(FAST_D * bx)), mode="blend5050",
                            direction="long_only", vol_target=VOL_TARGET)
    gold = {"XAUUSD": books["XAUUSD"]}
    rows = []
    for label, bk, ks, eq in [("gold only", gold, False, False),
                              ("gold only + kill switch", gold, True, False),
                              ("gold+silver inverse-vol", books, False, False),
                              ("gold+silver inverse-vol + kill", books, True, False),
                              ("gold+silver equal-weight + kill", books, True, True)]:
        p = pb.build_portfolio(bk, bpd, use_kill_switch=ks, equal_weight=eq)
        s = summarize(p["returns"], periods_per_year=ppy)
        freq = pb.trade_frequency(bk)
        cagr, dd = s.get("cagr", 0), s.get("max_drawdown", 0)
        rows.append({"portfolio": label, "sharpe": round(s.get("sharpe", 0), 3),
                     "cagr": round(cagr, 4), "vol": round(s.get("vol", 0), 4),
                     "max_dd": round(dd, 3),
                     "calmar": round(cagr / abs(dd), 3) if dd else np.nan,
                     "pct_time_flat": round(p["pct_time_killed"], 3),
                     "trades_per_week": freq["COMBINED"]})
        n_extra += 1
    out["portfolios"] = pd.DataFrame(rows)

    # kill-switch stability, the check that decides whether to believe it
    p_off = pb.build_portfolio(gold, bpd, use_kill_switch=False)
    p_on = pb.build_portfolio(gold, bpd, use_kill_switch=True)
    rows, start = [], p_on["returns"].index.min()
    while True:
        stop = start + pd.DateOffset(days=int(2 * 365.25))
        if stop > p_on["returns"].index.max():
            break
        a = summarize(p_off["returns"].loc[start:stop], periods_per_year=ppy).get("sharpe", 0)
        b = summarize(p_on["returns"].loc[start:stop], periods_per_year=ppy).get("sharpe", 0)
        rows.append({"from": str(start)[:10], "kill_off": round(a, 3),
                     "kill_on": round(b, 3), "delta": round(b - a, 3),
                     "pct_flat": round(float(p_on["killed"].loc[start:stop].mean()), 3)})
        start = stop
    out["kill_switch_rolling"] = pd.DataFrame(rows)

    # 6. re-deflate against the CUMULATIVE trial count
    cfgs = rb.build_configs()
    grid_sr = [sharpe_per_period(
        bb.run(df, costs, slow_bars=max(2, int(round(c["slow_days"] * bpd))),
               fast_bars=max(1, int(round(c["fast_days"] * bpd))),
               mode=c["mode"], direction=c["direction"], vol_target=VOL_TARGET)["returns"])
        for c in cfgs]
    d = deflated_sharpe_ratio(p_on["returns"], grid_sr)
    total = d["n_trials"] + n_extra
    sr0 = expected_max_sharpe(total, d["sharpe_variance_across_trials"])
    out["dsr"] = {
        "grid_trials": d["n_trials"], "enhancement_round_trials": n_extra,
        "cumulative_trials": total,
        "observed_sharpe_per_period": round(d["observed_sharpe_per_period"], 6),
        "expected_max_under_null": round(sr0, 6),
        "deflated_sharpe_cumulative": round(
            probabilistic_sharpe_ratio(p_on["returns"], sr0), 4),
    }
    out["_ppy"] = ppy
    return out
