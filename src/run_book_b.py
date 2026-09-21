"""Book B -- walk-forward evaluation, overfitting controls, and the honest
benchmark. Build step 3 of the brief.

The whole design of this script is defensive, because the brief's section 7 is
where this project either stays honest or stops being worth anything:

  * Nothing is selected on data it is then scored on. Parameters are chosen
    inside each in-sample window and evaluated only on the out-of-sample window
    that follows; the headline return series is the stitched OOS path.
  * Parameters are chosen from a PLATEAU, not a peak -- the selection criterion
    is the mean Sharpe of a setting's immediate neighbourhood, so a lone spike
    surrounded by failures can never win.
  * EVERY combination evaluated is counted and fed to the deflated Sharpe
    ratio. The count is an input to that metric, so under-reporting it would
    defeat the point.
  * The benchmark is vol-scaled buy-and-hold of the same instrument at the same
    cost, not zero. Per Kim/Tse/Wald (2016) and Huang et al. (2020) this is the
    honest hurdle, and on gold especially it is the only thing that separates
    the signal from fifteen years of drift.

A config is computed ONCE over the full history and then sliced per window.
That is legitimate precisely because `book_b.run` does no fitting -- every
parameter is supplied and every transform is causal -- so a slice is exactly
what a live system running that config would have produced over those dates.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
from common.financing import load_symbol_costs  # noqa: E402
from common.portfolio import summarize, vol_matched_benchmark, block_bootstrap_ci  # noqa: E402
from common.validation import (  # noqa: E402
    deflated_sharpe_ratio, sharpe_per_period, plateau_score,
)

DATA = REPO / "data"
REPORTS = REPO / "reports"

# --- the search grid -------------------------------------------------------
# Lookbacks in TRADING DAYS, converted to bars per instrument. The brief's
# primary medium speed is slow 60 / fast 10; the range brackets it widely
# enough that a plateau can be seen rather than assumed, and includes the
# published slow specification (250d / 21d) as a member rather than a
# special case.
SLOW_DAYS = [30, 60, 90, 120, 180, 250]
FAST_DAYS = [5, 10, 15, 21, 30, 40]
MODES = ["blend5050", "slow_only", "fast_only", "dma"]
DIRECTIONS = ["both", "long_only"]

VOL_TARGET = 0.15
MAX_LEVERAGE = 3.0


def build_configs() -> list[dict]:
    cfgs = []
    for slow, fast, mode, direction in itertools.product(
            SLOW_DAYS, FAST_DAYS, MODES, DIRECTIONS):
        if fast >= slow:
            continue
        # slow_only ignores the fast lookback, so every fast value would be a
        # duplicate run. Counting duplicates would inflate the trial count and
        # understate the deflated Sharpe's correction -- keep one.
        if mode == "slow_only" and fast != FAST_DAYS[0]:
            continue
        cfgs.append({"slow_days": slow, "fast_days": fast,
                     "mode": mode, "direction": direction})
    return cfgs


def evaluate_all(df: pd.DataFrame, costs: dict, configs: list[dict],
                 spread_multiplier: float = 1.0) -> dict:
    """Full-history net returns for every configuration."""
    bpd = bb.bars_per_day(df)
    out = {}
    for i, c in enumerate(configs):
        slow_bars = max(2, int(round(c["slow_days"] * bpd)))
        fast_bars = max(1, int(round(c["fast_days"] * bpd)))
        r = bb.run(df, costs, slow_bars=slow_bars, fast_bars=fast_bars,
                   mode=c["mode"], direction=c["direction"],
                   vol_target=VOL_TARGET, max_leverage=MAX_LEVERAGE,
                   spread_multiplier=spread_multiplier)
        out[i] = {"returns": r["returns"], "weights": r["weights"],
                  "buy_hold": r["buy_hold"], "cost": r["cost"],
                  "financing": r["financing"], "gross": r["gross"]}
    return out


def walk_forward(df: pd.DataFrame, results: dict, configs: list[dict],
                 is_years: float, oos_years: float) -> dict:
    """Rolling IS/OOS. Returns the stitched OOS path and the per-window record."""
    start, end = df.index.min(), df.index.max()
    windows = []
    is_start = start
    while True:
        is_end = is_start + pd.DateOffset(days=int(is_years * 365.25))
        oos_end = is_end + pd.DateOffset(days=int(oos_years * 365.25))
        if oos_end > end:
            break
        windows.append((is_start, is_end, oos_end))
        is_start = is_start + pd.DateOffset(days=int(oos_years * 365.25))

    rows, oos_parts = [], []
    for is_start, is_end, oos_end in windows:
        is_sharpes = []
        for i, c in enumerate(configs):
            seg = results[i]["returns"].loc[is_start:is_end]
            is_sharpes.append(sharpe_per_period(seg) if len(seg) > 30 else np.nan)

        grid = pd.DataFrame(configs)
        grid["is_sharpe"] = is_sharpes
        # Plateau selection, done separately within each (mode, direction)
        # family so that neighbourhood means are taken over the lookback
        # surface and not across structurally different strategies.
        scored = []
        for (mode, direction), sub in grid.groupby(["mode", "direction"]):
            if sub["is_sharpe"].notna().sum() == 0:
                continue
            s = plateau_score(sub.reset_index(), ["slow_days", "fast_days"], "is_sharpe")
            scored.append(s)
        scored = pd.concat(scored, ignore_index=True)
        scored = scored[np.isfinite(scored["neighbourhood_mean"])]
        if scored.empty:
            continue
        best = scored.loc[scored["neighbourhood_mean"].idxmax()]
        bi = int(best["index"])

        oos = results[bi]["returns"].loc[is_end:oos_end]
        oos_parts.append(oos)
        rows.append({
            "is_start": str(is_start)[:10], "is_end": str(is_end)[:10],
            "oos_end": str(oos_end)[:10],
            "slow_days": int(best["slow_days"]), "fast_days": int(best["fast_days"]),
            "mode": best["mode"], "direction": best["direction"],
            "is_sharpe_per_period": round(float(best["is_sharpe"]), 5),
            "is_neighbourhood_mean": round(float(best["neighbourhood_mean"]), 5),
            "peakiness": round(float(best["peakiness"]), 5),
            "oos_sharpe_per_period": round(sharpe_per_period(oos), 5),
            "oos_return": round(float((1 + oos).prod() - 1), 5),
            "oos_bars": len(oos),
        })

    stitched = pd.concat(oos_parts).sort_index() if oos_parts else pd.Series(dtype=float)
    stitched = stitched[~stitched.index.duplicated(keep="first")]
    return {"windows": pd.DataFrame(rows), "oos_returns": stitched}


def cfd_buy_hold(df: pd.DataFrame, costs: dict, target_vol_of: pd.Series,
                 index: pd.DatetimeIndex) -> pd.Series:
    """Buy-and-hold of the CFD, vol-matched to the strategy and charged the
    costs a real holder pays.

    The plain `vol_matched_benchmark` in common/portfolio.py scales raw price
    returns and charges nothing. For a cash equity that is roughly fair. For a
    CFD it is not: holding gold long here pays -3.78%/yr in swap EVERY night,
    on the full notional, forever. Leaving that out hands the benchmark a free
    3.78% a year and makes the hurdle look higher than it is.

    Charging it cuts both ways and that is the point -- the question the brief
    asks is whether the signal beats *actually buying and holding this
    instrument at this broker*, not an idealised index. The strategy's
    advantage, if it has one, is precisely that it is flat much of the time and
    so pays this charge much less often.
    """
    from common.financing import financing_return

    ret = df["close"].astype(float).pct_change().fillna(0.0).loc[index]
    sv = target_vol_of.std(ddof=1)
    bv = ret.std(ddof=1)
    k = float(sv / bv) if bv > 0 else 0.0

    w = pd.Series(k, index=index)
    fin = financing_return(w, index, costs["swap_long_annual"],
                           costs["swap_short_annual"], costs["triple_weekday"])
    # One entry crossing at the start; a holder pays the spread once, not per bar.
    entry = pd.Series(0.0, index=index)
    if len(index):
        px = float(df["close"].loc[index[0]])
        entry.iloc[0] = k * (costs["typical_spread_price"] / 2.0) / px
    return k * ret + fin - entry


def run_symbol(symbol: str, timeframe: str, is_years: float, oos_years: float) -> dict:
    df = bb.load(symbol, timeframe)
    costs = load_symbol_costs(str(DATA / "costs.csv"), symbol)
    ppy = int(round(bb.periods_per_year(df)))
    configs = build_configs()

    print(f"\n=== {symbol} {timeframe} | {len(df):,} bars | "
          f"{len(configs)} configurations ===", flush=True)

    results = evaluate_all(df, costs, configs)
    wf = walk_forward(df, results, configs, is_years, oos_years)
    oos = wf["oos_returns"]
    if oos.empty:
        print("  not enough history for a walk-forward at these window sizes")
        return {"symbol": symbol, "timeframe": timeframe, "insufficient": True}

    # The honest hurdle: same dates, same instrument, vol-matched, and charged
    # the swap a real CFD holder pays every night.
    bench = cfd_buy_hold(df, costs, oos, oos.index)
    # Also keep the uncosted version, to show how much of the hurdle is the
    # instrument's drift and how much is the financing being waived.
    bench_free = vol_matched_benchmark(results[0]["buy_hold"].loc[oos.index], oos)

    strat = summarize(oos, periods_per_year=ppy)
    bench_s = summarize(bench, periods_per_year=ppy)
    bench_free_s = summarize(bench_free, periods_per_year=ppy)

    # The decisive overfitting diagnostic: does in-sample selection predict
    # out-of-sample results at all? If this correlation is ~0, the optimiser
    # cannot tell in advance which parameters will work, and a bigger grid
    # would not help.
    wdf = wf["windows"]
    if len(wdf) > 2:
        is_oos_corr = float(np.corrcoef(wdf["is_sharpe_per_period"],
                                        wdf["oos_sharpe_per_period"])[0, 1])
    else:
        is_oos_corr = float("nan")

    # Deflated Sharpe. The trial variance comes from the full-sample Sharpe of
    # every configuration searched -- that spread is what says how much of the
    # winner's score is selection rather than signal.
    all_sr = [sharpe_per_period(results[i]["returns"]) for i in range(len(configs))]
    dsr = deflated_sharpe_ratio(oos, all_sr)

    lo, hi = block_bootstrap_ci(
        oos, lambda s: np.sqrt(ppy) * s.mean() / s.std(ddof=1) if s.std(ddof=1) > 0 else 0.0,
        block_size=max(20, ppy // 4), n_boot=500)

    # Trade frequency, measured on the config chosen most often across windows.
    wmode = wf["windows"].mode(numeric_only=False).iloc[0]
    years = (oos.index[-1] - oos.index[0]).days / 365.25
    chosen_idx = next(i for i, c in enumerate(configs)
                      if c["slow_days"] == int(wmode["slow_days"])
                      and c["fast_days"] == int(wmode["fast_days"])
                      and c["mode"] == wmode["mode"]
                      and c["direction"] == wmode["direction"])
    w = results[chosen_idx]["weights"].loc[oos.index]
    flips = int((np.sign(w).diff().fillna(0) != 0).sum())

    return {
        "symbol": symbol, "timeframe": timeframe, "insufficient": False,
        "n_bars": len(df), "periods_per_year": ppy,
        "n_configs": len(configs),
        "oos_start": str(oos.index.min())[:10], "oos_end": str(oos.index.max())[:10],
        "oos_years": round(years, 2),
        "strategy": strat, "benchmark": bench_s, "benchmark_uncosted": bench_free_s,
        "beats_benchmark": bool(strat.get("sharpe", 0) > bench_s.get("sharpe", 0)),
        "is_oos_correlation": round(is_oos_corr, 4) if np.isfinite(is_oos_corr) else None,
        "sharpe_ci95": (round(lo, 3), round(hi, 3)),
        "dsr": dsr,
        "windows": wf["windows"],
        "modal_config": {k: (int(wmode[k]) if k.endswith("_days") else wmode[k])
                         for k in ("slow_days", "fast_days", "mode", "direction")},
        "direction_changes_per_year": round(flips / years, 1) if years > 0 else np.nan,
        "trades_per_month": round(flips / years / 12, 2) if years > 0 else np.nan,
        "cost_drag_total": round(float(results[chosen_idx]["cost"].loc[oos.index].sum()), 4),
        "financing_drag_total": round(float(results[chosen_idx]["financing"].loc[oos.index].sum()), 4),
        "_results": results, "_configs": configs, "_df": df, "_costs": costs,
        "_chosen_idx": chosen_idx,
    }


def cost_sensitivity(res: dict) -> pd.DataFrame:
    """Re-run the chosen configuration at 1.5x and 2x spread (brief 7.3)."""
    rows = []
    cfg = res["_configs"][res["_chosen_idx"]]
    df, costs = res["_df"], res["_costs"]
    bpd = bb.bars_per_day(df)
    oos_idx = res["_results"][res["_chosen_idx"]]["returns"].loc[
        res["oos_start"]:res["oos_end"]].index
    for mult in (1.0, 1.5, 2.0):
        r = bb.run(df, costs,
                   slow_bars=max(2, int(round(cfg["slow_days"] * bpd))),
                   fast_bars=max(1, int(round(cfg["fast_days"] * bpd))),
                   mode=cfg["mode"], direction=cfg["direction"],
                   vol_target=VOL_TARGET, max_leverage=MAX_LEVERAGE,
                   spread_multiplier=mult)
        seg = r["returns"].loc[oos_idx]
        s = summarize(seg, periods_per_year=res["periods_per_year"])
        rows.append({"spread_multiple": mult, "sharpe": round(s.get("sharpe", 0), 4),
                     "cagr": round(s.get("cagr", 0), 4),
                     "max_drawdown": round(s.get("max_drawdown", 0), 4)})
    return pd.DataFrame(rows)


def overlay_variants(res: dict) -> pd.DataFrame:
    """Vol targeting on/off and at different targets, on the chosen config."""
    rows = []
    cfg = res["_configs"][res["_chosen_idx"]]
    df, costs = res["_df"], res["_costs"]
    bpd = bb.bars_per_day(df)
    oos_idx = res["_results"][res["_chosen_idx"]]["returns"].loc[
        res["oos_start"]:res["oos_end"]].index
    for label, vt, band in [("none", None, 0.0), ("target 10%", 0.10, 0.0),
                            ("target 15%", 0.15, 0.0), ("target 20%", 0.20, 0.0),
                            ("target 15% + 0.1 band", 0.15, 0.1),
                            ("target 15% + 0.25 band", 0.15, 0.25)]:
        r = bb.run(df, costs,
                   slow_bars=max(2, int(round(cfg["slow_days"] * bpd))),
                   fast_bars=max(1, int(round(cfg["fast_days"] * bpd))),
                   mode=cfg["mode"], direction=cfg["direction"],
                   vol_target=vt, max_leverage=MAX_LEVERAGE, rebalance_band=band)
        seg = r["returns"].loc[oos_idx]
        w = r["weights"].loc[oos_idx]
        years = (oos_idx[-1] - oos_idx[0]).days / 365.25
        s = summarize(seg, periods_per_year=res["periods_per_year"])
        rows.append({
            "overlay": label,
            "sharpe": round(s.get("sharpe", 0), 4),
            "cagr": round(s.get("cagr", 0), 4),
            "vol": round(s.get("vol", 0), 4),
            "max_drawdown": round(s.get("max_drawdown", 0), 4),
            "turnover_per_year": round(float(w.diff().abs().sum() / years), 1),
            "trades_per_month": round(float((np.sign(w).diff().fillna(0) != 0).sum()
                                            / years / 12), 2),
        })
    return pd.DataFrame(rows)
