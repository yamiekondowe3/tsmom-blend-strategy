"""Book B as a two-instrument portfolio: the instruments that survived the cross-instrument
screen AND the pre-2020 holdout, combined, against gold alone.

Survivors: XAUUSD and BTCUSD. ETHUSD failed the holdout; XAUEUR had only nine
months of pre-screen history and is gold priced in another currency, so it adds
no independent evidence and would double the gold exposure.

Same fixed specification on every sleeve. Sleeves are combined equal-weight;
each is already vol-targeted to 15%, so equal weight is roughly equal risk.

Run: python src/portfolio_gold_btc.py
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
import src.holdout as ho  # noqa: E402
import src.portfolio_b as pbk  # noqa: E402  (section 6 kill switch)
import src.screen_universe as su  # noqa: E402
from common.portfolio import summarize  # noqa: E402
from common.validation import deflated_sharpe_ratio, sharpe_per_period  # noqa: E402

DATA = ho.DATA
REPORTS = ho.REPORTS
SLEEVES = ["XAUUSD", "BTCUSD"]
HOLDOUT_END = "2020-09-21"
PRIOR_TRIALS = 246          # spec grid + enhancement round, from reports/enhancements.md


def sleeve(sym: str, costs: dict, spread_mult: float = 1.0, fin_mult: float = 1.0):
    df = pd.read_csv(ho.DEEP_DIR / f"{sym}_H4.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    c = dict(costs)
    c["typical_spread_price"] *= spread_mult
    for k in ("swap_long_annual", "swap_short_annual"):
        if c[k] < 0:
            c[k] *= fin_mult
    bpd = bb.bars_per_day(df)
    r = bb.run(df, c, slow_bars=max(2, int(round(su.SLOW_D * bpd))),
               fast_bars=max(1, int(round(su.FAST_D * bpd))),
               mode="blend5050", direction=su.DIRECTION,
               vol_target=su.VOL_TARGET, max_leverage=su.MAX_LEV)
    return r["returns"], r["weights"]


def combine(rets: dict[str, pd.Series]) -> pd.Series:
    """Equal-weight on a common H4 clock. Gold does not trade at weekends and BTC
    does; a missing bar is a flat bar for that sleeve (no position, no P&L), not
    a gap to be dropped from the whole book."""
    m = pd.DataFrame(rets).fillna(0.0)
    return m.mean(axis=1)


def trades_per_week(weights: dict[str, pd.Series], idx) -> float:
    years = (idx[-1] - idx[0]).days / 365.25
    # Carry each position FORWARD over bars where its market is shut. Gold has no
    # weekend bars and BTC does; filling gold's weight with zero there booked a
    # fake exit every Saturday and a fake re-entry every Monday, and inflated
    # the count from ~1.7 to 3.9 trades a week.
    n = sum(float((np.sign(w.reindex(idx, method="ffill").fillna(0)).diff().fillna(0) != 0)
                  .sum())
            for w in weights.values())
    return n / years / 52


def main() -> int:
    costs = pd.read_csv(DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}

    rets, wts = {}, {}
    for s in SLEEVES:
        rets[s], wts[s] = sleeve(s, cmap[s])
    common_start = max(r.index.min() for r in rets.values())
    rets = {k: v.loc[common_start:] for k, v in rets.items()}
    port = combine(rets)
    ppy = int(round(len(port) / ((port.index[-1] - port.index[0]).days / 365.25)))

    periods = [("holdout (pre-screen)", None, HOLDOUT_END),
               ("screen window", "2020-09-22", None),
               ("full", None, None)]
    rows = []
    for label, lo, hi in periods:
        p = port.loc[lo:hi]
        g = rets["XAUUSD"].reindex(port.index).fillna(0).loc[lo:hi]
        ps, gs = summarize(p, periods_per_year=ppy), summarize(g, periods_per_year=ppy)
        rows.append({
            "period": label, "from": str(p.index[0])[:10], "to": str(p.index[-1])[:10],
            "portfolio_sharpe": round(ps["sharpe"], 3), "portfolio_cagr": round(ps["cagr"], 4),
            "portfolio_max_dd": round(ps["max_drawdown"], 3),
            "gold_only_sharpe": round(gs["sharpe"], 3), "gold_only_cagr": round(gs["cagr"], 4),
            "gold_only_max_dd": round(gs["max_drawdown"], 3),
            "trades_per_week": round(trades_per_week(wts, p.index), 2),
        })
    tab = pd.DataFrame(rows)

    # rolling 2-year windows, portfolio vs gold alone
    roll, start = [], port.index.min()
    while True:
        stop = start + pd.DateOffset(days=int(2 * 365.25))
        if stop > port.index.max():
            break
        p = port.loc[start:stop]
        g = rets["XAUUSD"].reindex(port.index).fillna(0).loc[start:stop]
        b = rets["BTCUSD"].reindex(port.index).fillna(0).loc[start:stop]
        roll.append({"from": str(start)[:10], "to": str(stop)[:10],
                     "portfolio": round(summarize(p, periods_per_year=ppy)["sharpe"], 3),
                     "gold": round(summarize(g, periods_per_year=ppy)["sharpe"], 3),
                     "btc": round(summarize(b, periods_per_year=ppy)["sharpe"], 3)})
        start = stop
    roll = pd.DataFrame(roll)
    roll["portfolio_beats_gold"] = roll["portfolio"] > roll["gold"]

    corr = pd.DataFrame(rets).fillna(0).corr().iloc[0, 1]

    # Section 6 kill switch, reused from portfolio_b rather than re-implemented:
    # aggregate realised vol above its trailing 95th percentile flattens the book.
    # With two sleeves its rationale -- one trigger across risk that spikes
    # together -- applies again, so both overlays are reported side by side, and
    # gold alone gets the same treatment so the comparison is like for like.
    def with_kill(r: pd.Series) -> tuple[pd.Series, float]:
        bpd_c = len(r) / r.index.normalize().nunique()
        vw = max(2, int(round(20 * bpd_c)))
        k = pbk.kill_switch(r, vw, int(round(252 * 2 * bpd_c)))
        return r.where(~k, 0.0), float(k.mean())

    gold_full = rets["XAUUSD"].reindex(port.index).fillna(0.0)
    ov_rows = []
    for name, r in (("gold alone", gold_full), ("gold + BTC", port)):
        for ov in ("none", "kill switch"):
            rr, flat = (r, 0.0) if ov == "none" else with_kill(r)
            s_ = summarize(rr, periods_per_year=ppy)
            h_ = summarize(rr.loc[:HOLDOUT_END], periods_per_year=ppy)
            ov_rows.append({"book": name, "overlay": ov,
                            "sharpe": round(s_["sharpe"], 3), "cagr": round(s_["cagr"], 4),
                            "max_dd": round(s_["max_drawdown"], 3),
                            "holdout_sharpe": round(h_["sharpe"], 3),
                            "pct_time_flat": round(flat, 3)})
    overlay = pd.DataFrame(ov_rows)

    # stress: 2x spread and 2x financing on both sleeves together
    stress = {}
    for label, sm, fm in [("base", 1, 1), ("2x spread", 2, 1), ("2x financing", 1, 2),
                          ("2x spread + 2x financing", 2, 2)]:
        rr = {s: sleeve(s, cmap[s], sm, fm)[0].loc[common_start:] for s in SLEEVES}
        stress[label] = round(summarize(combine(rr), periods_per_year=ppy)["sharpe"], 3)

    # Deflated Sharpe against the CUMULATIVE trial count: the original grid, the
    # enhancement round, and every instrument in the screen. The trial Sharpe
    # dispersion comes from the screen's cross-section, which is the search that
    # produced these two sleeves.
    from common.validation import expected_max_sharpe, probabilistic_sharpe_ratio
    screen = pd.read_csv(REPORTS / "universe_screen.csv")
    n_screen = int(len(screen))
    n_total = PRIOR_TRIALS + n_screen
    # Per-period Sharpe dispersion of the actual search: the screen's instruments,
    # annual Sharpe de-annualised at the H4 rate. This is the spread that says how
    # far the best of n_total worthless trials would reach by luck alone.
    sr_pp = screen["sharpe"].to_numpy(dtype=float) / np.sqrt(ppy)
    sr_var = float(np.var(sr_pp, ddof=1))
    sr0 = expected_max_sharpe(n_total, sr_var)
    dsr = {"deflated_sharpe_ratio": probabilistic_sharpe_ratio(port, sr0)}
    dsr["passes_at_95pct"] = dsr["deflated_sharpe_ratio"] > 0.95
    dsr_ho = {"deflated_sharpe_ratio":
              probabilistic_sharpe_ratio(port.loc[:HOLDOUT_END], sr0)}
    dsr_ho["passes_at_95pct"] = dsr_ho["deflated_sharpe_ratio"] > 0.95

    cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))
    L = []
    L.append("# Book B portfolio -- gold + bitcoin\n\n")
    L.append("Generated {:%Y-%m-%d %H:%M} UTC from `{}@{}` ({}).\n\n".format(
        dt.datetime.now(dt.UTC), cfg["account"]["login"], cfg["account"]["server"],
        cfg["account"]["trade_mode_label"]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n\n")
    L.append("Sleeves: **{}**, equal-weight, same fixed specification on each. Return "
             "correlation between the sleeves: **{:.2f}**.\n\n".format(
                 " + ".join(SLEEVES), corr))
    L.append("## Portfolio vs gold alone\n\n")
    L.append(_tbl(tab))
    L.append("\n## Kill switch (section 6), like for like\n\n")
    L.append(_tbl(overlay))
    L.append("\n## Rolling 2-year windows (Sharpe)\n\n")
    L.append("Portfolio beats gold alone in **{} of {}** windows.\n\n".format(
        int(roll["portfolio_beats_gold"].sum()), len(roll)))
    L.append(_tbl(roll))
    L.append("\n## Cost stress (full period, portfolio Sharpe)\n\n")
    L.append("| Scenario | Sharpe |\n|---|---|\n")
    for k, v in stress.items():
        L.append(f"| {k} | {v} |\n")
    L.append("\n## Deflated Sharpe, cumulative trial count\n\n")
    L.append("Trials counted: **{}** = {} (spec grid + enhancement round) + {} (every "
             "instrument in the cross-instrument screen, real and synthetic).\n\n".format(
                 n_total, PRIOR_TRIALS, n_screen))
    L.append("| Sample | Deflated Sharpe | Passes 0.95 |\n|---|---|---|\n")
    L.append("| full | {:.3f} | {} |\n".format(dsr["deflated_sharpe_ratio"],
                                               dsr["passes_at_95pct"]))
    L.append("| holdout only (pre-2020, unseen by the screen) | {:.3f} | {} |\n".format(
        dsr_ho["deflated_sharpe_ratio"], dsr_ho["passes_at_95pct"]))
    (REPORTS / "portfolio_gold_btc.md").write_text("".join(L), encoding="utf-8")
    tab.to_csv(REPORTS / "portfolio_gold_btc.csv", index=False)
    roll.to_csv(REPORTS / "portfolio_gold_btc_rolling.csv", index=False)
    overlay.to_csv(REPORTS / "portfolio_gold_btc_overlay.csv", index=False)

    print(tab.to_string(index=False))
    print("\n" + roll.to_string(index=False))
    print("\n" + overlay.to_string(index=False))
    print("\ncorr", round(corr, 3), "| stress", stress)
    print("DSR full", round(dsr["deflated_sharpe_ratio"], 4), "| DSR holdout",
          round(dsr_ho["deflated_sharpe_ratio"], 4), "| trials", n_total)
    return 0


def _tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |\n",
           "|" + "---|" * len(cols) + "\n"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |\n")
    return "".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
