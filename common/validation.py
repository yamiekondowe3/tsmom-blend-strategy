"""Overfitting controls: probabilistic and deflated Sharpe ratios.

Bailey & Lopez de Prado, *The Deflated Sharpe Ratio* (SSRN 2460551), which the
brief's section 9 says to read BEFORE building rather than after a backtest
looks brilliant.

The problem it solves: if you try N parameter combinations and keep the best,
the winner's Sharpe is biased upward even when every combination is worthless.
The expected maximum Sharpe from N independent worthless strategies grows like
sqrt(2*ln(N)). Try 100 of them on noise and the best will show a Sharpe near
0.3-0.4 per period purely by selection. Quoting that number as if it were the
result of a single test is the single most common way a backtest lies.

The deflated Sharpe corrects for exactly that, and for the fact that returns
are neither normal nor serially independent. It needs the TRIAL COUNT as an
input, so the count has to be honest -- every combination evaluated, not just
the ones written up. That is the whole point of the metric and the reason the
grid sizes in this project are recorded in the reports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

EULER_MASCHERONI = 0.5772156649015329


def sharpe_per_period(returns: pd.Series) -> float:
    """Non-annualised Sharpe. PSR and DSR are defined on the per-period figure;
    feeding them an annualised one silently inflates both."""
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def probabilistic_sharpe_ratio(returns: pd.Series, benchmark_sr: float = 0.0) -> float:
    """P(true Sharpe > benchmark_sr), accounting for skew and kurtosis.

    Negative skew and fat tails -- both normal in trend-following returns --
    make a given Sharpe less trustworthy, and this is where that enters.
    """
    r = pd.Series(returns).dropna()
    n = len(r)
    if n < 3:
        return float("nan")
    sr = sharpe_per_period(r)
    g3 = float(stats.skew(r, bias=False))
    g4 = float(stats.kurtosis(r, fisher=False, bias=False))
    denom = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr ** 2
    if denom <= 0:
        return float("nan")
    z = (sr - benchmark_sr) * np.sqrt(n - 1) / np.sqrt(denom)
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum per-period Sharpe across `n_trials` worthless strategies.

    This is the bar a selected strategy has to clear just to be distinguishable
    from the best of N coin flips.
    """
    if n_trials < 2 or sr_variance <= 0:
        return 0.0
    g = EULER_MASCHERONI
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(sr_variance) * ((1.0 - g) * z1 + g * z2))


def deflated_sharpe_ratio(returns: pd.Series, all_trial_sharpes, ) -> dict:
    """The headline control.

    `all_trial_sharpes` must be the per-period Sharpe of EVERY combination
    tested, not a shortlist. Their variance is what tells the metric how much
    of the winner's performance is selection.

    Returns the deflated probability plus the inputs, so a reader can check
    the trial count against what was actually run.
    """
    sr_list = np.asarray([s for s in all_trial_sharpes if np.isfinite(s)], dtype=float)
    n_trials = len(sr_list)
    sr_var = float(np.var(sr_list, ddof=1)) if n_trials > 1 else 0.0
    sr0 = expected_max_sharpe(n_trials, sr_var)
    dsr = probabilistic_sharpe_ratio(returns, benchmark_sr=sr0)
    return {
        "n_trials": n_trials,
        "sharpe_variance_across_trials": sr_var,
        "expected_max_sharpe_under_null": sr0,
        "observed_sharpe_per_period": sharpe_per_period(returns),
        "deflated_sharpe_ratio": dsr,
        "psr_vs_zero": probabilistic_sharpe_ratio(returns, 0.0),
        # The conventional reading: below 0.95 the result is not distinguishable
        # from the best of N lucky draws at a 5% level.
        "passes_at_95pct": bool(np.isfinite(dsr) and dsr > 0.95),
    }


def plateau_score(grid: pd.DataFrame, param_cols: list[str], metric_col: str) -> pd.DataFrame:
    """Rank parameter settings by their NEIGHBOURHOOD, not their own value.

    The brief says to pick from a plateau, never a peak. A peak that towers
    over its immediate neighbours is a fluke of the sample: change the
    parameter slightly, as live conditions effectively will, and performance
    collapses. A broad plateau means nearby settings work too, which is what a
    real effect looks like.

    For each row, this averages `metric_col` over all rows within one grid step
    of it on every parameter axis. A setting is worth trusting when its own
    score and its neighbourhood score are both high.
    """
    g = grid.copy().reset_index(drop=True)
    levels = {c: np.sort(g[c].unique()) for c in param_cols}
    rank = {c: {v: i for i, v in enumerate(levels[c])} for c in param_cols}
    idx = {c: g[c].map(rank[c]).to_numpy() for c in param_cols}

    neigh_mean, neigh_min, neigh_n = [], [], []
    vals = g[metric_col].to_numpy(dtype=float)
    for i in range(len(g)):
        mask = np.ones(len(g), dtype=bool)
        for c in param_cols:
            mask &= np.abs(idx[c] - idx[c][i]) <= 1
        block = vals[mask]
        block = block[np.isfinite(block)]
        neigh_mean.append(block.mean() if len(block) else np.nan)
        neigh_min.append(block.min() if len(block) else np.nan)
        neigh_n.append(len(block))
    g["neighbourhood_mean"] = neigh_mean
    g["neighbourhood_min"] = neigh_min
    g["neighbourhood_n"] = neigh_n
    # A peak stands far above its neighbours; a plateau sits level with them.
    g["peakiness"] = g[metric_col] - g["neighbourhood_mean"]
    return g
