"""Follow-ups to the harness run: a cost-model correction, and the one
optimisation the harness permits.

TWO SEPARATE THINGS HAPPEN HERE.

1. A COST-MODEL CORRECTION, not a rescue attempt.
   Every cost in this project so far charges a CONSTANT spread in price units.
   For gold that is fine (0.15 on a price between 1,200 and 4,300). For bitcoin
   it is indefensible: today's 2.424 spread is 50% of BTC's 2011 price, 36% of
   2012's and 2.2% of 2013's. A crypto CFD spread scales with price; charging
   today's dollar spread at $5 BTC is not conservative, it is simply wrong, and
   it makes the pre-2017 holdout unreadable. The proportional model charges the
   same spread as a FRACTION of price. This was decided on the arithmetic above,
   before re-running anything.

2. THE EXIT MENU -- a pre-registered search of exactly five options.
   harness/registry.py exists so that "best of N" carries an N you can correct
   for. All five are reported, not just the winner, and the Bonferroni bar is
   the strictest the harness offers. If the best of five only looks good because
   it is the best of five, that will show as a gate failure rather than a
   headline.

Run: python src/harness_opt.py
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

import src.harness_test as ht  # noqa: E402
import src.universe as un  # noqa: E402
from common.data_fetch import save_parquet, load_parquet  # noqa: E402
from harness import report as hreport, gates as hgates  # noqa: E402
from harness.registry import EXITS  # noqa: E402

REPORTS = ht.REPORTS
PROPORTIONAL = ["BTCUSD", "ETHUSD"]      # priced in dollars that moved 10,000x


def rebuild_proportional() -> dict:
    """Rewrite crypto parquet with spread as a constant FRACTION of price."""
    spreads = ht._spread_map()
    out = {}
    for sym in PROPORTIONAL:
        src = ht.ho.DEEP_DIR / f"{un._safe(sym)}_H4.csv"
        if not src.exists():
            src = un.UNIVERSE_DIR / f"{un._safe(sym)}_H4.csv"
        if not src.exists() or sym not in spreads:
            continue
        df = pd.read_csv(src, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        last_px = float(df["close"].iloc[-1])
        frac = float(spreads[sym]) / last_px
        df["spread"] = df["close"].astype(float) * frac
        save_parquet(df, sym, "H4", root=ht.DATA_ROOT)
        out[sym] = {"fraction_of_price": frac,
                    "spread_2013": round(float(df.loc["2013", "spread"].median()), 4)
                    if "2013" in df.index.strftime("%Y") else None,
                    "spread_now": round(float(df["spread"].iloc[-1]), 4)}
    return out


def exit_menu(symbol: str, window, label: str) -> pd.DataFrame:
    """Every registered exit, on one window. All five reported."""
    d = load_parquet(symbol, "H4", root=ht.DATA_ROOT)
    strat = ht.make_strategy(symbol)
    rows = []
    for name in sorted(EXITS):
        s, _ = hgates.evaluate(strat, d, symbol, *window, name, None)
        rows.append({"symbol": symbol, "window": label, "exit": name,
                     "n": s["n"] if s else 0,
                     "expectancy_r": round(s["expectancy_r"], 4) if s else np.nan,
                     "profit_factor": round(s["profit_factor"], 3) if s else np.nan,
                     "win_rate": round(s["win_rate"], 1) if s else np.nan,
                     "sharpe": round(s["sharpe"], 3) if s else np.nan,
                     "max_dd_r": round(s["max_dd_r"], 1) if s else np.nan})
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 96)
    print("COST-MODEL CORRECTION: proportional spread for crypto")
    info = rebuild_proportional()
    for k, v in info.items():
        print(f"  {k}: spread = {v['fraction_of_price']*100:.5f}% of price "
              f"(now {v['spread_now']}, 2013 {v['spread_2013']})")
    print("=" * 96)

    # BTC re-run under the corrected cost model, same gates as before.
    ht._CACHE.pop("BTCUSD", None)
    btc = hreport.validate(ht.make_strategy("BTCUSD"), "BTCUSD", ht.SELECT,
                           unseen=ht.UNSEEN, exit_policy="E1_trail", session=None,
                           cross=None, n_hypotheses=5, data_root=ht.DATA_ROOT,
                           timeframe="H4", n_placebo=200)

    print("\n" + "=" * 96)
    print("EXIT MENU -- all five registered exits, selection AND unseen windows")
    print("=" * 96)
    frames = []
    for sym in ("XAUUSD", "BTCUSD"):
        frames.append(exit_menu(sym, ht.SELECT, "selection"))
        frames.append(exit_menu(sym, ht.UNSEEN, "unseen"))
    menu = pd.concat(frames, ignore_index=True)
    pd.set_option("display.width", 200)
    print(menu.to_string(index=False))
    menu.to_csv(REPORTS / "harness_exit_menu.csv", index=False)

    print("\nBest exit by SELECTION expectancy, and what it then did on UNSEEN:")
    for sym in ("XAUUSD", "BTCUSD"):
        sel = menu[(menu.symbol == sym) & (menu.window == "selection")]
        if sel["expectancy_r"].isna().all():
            continue
        best = sel.loc[sel["expectancy_r"].idxmax(), "exit"]
        un_row = menu[(menu.symbol == sym) & (menu.window == "unseen") &
                      (menu.exit == best)]
        sel_v = float(sel.loc[sel.exit == best, "expectancy_r"].iloc[0])
        un_v = float(un_row["expectancy_r"].iloc[0]) if len(un_row) else np.nan
        print(f"  {sym}: {best}  selection E[R] {sel_v:+.4f} -> unseen E[R] {un_v:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
