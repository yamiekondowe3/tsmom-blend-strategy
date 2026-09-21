"""Step 2 -- pull price history from the connected MT5 terminal and report,
honestly, how much of it actually arrived.

READ-ONLY (brief section 2): copy_rates_range only. No order functions.

Two rules from the brief drive the shape of this script:

  * "Do not substitute Yahoo, TradingView or any third-party feed -- CFD prices
    differ from the underlying index, and that gap is where backtests lie."
    So every bar here comes from the broker that would actually fill the order.

  * "Report how much history the broker actually provides -- do not assume
    5 years arrived." It did not. Deriv carries ~15.7y on the metals and only
    ~2.66y on the two index CFDs. That asymmetry is a finding, not a nuisance,
    and it is written into reports/data_coverage.md rather than smoothed over.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from common.data_fetch import (  # noqa: E402
    fetch_mt5, save_csv, report_coverage, bars_per_day,
)

DATA = REPO / "data"
REPORTS = REPO / "reports"

SYMBOLS = ["US100", "US500", "XAUUSD", "XAGUSD"]
TIMEFRAMES = ["D1", "H4", "H1"]
PAIRS = [("US100", "US500"), ("XAUUSD", "XAGUSD")]

# Request far more than the brief's 5-year minimum and let the broker return
# whatever it has. Asking for exactly 5 years would hide the fact that the
# metals carry three times that -- and hide, too, that the indices carry half.
REQUEST_START = pd.Timestamp("2010-01-01", tz="UTC")
MIN_YEARS_REQUIRED = 5.0


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    end = pd.Timestamp.now(tz="UTC")

    coverage, bpd_rows, frames = [], [], {}

    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            df = fetch_mt5(sym, tf, REQUEST_START, end)
            if df.empty:
                print(f"EMPTY {sym} {tf}", file=sys.stderr)
                coverage.append({"symbol": sym, "timeframe": tf, "n_bars": 0,
                                 "years_covered": 0.0, "achieved_start": None,
                                 "achieved_end": None, "venue": "n/a"})
                continue
            path = save_csv(df, sym, tf, DATA)
            cov = report_coverage(df, sym)
            cov.update({"timeframe": tf, "file": path.name})
            coverage.append(cov)
            frames[(sym, tf)] = df
            bpd = bars_per_day(df)
            bpd_rows.append({"symbol": sym, "timeframe": tf,
                             "bars_per_day": round(bpd, 4),
                             "n_bars": len(df),
                             "n_trading_days": df.index.normalize().nunique()})
            print(f"{sym:<7} {tf:<3} {len(df):>7} bars  "
                  f"{cov['achieved_start'][:10]}..{cov['achieved_end'][:10]}  "
                  f"{cov['years_covered']}y -> {path.name}")

    cov_df = pd.DataFrame(coverage)
    bpd_df = pd.DataFrame(bpd_rows)
    bpd_df.to_csv(DATA / "bars_per_day.csv", index=False)

    # Leg alignment. The two legs of a pair can only be traded together on bars
    # where BOTH quote, so the overlap -- not either leg's own history -- is the
    # real sample size for the cost screen.
    align_rows = []
    for a, b in PAIRS:
        for tf in TIMEFRAMES:
            fa, fb = frames.get((a, tf)), frames.get((b, tf))
            if fa is None or fb is None:
                continue
            common = fa.index.intersection(fb.index)
            lo = max(fa.index.min(), fb.index.min())
            hi = min(fa.index.max(), fb.index.max())
            in_a = fa.loc[lo:hi]
            in_b = fb.loc[lo:hi]
            union = in_a.index.union(in_b.index)
            dropped = len(union) - len(common)
            align_rows.append({
                "pair": f"{a}/{b}", "timeframe": tf,
                "overlap_start": str(lo), "overlap_end": str(hi),
                "overlap_years": round((hi - lo).days / 365.25, 2),
                "common_bars": len(common),
                "leg_a_bars": len(in_a),
                "leg_b_bars": len(in_b),
                "bars_missing_one_leg": dropped,
                "pct_bars_dropped": round(100 * dropped / max(len(union), 1), 2),
            })
            print(f"ALIGN {a}/{b} {tf}: {len(common)} common bars over "
                  f"{align_rows[-1]['overlap_years']}y, "
                  f"{align_rows[-1]['pct_bars_dropped']}% dropped")

    align_df = pd.DataFrame(align_rows)
    align_df.to_csv(DATA / "leg_alignment.csv", index=False)
    write_report(cov_df, bpd_df, align_df)
    return 0


def write_report(cov: pd.DataFrame, bpd: pd.DataFrame, align: pd.DataFrame) -> None:
    cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))
    acc = cfg["account"]
    short = cov[(cov.n_bars > 0) & (cov.years_covered < MIN_YEARS_REQUIRED)]

    L = []
    L.append("# Data coverage -- what the broker actually provided\n\n")
    L.append("Generated {:%Y-%m-%d %H:%M} UTC from `{}@{}` ({}).\n\n".format(
        dt.datetime.now(dt.UTC), acc["login"], acc["server"], acc["trade_mode_label"]))
    L.append("Server clock offset vs UTC: **{} h** (measured; method: {}). "
             "All timestamps in `data/` are UTC.\n\n".format(
                 cfg["server_clock"]["offset_hours"], cfg["server_clock"]["method"]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n")

    L.append("\n## Headline: the index CFDs are far short of the 5-year minimum\n\n")
    if short.empty:
        L.append("All symbols met the brief's 5-year minimum.\n")
    else:
        L.append("The brief (section 3.1) asks for **{:.0f} years minimum** per symbol. "
                 "These did not reach it:\n\n".format(MIN_YEARS_REQUIRED))
        for _, r in short.iterrows():
            L.append("- **{} {}** -- {}y (from {}), short by {:.2f}y\n".format(
                r["symbol"], r["timeframe"], r["years_covered"],
                str(r["achieved_start"])[:10], MIN_YEARS_REQUIRED - r["years_covered"]))
        L.append("\nDeriv's index CFD listings begin 2024-01-22. This is a hard limit of the "
                 "broker's own history, not a truncation this script can fix: `Max bars in "
                 "chart` is already 100,000,000 and the request asked for history from 2010.\n")
        L.append("\n**What it means for the screen.** Pair A1 (US100/US500) is screened on "
                 "~2.66 years. That is adequate for a spread-cost ratio, which is a "
                 "short-horizon quantity, but it is thin for a half-life estimate and it "
                 "contains no pre-2024 regime at all -- no 2022 rate shock, no COVID. A1's "
                 "verdict should be read as provisional on that basis whichever way it lands. "
                 "Pair A2 (XAUUSD/XAGUSD) has 15.7 years and carries no such caveat.\n")

    L.append("\n## Per symbol and timeframe\n\n")
    L.append("| Symbol | TF | Bars | From | To | Years | Meets 5y |\n|---|---|---|---|---|---|---|\n")
    for _, r in cov.iterrows():
        ok = "n/a" if r["n_bars"] == 0 else (
            "yes" if r["years_covered"] >= MIN_YEARS_REQUIRED else "**NO**")
        L.append("| {} | {} | {:,} | {} | {} | {} | {} |\n".format(
            r["symbol"], r["timeframe"], r["n_bars"], str(r["achieved_start"])[:10],
            str(r["achieved_end"])[:10], r["years_covered"], ok))

    L.append("\n## Observed bars per trading day\n\n")
    L.append("Measured from the data, not assumed. Used to convert an OU half-life in bars "
             "into days for the brief's 5-day drop rule. Assuming 24 H1 bars/day would "
             "overstate bars/day (these CFDs take a daily break and close at weekends) and "
             "so understate the half-life in days -- biasing pairs *towards* passing.\n\n")
    L.append("| Symbol | TF | Bars/day | Bars | Trading days |\n|---|---|---|---|---|\n")
    for _, r in bpd.iterrows():
        L.append("| {} | {} | {} | {:,} | {:,} |\n".format(
            r["symbol"], r["timeframe"], r["bars_per_day"], r["n_bars"], r["n_trading_days"]))

    L.append("\n## Leg alignment\n\n")
    L.append("A pair can only be traded on bars where **both** legs quote. The overlap is the "
             "real sample size; bars present on one leg only are dropped.\n\n")
    L.append("| Pair | TF | Overlap | Years | Common bars | Dropped | % dropped |\n")
    L.append("|---|---|---|---|---|---|---|\n")
    for _, r in align.iterrows():
        L.append("| {} | {} | {}..{} | {} | {:,} | {:,} | {}% |\n".format(
            r["pair"], r["timeframe"], r["overlap_start"][:10], r["overlap_end"][:10],
            r["overlap_years"], r["common_bars"], r["bars_missing_one_leg"],
            r["pct_bars_dropped"]))

    L.append("\n## Method\n\n")
    L.append("- Source: `MetaTrader5.copy_rates_range` via `common/data_fetch.py::fetch_mt5`, "
             "requesting 2010-01-01 to now so the broker returns its full depth.\n")
    L.append("- No third-party price feed was used anywhere (brief section 3.1).\n")
    L.append("- The `spread` column is the broker's own recorded per-bar spread, converted "
             "from MT5 integer points into price units.\n")
    L.append("- Price CSVs are gitignored as bulk data; regenerate with "
             "`python src/pull_history.py`.\n")

    (REPORTS / "data_coverage.md").write_text("".join(L), encoding="utf-8")
    print("\nwrote " + str(REPORTS / "data_coverage.md"))


if __name__ == "__main__":
    raise SystemExit(main())
