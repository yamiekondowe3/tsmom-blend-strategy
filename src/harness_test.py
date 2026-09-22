"""Run Book B through the independent validation harness in ../harness.

WHY THIS IS A REAL TEST AND NOT A VICTORY LAP. The harness is a different
engine with a different philosophy: discrete trades, one position at a time,
ATR-based stops from a fixed pre-registered menu, results in R-multiples. Book B
is a continuous, vol-sized exposure with no stops at all. Putting the signal
through it therefore asks a question our own backtest cannot:

    does the ENTRY TIMING carry information, independently of the
    continuous vol-sizing that has been doing so much of the work?

The harness's gates are the ones that matter here -- especially G2, the
random-entry placebo with the same trade count, direction mix, session, exits
and costs. If Book B's entries are no better than random entries managed by the
same stops, the signal is not what is producing the result.

Two honest notes about the fit:

  * The harness re-enters as soon as an exit fires while the signal is still
    long, so what is being tested is "Book B entries, stop-managed" -- a
    variant, not the deployed strategy. Stated plainly rather than glossed.
  * `CostModel.for_symbol` refuses to guess a spread and derives it from the
    data's own `spread` column. The broker's recorded column is unusable
    historically (XAUUSD reports exactly 0.000 through much of 2019-2023), so
    the parquet written here carries the TICK-MEASURED median from
    data/universe_costs.csv as a constant. That is the same number the rest of
    this project costs with, and the substitution is declared in the report
    rather than hidden -- which is what that module asks callers to do.

Run: python src/harness_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
WORKSPACE = REPO.parent
for p in (str(REPO), str(WORKSPACE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import src.holdout as ho  # noqa: E402
import src.universe as un  # noqa: E402
from src.parity import SPEC, VOL_TARGET, MAX_LEV, REGIME_DECILE  # noqa: E402

from common.data_fetch import save_parquet, load_parquet  # noqa: E402
from harness.strategies import wilder_atr  # noqa: E402
from harness import report as hreport  # noqa: E402
from harness import gates as hgates  # noqa: E402
from harness.costs import CostModel  # noqa: E402

DATA_ROOT = REPO / "data" / "harness_cache"
REPORTS = REPO / "reports"

SELECT = ("2020-09-22", "2026-08-31")     # the cross-instrument screen window
UNSEEN = ("2011-01-03", "2020-09-21")     # pre-screen holdout

# Cross-section: the identical rules on markets Book B was NOT built on. Chosen
# for liquidity and for spanning different risk factors, before seeing results.
CROSS = ["XAGUSD", "XPTUSD", "EURUSD", "USDJPY", "GBPUSD", "USDCHF", "ETHUSD"]


def _spread_map() -> dict:
    c = pd.read_csv(un.DATA / "universe_costs.csv").set_index("symbol")
    return c["typical_spread_price"].to_dict()


def build_cache() -> dict:
    """Write parquet the harness can load, carrying measured spreads."""
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    spreads = _spread_map()
    written = {}
    for sym in list(SPEC) + CROSS:
        deep = ho.DEEP_DIR / f"{un._safe(sym)}_H4.csv"
        shallow = un.UNIVERSE_DIR / f"{un._safe(sym)}_H4.csv"
        src = deep if deep.exists() else shallow
        if not src.exists() or sym not in spreads:
            continue
        df = pd.read_csv(src, parse_dates=["timestamp"]).set_index("timestamp")
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        df["spread"] = float(spreads[sym])
        save_parquet(df, sym, "H4", root=DATA_ROOT)
        written[sym] = (str(df.index.min())[:10], str(df.index.max())[:10], len(df))
    return written


def book_b_side(symbol: str) -> pd.Series:
    """Book B's long-only target weight over the FULL history, as +1/0 entries.

    Computed on the whole series and then sliced, rather than recomputed on each
    window the harness passes in. That is deliberate: the harness warms up 400
    days, while the regime filter needs a two-year trailing lookback, and the
    parity test already showed that starting it cold changes its threshold by up
    to 57%. Slicing a causal series is not look-ahead; recomputing it on a short
    slice would simply be a different, colder filter.
    """
    s = SPEC[symbol]
    df = load_parquet(symbol, "H4", root=DATA_ROOT)
    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0.0)

    slow_sig = np.sign(close / close.shift(s["slow"]) - 1.0).fillna(0.0)
    fast_sig = np.sign(close / close.shift(s["fast"]) - 1.0).fillna(0.0)
    pos = 0.5 * slow_sig + 0.5 * fast_sig
    pos.iloc[: max(s["slow"], s["fast"])] = 0.0

    ma = close.rolling(s["slow"]).mean()
    allow = np.sign(close - ma).fillna(0.0)
    pos = pd.Series(np.where(np.sign(pos) == allow, pos, 0.0), index=pos.index)

    rv = ret.rolling(s["volwin"]).std(ddof=1)
    thr = rv.rolling(s["regimelb"], min_periods=s["volwin"] * 3).quantile(REGIME_DECILE)
    pos = pos.where(~(rv > thr).fillna(False), 0.0)

    w = pos.clip(lower=0.0).shift(1).fillna(0.0)     # one-bar lag, as deployed
    return (w > 0).astype(int)


_CACHE: dict[str, pd.Series] = {}


def make_strategy(symbol: str):
    """Return a harness-contract strategy: signals(df, **params) -> side/atr."""
    if symbol not in _CACHE:
        _CACHE[symbol] = book_b_side(symbol)
    side_full = _CACHE[symbol]

    def book_b(df, atr_period: int = 14):
        side = side_full.reindex(df.index).fillna(0).astype(int)
        return pd.DataFrame({"side": side, "atr": wilder_atr(df, atr_period)},
                            index=df.index)

    book_b.__name__ = f"book_b_{symbol}"
    return book_b


def cross_section_h4(symbol_list, exit_policy, a, b) -> pd.DataFrame:
    """G3 at H4.

    harness.gates.cross_section hardcodes the H1 timeframe, so it is called
    through the same `evaluate` it uses internally rather than by relabelling H4
    data as H1 -- which would have quietly mis-stated the timeframe in every
    downstream number.
    """
    rows = []
    for sym in symbol_list:
        if sym not in SPEC:
            SPEC[sym] = SPEC["XAUUSD"]      # same lookbacks, not re-tuned
        try:
            d = load_parquet(sym, "H4", root=DATA_ROOT)
            strat = make_strategy(sym)
            s, _ = hgates.evaluate(strat, d, sym, a, b, exit_policy, None)
        except Exception as e:
            rows.append({"symbol": sym, "error": str(e)[:60]})
            continue
        if s:
            rows.append({"symbol": sym, "n": s["n"],
                         "expectancy_r": round(s["expectancy_r"], 4),
                         "profit_factor": round(s["profit_factor"], 3),
                         "win_rate": round(s["win_rate"], 1),
                         "sharpe": round(s["sharpe"], 3)})
    return pd.DataFrame(rows)


def main() -> int:
    written = build_cache()
    print("harness cache written:")
    for k, v in written.items():
        print(f"  {k:<8} {v[0]}..{v[1]}  {v[2]:,} bars")

    results = {}
    for sym in ("XAUUSD", "BTCUSD"):
        strat = make_strategy(sym)
        # n_hypotheses=5 -> the strictest Bonferroni z the harness offers (2.58).
        # This project has tested far more than five configurations, so the
        # strictest available bar is the only defensible one.
        results[sym] = hreport.validate(
            strat, sym, SELECT, unseen=UNSEEN, exit_policy="E1_trail",
            session=None, cross=None, n_hypotheses=5,
            data_root=DATA_ROOT, timeframe="H4", n_placebo=200)

    print("\n" + "=" * 96)
    print("G3  CROSS-SECTION at H4 (markets Book B was not built on, own costs)")
    cs = cross_section_h4(CROSS, "E1_trail", *SELECT)
    print(cs.to_string(index=False))
    if "expectancy_r" in cs:
        good = cs["expectancy_r"].dropna()
        print(f"  positive {int((good > 0).sum())}/{len(good)}  "
              f"median E[R] {good.median():+.4f}")
    cs.to_csv(REPORTS / "harness_cross_section.csv", index=False)
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
