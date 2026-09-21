"""Book B -- the full evidence pack, and the script that writes reports/book_b.md.

The conclusion this produces is NOT "here is a profitable system". It is a
ranked, costed comparison against the one benchmark that can tell a signal
apart from an instrument's drift, with every control the brief's section 7
demands attached to it.

Read the CONCLUSIONS section of the generated report before the tables.
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
from common.financing import load_symbol_costs  # noqa: E402
from common.portfolio import summarize  # noqa: E402
from common.validation import deflated_sharpe_ratio, sharpe_per_period  # noqa: E402

DATA = REPO / "data"
REPORTS = REPO / "reports"

VOL_TARGET = 0.15

# The specifications under test. The lookbacks are the brief's and the
# literature's, NOT values found by searching this data -- which is the point.
# Goulding/Harvey/Mazzoleni's medium speed is slow 60d / fast 10d; the D1 slow
# pair is the published 12-month / 1-month specification.
CANDIDATES = [
    ("XAUUSD", "H4", 60, 10, "blend5050", "long_only", "B1a  gold H4 medium, long-only"),
    ("XAUUSD", "H4", 60, 10, "blend5050", "both", "B1b  gold H4 medium, long/short"),
    ("XAUUSD", "D1", 250, 21, "blend5050", "both", "B1c  gold D1 slow (published spec)"),
    ("XAUUSD", "D1", 250, 21, "blend5050", "long_only", "B1d  gold D1 slow, long-only"),
    ("US100", "H4", 60, 10, "blend5050", "both", "B2a  US100 H4 medium, long/short"),
    ("US100", "H4", 60, 10, "blend5050", "long_only", "B2b  US100 H4 medium, long-only"),
]

PERIODS = {
    "XAUUSD": [
        ("2011-2015 gold bear", "2011-01-01", "2015-12-31"),
        ("2016-2019 recovery", "2016-01-01", "2019-12-31"),
        ("2020-2022 covid/rates", "2020-01-01", "2022-12-31"),
        ("2023-2026 bull", "2023-01-01", "2026-12-31"),
    ],
    "US100": [
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
        ("2026 ytd", "2026-01-01", "2026-12-31"),
    ],
}


def build(symbol, tf, slow_d, fast_d, mode, direction, **kw):
    df = bb.load(symbol, tf)
    costs = load_symbol_costs(str(DATA / "costs.csv"), symbol)
    bpd = bb.bars_per_day(df)
    r = bb.run(df, costs,
               slow_bars=max(2, int(round(slow_d * bpd))),
               fast_bars=max(1, int(round(fast_d * bpd))),
               mode=mode, direction=direction, vol_target=VOL_TARGET, **kw)
    return df, costs, r


def score(df, costs, net, weights, lo=None, hi=None) -> dict:
    seg = net.loc[lo:hi] if (lo or hi) else net
    if len(seg) < 50:
        return {}
    ppy = int(round(bb.periods_per_year(df)))
    bench = rb.cfd_buy_hold(df, costs, seg, seg.index)
    s = summarize(seg, periods_per_year=ppy)
    b = summarize(bench, periods_per_year=ppy)
    w = weights.loc[seg.index]
    years = (seg.index[-1] - seg.index[0]).days / 365.25
    flips = int((np.sign(w).diff().fillna(0) != 0).sum())
    return {
        "sharpe": round(s.get("sharpe", 0), 3),
        "cagr": round(s.get("cagr", 0), 4),
        "vol": round(s.get("vol", 0), 4),
        "max_dd": round(s.get("max_drawdown", 0), 3),
        "calmar": round(s.get("calmar", 0), 3),
        "bench_sharpe": round(b.get("sharpe", 0), 3),
        "bench_cagr": round(b.get("cagr", 0), 4),
        "excess_sharpe": round(s.get("sharpe", 0) - b.get("sharpe", 0), 3),
        "beats_bh": bool(s.get("sharpe", 0) > b.get("sharpe", 0)),
        "trades_per_month": round(flips / years / 12, 2) if years > 0 else np.nan,
        "in_market": round(float((w.abs() > 1e-9).mean()), 3),
        "years": round(years, 2),
    }


def ablation(symbol, tf, slow_d, fast_d, mode, direction) -> pd.DataFrame:
    """Does each filter earn its place, or is it decoration?"""
    rows = []
    for label, kw in [
        ("full spec", {}),
        ("no directional filter", {"use_directional": False}),
        ("no vol-regime filter", {"use_vol_regime": False}),
        ("no filters at all", {"use_directional": False, "use_vol_regime": False}),
        ("no vol targeting", {"vol_target_override": None}),
    ]:
        kw = dict(kw)
        vt = kw.pop("vol_target_override", VOL_TARGET)
        df = bb.load(symbol, tf)
        costs = load_symbol_costs(str(DATA / "costs.csv"), symbol)
        bpd = bb.bars_per_day(df)
        r = bb.run(df, costs, slow_bars=max(2, int(round(slow_d * bpd))),
                   fast_bars=max(1, int(round(fast_d * bpd))),
                   mode=mode, direction=direction, vol_target=vt, **kw)
        m = score(df, costs, r["returns"], r["weights"])
        rows.append({"variant": label, **{k: m[k] for k in
                     ("sharpe", "cagr", "max_dd", "excess_sharpe",
                      "trades_per_month", "in_market")}})
    return pd.DataFrame(rows)


def sanity(symbol, tf, slow_d, fast_d, mode, direction) -> dict:
    df, costs, r = build(symbol, tf, slow_d, fast_d, mode, direction)
    ppy = int(round(bb.periods_per_year(df)))
    ret = df["close"].pct_change().fillna(0.0)
    base = summarize(r["returns"], periods_per_year=ppy).get("sharpe", 0)
    out = {"baseline": round(base, 3)}
    for sh, name in [(-1, "look_ahead_1bar"), (1, "delayed_1bar"), (2, "delayed_2bar")]:
        w = r["weights"].shift(sh).fillna(0.0)
        out[name] = round(summarize(w * ret, periods_per_year=ppy).get("sharpe", 0), 3)
    rng = np.random.default_rng(42)
    w = r["weights"]
    sh_list = [summarize(pd.Series(rng.permutation(w.to_numpy()), index=w.index) * ret,
                         periods_per_year=ppy).get("sharpe", 0) for _ in range(200)]
    out["placebo_mean"] = round(float(np.mean(sh_list)), 3)
    out["placebo_p95"] = round(float(np.percentile(sh_list, 95)), 3)
    out["baseline_pctile_vs_placebo"] = round(float((np.array(sh_list) < base).mean()), 3)
    return out


def rolling_stability(symbol, tf, slow_d, fast_d, mode, direction,
                      window_years: float = 2.0) -> pd.DataFrame:
    """Non-overlapping fixed windows. No selection -- the SAME parameters
    everywhere, so this measures the strategy's consistency, not an
    optimiser's luck."""
    df, costs, r = build(symbol, tf, slow_d, fast_d, mode, direction)
    net, w = r["returns"], r["weights"]
    rows, start = [], net.index.min()
    while True:
        stop = start + pd.DateOffset(days=int(window_years * 365.25))
        if stop > net.index.max():
            break
        m = score(df, costs, net, w, start, stop)
        if m:
            rows.append({"from": str(start)[:10], "to": str(stop)[:10], **m})
        start = stop
    return pd.DataFrame(rows)


