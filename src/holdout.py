"""Stage 2: validate screen survivors on history the screen never saw.

The cross-instrument screen (report_universe.py) selects instruments using only
the last six years. Everything before that window played no part in the
selection, which makes it a genuine holdout -- the one test that answers the
multiple-testing problem rather than just correcting for it. An instrument that
was picked because it happened to look good in 2020-2026 has no reason to also
look good in 2010-2020 unless the effect is real.

Same fixed specification, no refitting. The series is computed over the full
history so every indicator is warm at the holdout boundary, then only the
holdout span is scored.

READ-ONLY against MT5: copy_rates_range only.

Run: python src/holdout.py
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
import src.universe as un  # noqa: E402
import src.screen_universe as su  # noqa: E402
from common.portfolio import summarize  # noqa: E402

DATA = un.DATA
REPORTS = un.REPORTS
DEEP_DIR = DATA / "universe_deep"
HOLDOUT_START = "2010-01-01"


def deep_pull(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Full H4 history back to 2010 for the survivors only (slow per symbol,
    which is exactly why it is not done for the whole universe)."""
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    DEEP_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    try:
        lo = pd.Timestamp(HOLDOUT_START, tz="UTC").to_pydatetime()
        hi = pd.Timestamp.now(tz="UTC").to_pydatetime()
        for name in symbols:
            path = DEEP_DIR / f"{un._safe(name)}_H4.csv"
            if path.exists():
                df = pd.read_csv(path, parse_dates=["timestamp"]).set_index("timestamp")
            else:
                print(f"  deep pull {name}", flush=True)
                if not mt5.symbol_info(name).visible:
                    mt5.symbol_select(name, True)
                r = mt5.copy_rates_range(name, mt5.TIMEFRAME_H4, lo, hi)
                if r is None or len(r) == 0:
                    continue
                df = pd.DataFrame(r).rename(columns={"tick_volume": "volume"})
                df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
                df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
                df.to_csv(path, index_label="timestamp")
            out[name] = df.sort_index()[~df.index.duplicated(keep="last")]
    finally:
        mt5.shutdown()
    return out


def score_period(df: pd.DataFrame, costs: dict, lo, hi) -> dict | None:
    bpd = bb.bars_per_day(df)
    ppy = int(round(bb.periods_per_year(df)))
    r = bb.run(df, costs,
               slow_bars=max(2, int(round(su.SLOW_D * bpd))),
               fast_bars=max(1, int(round(su.FAST_D * bpd))),
               mode="blend5050", direction=su.DIRECTION,
               vol_target=su.VOL_TARGET, max_leverage=su.MAX_LEV)
    seg = r["returns"].loc[lo:hi]
    if len(seg) < 500:
        return None
    bench = su.cfd_buy_hold(df, costs, seg, seg.index)
    s = summarize(seg, periods_per_year=ppy)
    b = summarize(bench, periods_per_year=ppy)
    w = r["weights"].loc[seg.index]
    years = (seg.index[-1] - seg.index[0]).days / 365.25
    return {
        "from": str(seg.index[0])[:10], "to": str(seg.index[-1])[:10],
        "years": round(years, 2),
        "sharpe": round(s.get("sharpe", 0), 3), "cagr": round(s.get("cagr", 0), 4),
        "max_dd": round(s.get("max_drawdown", 0), 3),
        "bench_sharpe": round(b.get("sharpe", 0), 3),
        "excess_sharpe": round(s.get("sharpe", 0) - b.get("sharpe", 0), 3),
        "trades_per_week": round(float((np.sign(w).diff().fillna(0) != 0).sum())
                                 / years / 52, 2),
        "_returns": seg,
    }


def main() -> int:
    screen = pd.read_csv(REPORTS / "universe_screen.csv")
    costs = pd.read_csv(DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}
    sel = su.select(screen)
    survivors = sel[sel.passes]["symbol"].tolist()
    print(f"survivors from screen: {survivors}", flush=True)
    if not survivors:
        print("nothing to validate")
        return 0

    screen_start = pd.read_csv(DATA / "universe_meta.csv").set_index("symbol")["start"]
    deep = deep_pull(survivors)

    rows, series = [], {}
    for sym in survivors:
        if sym not in deep or sym not in cmap:
            continue
        cut = pd.Timestamp(screen_start[sym], tz="UTC")
        ho = score_period(deep[sym], cmap[sym], None, cut - pd.Timedelta(hours=4))
        if ho is None:
            rows.append({"symbol": sym, "holdout": "insufficient pre-screen history"})
            continue
        series[sym] = ho.pop("_returns")
        ho["passes_holdout"] = bool(ho["excess_sharpe"] > 0 and ho["sharpe"] > 0)
        rows.append({"symbol": sym, **ho})
        print(f"  {sym:<14} holdout {ho['from']}..{ho['to']} sharpe {ho['sharpe']:+.2f} "
              f"excess {ho['excess_sharpe']:+.2f} -> "
              f"{'PASS' if ho['passes_holdout'] else 'FAIL'}", flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(REPORTS / "holdout_validation.csv", index=False)
    print("\n" + res.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
