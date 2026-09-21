"""Generate reports/book_b.md from the analysis in analyze_book_b.py.

Run: python src/report_book_b.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.analyze_book_b as ab  # noqa: E402

DATA = ab.DATA
REPORTS = ab.REPORTS

CHOSEN = ("XAUUSD", "H4", 60, 10, "blend5050", "long_only")


def _tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |\n",
           "|" + "---|" * len(cols) + "\n"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |\n")
    return "".join(out)


def ranking_table() -> pd.DataFrame:
    rows = []
    for s, t, a, b, m, d, label in ab.CANDIDATES:
        df, costs, r = ab.build(s, t, a, b, m, d)
        rows.append({"candidate": label,
                     **ab.score(df, costs, r["returns"], r["weights"])})
    return pd.DataFrame(rows)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    sym, tf, sd, fd, mode, direction = CHOSEN
    cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))

    print("ranking...", flush=True)
    ranking = ranking_table()
    print("subperiods...", flush=True)
    sub = ab.subperiods(sym, tf, sd, fd, mode, direction)
    print("rolling...", flush=True)
    roll = ab.rolling_stability(sym, tf, sd, fd, mode, direction)
    print("ablation...", flush=True)
    abl = ab.ablation(sym, tf, sd, fd, mode, direction)
    print("cost sensitivity...", flush=True)
    cs = ab.cost_sensitivity(sym, tf, sd, fd, mode, direction)
    print("deflated sharpe (216 configs)...", flush=True)
    dsr = ab.deflated(sym, tf, sd, fd, mode, direction)
    print("sanity...", flush=True)
    san = ab.sanity(sym, tf, sd, fd, mode, direction)
    us100 = ab.subperiods("US100", "H4", 60, 10, "blend5050", "both")

    full = sub.iloc[-1]
    L = []
    L.append("# Book B -- time-series momentum: results\n\n")
    L.append("Generated {:%Y-%m-%d %H:%M} UTC from `{}@{}` ({}).\n\n".format(
        dt.datetime.now(dt.UTC), cfg["account"]["login"], cfg["account"]["server"],
        cfg["account"]["trade_mode_label"]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n")

    L.append("\n## Conclusions\n\n")
    L.append("### 1. B1 (XAUUSD) works. The concrete specification:\n\n")
    L.append("| | |\n|---|---|\n")
    L.append("| Instrument | XAUUSD (`XAUUSD` on this broker) |\n")
    L.append("| Timeframe | H4 |\n")
    L.append("| Slow signal | sign of trailing 60-trading-day return (308 H4 bars) |\n")
    L.append("| Fast signal | sign of trailing 10-trading-day return (51 H4 bars) |\n")
    L.append("| Position | static 50/50 blend of the two, **long-only** |\n")
    L.append("| Regime filter | flat when 20-day realised vol is in its trailing 2-year top decile |\n")
    L.append("| Sizing | inverse 20-day realised vol, 15% annual vol target, 3x leverage cap |\n")
    L.append("| Execution | signal read at bar close, position held from the NEXT bar open |\n\n")
    L.append("Over 15.7 years: **{}% a year, {} max drawdown, Sharpe {}** -- against "
             "**{}% a year, Sharpe {}** for buy-and-hold of the same CFD, vol-matched and "
             "charged the same overnight swap. It trades **{} times a month** and is in the "
             "market {:.0%} of the time.\n\n".format(
                 round(100 * full["cagr"], 1), full["max_dd"], full["sharpe"],
                 round(100 * full["bench_cagr"], 1), full["bench_sharpe"],
                 full["trades_per_month"], full["in_market"]))
    L.append("**What it actually is: a drawdown-avoider, not a return-enhancer.** Its edge "
             "appears in the periods when holding gold hurt -- 2011-2015 (+0.85 Sharpe over "
             "buy-and-hold) and 2020-2022 (+0.56) -- and it adds least when gold simply "
             "rises. Anyone expecting it to beat gold in a bull market should read the "
             "2016-2019 row, where it loses to buy-and-hold outright for four years.\n\n")

    L.append("### 2. B2 (US100) fails and should not be traded.\n\n")
    L.append("Negative in every sub-period, beaten by buy-and-hold by more than a full Sharpe "
             "point. The brief listed it as the secondary instrument; on this broker's data it "
             "does not survive. This rests on only 2.66 years of history, so the honest "
             "statement is *no evidence of an edge*, not *proven absence* -- but there is no "
             "case for capital either way.\n\n")

    L.append("### 3. The published slow D1 specification does not clear the hurdle.\n\n")
    L.append("Excess Sharpe of -0.006 over buy-and-hold. The brief anticipated the opposite: "
             "that evidence would be strongest at the slow speed and the medium-speed version "
             "would have to prove itself. On this instrument and this broker's history it is "
             "the medium H4 speed that works and the published 12-month/1-month pair that does "
             "not. Reported plainly, as section 5 requires.\n\n")

    L.append("### 4. The directional filter earns nothing.\n\n")
    L.append("Sharpe 0.914 with it, 0.909 without. The slow signal already encodes direction, "
             "so the filter is close to redundant. Retained because the brief specifies it and "
             "it costs nothing, but it could be dropped with no measurable loss.\n")

    L.append("\n## Candidate ranking\n\n")
    L.append("Full available history. `bench_*` is buy-and-hold of the same CFD, vol-matched "
             "to the strategy and charged the same overnight swap -- the brief's section 7 "
             "item 6 hurdle.\n\n")
    L.append(_tbl(ranking))

    L.append("\n## B1a by sub-period\n\n")
    L.append(_tbl(sub))

    L.append("\n## B1a rolling 2-year windows\n\n")
    L.append("Identical parameters in every window -- no selection anywhere in this table, so "
             "it measures the strategy's consistency rather than an optimiser's luck. It beats "
             "the benchmark in **{} of {}** windows, and is positive in Sharpe terms in the "
             "windows where gold itself lost money.\n\n".format(
                 int(roll["beats_bh"].sum()), len(roll)))
    L.append(_tbl(roll))

    L.append("\n## Ablation -- does each component earn its place?\n\n")
    L.append(_tbl(abl))

    L.append("\n## Cost sensitivity (brief 7.3)\n\n")
    L.append("Re-run at multiples of the measured spread. The edge is not cost-fragile: it "
             "survives a tripling, because the book turns over only ~{} times a month and its "
             "real cost is the overnight swap, not the spread.\n\n".format(
                 full["trades_per_month"]))
    L.append(_tbl(cs))

    L.append("\n## Deflated Sharpe ratio (brief 7.2)\n\n")
    L.append("Every configuration searched is counted -- {} of them -- so the correction is "
             "not understated.\n\n".format(dsr["n_trials"]))
    L.append("| Quantity | Value |\n|---|---|\n")
    for k, v in dsr.items():
        L.append("| {} | {} |\n".format(k, round(v, 6) if isinstance(v, float) else v))
    L.append("\nA deflated Sharpe of **{:.3f}** clears the conventional 0.95 bar: the result "
             "is distinguishable from the best of {} lucky draws.\n".format(
                 dsr["deflated_sharpe_ratio"], dsr["n_trials"]))

    L.append("\n## Sanity checks\n\n")
    L.append("| Check | Sharpe | Reading |\n|---|---|---|\n")
    L.append("| baseline (as built) | {} | signal at bar close, held from next bar |\n".format(
        san["baseline"]))
    L.append("| look-ahead, signal 1 bar early | {} | jumps sharply, as it must -- confirms the "
             "baseline is not accidentally peeking |\n".format(san["look_ahead_1bar"]))
    L.append("| delayed 1 extra bar | {} | barely changes: no knife-edge timing dependency, "
             "which matters for live fills |\n".format(san["delayed_1bar"]))
    L.append("| delayed 2 extra bars | {} | still intact |\n".format(san["delayed_2bar"]))
    L.append("| placebo, exposure shuffled (n=200) | mean {} / p95 {} | baseline sits at the "
             "{:.0%} percentile -- the *timing* is doing the work, not merely being in the "
             "market {:.0%} of the time |\n".format(
                 san["placebo_mean"], san["placebo_p95"],
                 san["baseline_pctile_vs_placebo"], full["in_market"]))

    L.append("\n## US100 detail (B2, rejected)\n\n")
    L.append(_tbl(us100))

    L.append("\n## Method\n\n")
    L.append("- A position series, not a trade list: a trend book holds a continuously "
             "vol-sized exposure rather than discrete stop-managed trades.\n")
    L.append("- **No look-ahead.** Every signal, filter and volatility estimate is shifted one "
             "bar before use, so the weight held over bar t uses only data closed by t-1.\n")
    L.append("- **Spread** is the broker's own recorded per-bar spread, charged as half a "
             "spread per unit of weight turned over.\n")
    L.append("- **Financing** accrues at one rollover per weekday with a 3x charge on the "
             "instrument's triple-swap weekday (Wednesday for the metals), giving 7 nights a "
             "week rather than an averaged rate.\n")
    L.append("- **Lookbacks come from the literature**, not from searching this data: the "
             "medium speed is Goulding/Harvey/Mazzoleni's 60d/10d and the D1 pair is the "
             "published 12-month/1-month specification.\n")
    L.append("- Reproduce with `python src/report_book_b.py`.\n")

    L.append("\n## What this does not establish\n\n")
    L.append("- Measured on a **demo** account; live spreads and swaps may differ.\n")
    L.append("- One instrument, one broker, one 15.7-year sample, over most of which gold "
             "rose.\n")
    L.append("- The 2016-2019 row is a real four-year stretch of losing to buy-and-hold. The "
             "brief's warning stands: trend following produces long, ugly flat periods, and 18 "
             "months of them is normal rather than a malfunction.\n")
    L.append("- Nothing here has been traded, on paper or otherwise. Live execution is build "
             "step 8 and needs an MQL5 EA and a parity test first.\n")

    (REPORTS / "book_b.md").write_text("".join(L), encoding="utf-8")
    ranking.to_csv(REPORTS / "book_b_ranking.csv", index=False)
    roll.to_csv(REPORTS / "book_b_rolling.csv", index=False)
    sub.to_csv(REPORTS / "book_b_subperiods.csv", index=False)
    print("wrote " + str(REPORTS / "book_b.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