def cost_sensitivity(symbol, tf, slow_d, fast_d, mode, direction) -> pd.DataFrame:
    """Brief 7.3: re-run at 1.5x and 2x the measured spread."""
    rows = []
    for mult in (1.0, 1.5, 2.0, 3.0):
        df, costs, r = build(symbol, tf, slow_d, fast_d, mode, direction,
                             spread_multiplier=mult)
        m = score(df, costs, r["returns"], r["weights"])
        rows.append({"spread_multiple": mult, "sharpe": m["sharpe"],
                     "cagr": m["cagr"], "max_dd": m["max_dd"],
                     "excess_sharpe": m["excess_sharpe"], "beats_bh": m["beats_bh"]})
    return pd.DataFrame(rows)


def deflated(symbol, tf, slow_d, fast_d, mode, direction) -> dict:
    """Deflate the chosen spec against the FULL grid that was searched.

    The trial count is the honest one: every configuration in
    run_book_b.build_configs(), which is the search space this candidate was
    drawn from. Under-reporting it would weaken the correction and defeat the
    metric's purpose.
    """
    df = bb.load(symbol, tf)
    costs = load_symbol_costs(str(DATA / "costs.csv"), symbol)
    configs = rb.build_configs()
    all_sr = []
    for c in configs:
        bpd = bb.bars_per_day(df)
        r = bb.run(df, costs,
                   slow_bars=max(2, int(round(c["slow_days"] * bpd))),
                   fast_bars=max(1, int(round(c["fast_days"] * bpd))),
                   mode=c["mode"], direction=c["direction"], vol_target=VOL_TARGET)
        all_sr.append(sharpe_per_period(r["returns"]))
    _, _, chosen = build(symbol, tf, slow_d, fast_d, mode, direction)
    return deflated_sharpe_ratio(chosen["returns"], all_sr)


def subperiods(symbol, tf, slow_d, fast_d, mode, direction) -> pd.DataFrame:
    df, costs, r = build(symbol, tf, slow_d, fast_d, mode, direction)
    rows = []
    for label, lo, hi in PERIODS[symbol]:
        m = score(df, costs, r["returns"], r["weights"], lo, hi)
        if m:
            rows.append({"period": label, **m})
    m = score(df, costs, r["returns"], r["weights"])
    rows.append({"period": "FULL", **m})
    return pd.DataFrame(rows)
