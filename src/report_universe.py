"""Run the cross-instrument screen and write reports/universe_screen.md.

Usage:
    python src/report_universe.py --pull    # enumerate + pull data + costs, then screen
    python src/report_universe.py           # re-screen from cached data
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

import src.universe as un  # noqa: E402
import src.screen_universe as su  # noqa: E402
from common.portfolio import summarize  # noqa: E402
from common.validation import probabilistic_sharpe_ratio  # noqa: E402

DATA = un.DATA
REPORTS = un.REPORTS
META_CSV = DATA / "universe_meta.csv"
COSTS_CSV = DATA / "universe_costs.csv"


def _tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |\n",
           "|" + "---|" * len(cols) + "\n"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |\n")
    return "".join(out)


ENUM_CSV = DATA / "universe_enumerated.csv"


def do_pull() -> tuple[pd.DataFrame, pd.DataFrame]:
    # Each stage checkpoints to disk and is skipped on a re-run if its output
    # already exists, so a run killed partway resumes instead of starting over.
    # (The first attempt at this died after 25 minutes in enumeration with
    # nothing saved.)
    if ENUM_CSV.exists():
        meta = pd.read_csv(ENUM_CSV)
        print(f"enumeration: reusing {len(meta)} symbols from checkpoint", flush=True)
    else:
        print("enumerating universe ...", flush=True)
        meta = un.enumerate_universe()
        meta.to_csv(ENUM_CSV, index=False)
    print(f"  {len(meta)} symbols with >= {un.MIN_YEARS}y of H4 history", flush=True)

    if META_CSV.exists() and COSTS_CSV.exists():
        print("pull + costs: reusing checkpoints", flush=True)
        return pd.read_csv(META_CSV), pd.read_csv(COSTS_CSV)

    # SCREEN WINDOW: the last MIN_YEARS only. Two reasons. Practical: that span is
    # already cached from the depth probe, while reaching back to 2010 forces MT5
    # to download a further decade of M1 bars per symbol -- measured at ~5
    # minutes each, about four hours for the universe. Statistical, and more
    # important: it leaves everything BEFORE the window untouched by the
    # selection. Survivors are then validated on that earlier history, which is a
    # genuine holdout -- the one check that answers the multiple-testing problem
    # rather than merely correcting for it.
    screen_start = (pd.Timestamp.now(tz="UTC")
                    - pd.Timedelta(days=int(un.MIN_YEARS * 365.25))).strftime("%Y-%m-%d")
    print(f"pulling H4 history from {screen_start} (screen window) ...", flush=True)
    cov = un.pull(meta["symbol"].tolist(), start=screen_start)
    ok = set(cov[cov.ok]["symbol"]) if len(cov) else set()
    meta = meta[meta.symbol.isin(ok)].reset_index(drop=True)

    # The enumeration probe only establishes that history reaches the cutoff --
    # it is a lower bound, not the real depth. Overwrite with what the full
    # fetch actually returned, so the report never quotes a made-up span.
    real = cov[cov.ok].set_index("symbol")
    meta["start"] = meta["symbol"].map(real["start"])
    meta["end"] = meta["symbol"].map(real["end"])
    meta["bars"] = meta["symbol"].map(real["bars"])
    meta["years"] = (
        (pd.to_datetime(meta["end"]) - pd.to_datetime(meta["start"])).dt.days / 365.25
    ).round(2)
    meta.to_csv(META_CSV, index=False)
    print(f"  {len(meta)} symbols pulled", flush=True)

    print("measuring costs (tick sampling, screening grade) ...", flush=True)
    costs = un.costs_for(meta["symbol"].tolist())
    costs.to_csv(COSTS_CSV, index=False)
    print(f"  costs for {len(costs)} symbols", flush=True)
    return meta, costs


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    if "--pull" in sys.argv or not (META_CSV.exists() and COSTS_CSV.exists()):
        meta, costs = do_pull()
    else:
        meta, costs = pd.read_csv(META_CSV), pd.read_csv(COSTS_CSV)

    print("screening ...", flush=True)
    res, extra = su.screen(meta, costs)
    stats = extra["stats"]
    sel = su.select(res)
    passed = sel[sel.passes]
    synth = res[res.kind == "synthetic"]

    # Deflate the best real candidate against the EFFECTIVE number of
    # independent tests, not the raw symbol count.
    best_dsr = np.nan
    if len(passed):
        best = passed.iloc[0]["symbol"]
        best_dsr = probabilistic_sharpe_ratio(
            extra["series"][best], stats["expected_max_sharpe_under_null"])

    cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))
    L = []
    L.append("# Cross-instrument screen -- where else does Book B work?\n\n")
    L.append("Generated {:%Y-%m-%d %H:%M} UTC from `{}@{}` ({}).\n\n".format(
        dt.datetime.now(dt.UTC), cfg["account"]["login"], cfg["account"]["server"],
        cfg["account"]["trade_mode_label"]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n")

    L.append("\n## What was done\n\n")
    L.append("Book B's specification -- H4, slow 60d / fast 10d blended 50/50, long-only, "
             "flat in the top volatility decile, sized on inverse 20-day realised vol at a "
             "15% target -- applied **unchanged** to every instrument on this broker with at "
             "least {:.0f} years of H4 history. Not one parameter was re-tuned per "
             "instrument.\n\n".format(un.MIN_YEARS))
    L.append("**{} real instruments** were tested, plus **{} synthetic instruments as a null "
             "control**. The synthetics are Deriv's engineered random processes, not markets; "
             "a momentum signal should not work on them, so they are the rows that say whether "
             "the engine is measuring an edge or a bug.\n".format(
                 stats["n_real_tested"], stats["n_synthetic_controls"]))

    L.append("\n## The multiple-testing problem, and what it does to the answer\n\n")
    L.append("Testing {} instruments and keeping the best is how false discoveries are "
             "manufactured. Three numbers decide whether the winners are real:\n\n".format(
                 stats["n_real_tested"]))
    L.append("| Quantity | Value | Reading |\n|---|---|---|\n")
    L.append("| Median excess Sharpe over buy-and-hold | **{}** | the typical instrument |\n"
             .format(stats["median_excess_sharpe"]))
    L.append("| Share beating costed buy-and-hold | **{:.0%}** | 50% would be a coin flip |\n"
             .format(stats["pct_beating_bh"]))
    L.append("| Average pairwise correlation | {} | how much the tests overlap |\n".format(
        stats["avg_pairwise_correlation"]))
    L.append("| Effective independent tests | **{}** | not {} -- correlated instruments are "
             "not separate experiments |\n".format(
                 stats["effective_independent_tests"], stats["n_real_tested"]))
    L.append("| Expected best Sharpe under the null | {} | the bar luck alone would clear |\n"
             .format(stats["expected_max_sharpe_under_null"]))

    L.append("\n## Null control -- the synthetics\n\n")
    if len(synth):
        L.append(_tbl(synth[["symbol", "sharpe", "bench_sharpe", "excess_sharpe",
                             "beats_bh", "window_hit_rate", "trades_per_week"]]))
        L.append("\nThese are random processes with engineered volatility. A momentum "
                 "signal that scored well here would mean the engine is manufacturing "
                 "returns rather than finding them.\n")
    else:
        L.append("_No synthetic controls available._\n")

    L.append("\n## Instruments that pass all three bars\n\n")
    L.append("A candidate must clear **all** of: excess Sharpe over costed buy-and-hold "
             ">= {}, absolute Sharpe >= {}, and beating the benchmark in >= {:.0%} of "
             "rolling 2-year windows. Ranking on Sharpe alone is what the controls above "
             "exist to prevent.\n\n".format(su.MIN_EXCESS_SHARPE, su.MIN_SHARPE,
                                            su.MIN_WINDOW_HIT_RATE))
    cols = ["symbol", "group", "years", "sharpe", "cagr", "max_dd", "calmar",
            "bench_sharpe", "excess_sharpe", "window_hit_rate", "trades_per_week",
            "in_market"]
    if len(passed):
        L.append(_tbl(passed[cols]))
    else:
        L.append("**None.** No instrument clears all three bars.\n")

    L.append("\n## Full cross-section (real instruments, ranked by excess Sharpe)\n\n")
    L.append(_tbl(sel[cols + ["passes"]]))

    L.append("\n## Method and caveats\n\n")
    L.append("- The same fixed specification everywhere; no per-instrument fitting, so the "
             "only selection is across instruments and it is countable.\n")
    L.append("- Each instrument is compared against **its own** vol-matched buy-and-hold, "
             "charged that instrument's own nightly swap -- not against zero.\n")
    L.append("- Spreads are tick-measured but on a **14-day screening window**, shorter than "
             "the 30 days used for the core instruments. Median spread is stable enough for "
             "a screen; the 95th percentile is not. Anything that survives here must have "
             "its costs re-measured properly before it is traded.\n")
    L.append("- Symbols with fewer than {:.0f} years or {} H4 bars were excluded, so nothing "
             "is judged on a sample too short to hold several independent windows.\n".format(
                 un.MIN_YEARS, un.MIN_BARS))
    L.append("- Read-only throughout: `symbol_info`, `copy_rates_range`, "
             "`copy_ticks_range`. No order functions.\n")
    L.append("- Reproduce with `python src/report_universe.py --pull`.\n")

    (REPORTS / "universe_screen.md").write_text("".join(L), encoding="utf-8")
    res.drop(columns=[c for c in res.columns if c.startswith("_")]).to_csv(
        REPORTS / "universe_screen.csv", index=False)
    print("\nwrote " + str(REPORTS / "universe_screen.md"))
    print(json.dumps(stats, indent=2))
    if len(passed):
        print(f"\nPASSED ({len(passed)}): {list(passed.symbol)}")
        print(f"best candidate deflated Sharpe vs effective null: {best_dsr:.4f}")
    else:
        print("\nPASSED: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
