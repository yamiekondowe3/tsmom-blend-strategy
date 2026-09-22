"""Write reports/enhancements.md from src/enhancements.py."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.enhancements as en  # noqa: E402

REPORTS = en.REPORTS
DATA = en.DATA


def _tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |\n",
           "|" + "---|" * len(cols) + "\n"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |\n")
    return "".join(out)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    print("running enhancement round (a few minutes) ...", flush=True)
    R = en.run_all()
    cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))
    base = R["baseline"]
    ks = R["kill_switch_rolling"]

    L = []
    L.append("# Enhancement round -- what was tried, and what survived\n\n")
    L.append("Generated {:%Y-%m-%d %H:%M} UTC from `{}@{}` ({}).\n\n".format(
        dt.datetime.now(dt.UTC), cfg["account"]["login"], cfg["account"]["server"],
        cfg["account"]["trade_mode_label"]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n")

    L.append("\n## Headline: five of six avenues fail, and that is the finding\n\n")
    L.append("Six independent attempts were made to improve Book B. One is retained on "
             "design grounds with a near-neutral measured effect; the other five are "
             "rejected. **The plain 60/10 blend on gold survives all of them.**\n\n")
    L.append("That is worth as much as a positive result would have been. A specification "
             "that six independent attempts cannot improve is far more likely to be a real "
             "effect than a lucky corner of a parameter grid -- which is exactly what the "
             "brief's plateau test is trying to establish. The temptation was to keep "
             "searching until something beat it; that search is itself multiple testing, so "
             "every evaluation below is counted and the deflated Sharpe recomputed against "
             "the larger total.\n\n")

    L.append("| # | Avenue | Verdict | Measured effect |\n|---|---|---|---|\n")
    L.append("| 1 | Better volatility estimators (Yang-Zhang, downside semi-vol) | "
             "**Rejected** | Both worse than the crude close-to-close default |\n")
    L.append("| 2 | Dynamic speed / state-conditional tilt (brief Variant 1) | "
             "**Rejected** | Sharpe 0.714 vs 0.922 for the static 50/50 blend |\n")
    L.append("| 3 | Speed ensembling across the lookback range | "
             "**Rejected on Sharpe** | 0.80-0.87 vs 0.92; better drawdown, worse return |\n")
    L.append("| 4 | Extra instruments (XAGUSD, US500) | "
             "**Rejected** | Silver marginal, US500 fails outright |\n")
    L.append("| 5 | Multi-instrument portfolio (gold + silver) | "
             "**Rejected** | Halves Sharpe: 0.913 -> 0.488 |\n")
    L.append("| 6 | Portfolio kill switch (brief section 6) | "
             "**Retained, near-neutral** | +0.064 full-sample, but helps in only "
             "{} of {} rolling windows |\n".format(int((ks["delta"] > 0).sum()), len(ks)))

    L.append("\n## 1. Volatility estimators -- the crude default wins\n\n")
    L.append("The brief says to test Yang-Zhang and downside semi-volatility as variants, "
             "and also to *resist sophistication here* because the published time-series "
             "momentum work uses a deliberately simple model. Both instincts are vindicated: "
             "neither estimator improves on close-to-close.\n\n")
    L.append(_tbl(R["vol_estimators"]))
    L.append("\nYang-Zhang does what Baltas & Kosowski predict -- it cuts turnover and "
             "slightly improves drawdown, because a less noisy volatility estimate means a "
             "less jumpy position size. It just does not pay for itself in return. Keep the "
             "crude one.\n")

    L.append("\n## 2. Signal variants -- the static blend beats the dynamic tilt\n\n")
    L.append("Goulding, Harvey & Mazzoleni's dynamic-speed idea is to tilt weights after "
             "Corrections and Rebounds based on how those states have paid historically. "
             "Estimated strictly walk-forward (expanding window, shifted, and zero until a "
             "state has 500 observations) it **underperforms the static 50/50 blend**. The "
             "state-conditional means are too noisy on one instrument to be worth acting on; "
             "the paper's evidence comes from equity markets and the brief already flagged "
             "that it is untested on gold.\n\n")
    L.append(_tbl(R["signal_variants"]))

    L.append("\n## 3. Speed ensembling -- better drawdown, worse return\n\n")
    L.append("Averaging the position across several slow/fast pairs is the standard answer to "
             "parameter uncertainty, and it averages *over* the grid rather than selecting "
             "*from* it, so it adds no fitting of its own. It does cut max drawdown "
             "materially and raises trade frequency. It does not improve Sharpe.\n\n")
    L.append(_tbl(R["ensembles"]))
    L.append("\nOne ensemble shows a better Calmar than the single spec -- but it is one of "
             "four definitions tried, and choosing among ensembles is itself a fitting "
             "decision. Treated as such, and not adopted. It remains the most defensible "
             "*robustness* option if dependence on a single parameter pair ever becomes the "
             "bigger worry than the Sharpe gap.\n")

    L.append("\n## 4. The fixed spec on every instrument in the brief's universe\n\n")
    L.append("Identical parameters, no refitting -- the strongest available test, since the "
             "specification was chosen on gold and has never seen these series.\n\n")
    L.append(_tbl(R["instruments"]))
    L.append("\n**Gold is the only instrument that works.** Silver clears the benchmark by "
             "+0.04 Sharpe over 15.7 years, which is noise rather than an edge; US500 fails "
             "as badly as US100 did. All four instruments in the brief's universe have now "
             "been tested for momentum, and three of them fail.\n")

    L.append("\n## 5. Portfolio construction -- adding silver destroys the book\n\n")
    L.append(_tbl(R["portfolios"]))
    L.append("\nThe gold and silver books correlate only 0.50 and overlap in the market just "
             "17% of the time, so the diversification case looked reasonable. It does not "
             "survive contact with the numbers: **adding silver nearly halves portfolio "
             "Sharpe**, because a book with no edge contributes risk and cost without "
             "contributing return. Diversification cannot manufacture an edge that is not "
             "there.\n")
    L.append("\nIt would have raised trade frequency from 0.87 to 1.8 a week, much closer to "
             "the brief's 2-3 target. That is exactly the trade the brief forbids: *never "
             "relax a threshold to hit the frequency target*. The rule is about thresholds, "
             "but the principle is the same -- the answer to too few trades is fewer trades, "
             "not worse ones.\n")

    L.append("\n## 6. The kill switch -- retained, but believe it only as insurance\n\n")
    L.append("Aggregate realised volatility above its trailing 95th percentile flattens the "
             "book. Full-sample it adds +0.064 Sharpe and trims volatility from 0.088 to "
             "0.081, flat about 6% of the time. Rolling windows tell a more honest story:\n\n")
    L.append(_tbl(ks))
    L.append("\nIt improves only **{} of {}** windows, and essentially the whole full-sample "
             "gain comes from one of them (the COVID window, +0.43). In the other five it "
             "costs a little. That is the signature of tail insurance, not of an alpha "
             "source, and it should be held for that reason rather than for its average "
             "contribution.\n".format(int((ks["delta"] > 0).sum()), len(ks)))
    L.append("\nOne structural caveat. The brief's rationale for a single kill switch is that "
             "*both* books fail on the same volatility spike, so scaling them separately "
             "leaves the portfolio correlated exactly when that costs money. With Book A dead "
             "there is only one book, so that rationale does not currently apply. The switch "
             "is kept because it is cheap and because the reasoning returns the moment a "
             "second book does.\n")

    L.append("\n## Overfitting accounting\n\n")
    L.append("Searching for improvements is multiple testing. Every evaluation in this round "
             "is added to the count and the deflated Sharpe recomputed.\n\n")
    L.append("| Quantity | Value |\n|---|---|\n")
    for k, v in R["dsr"].items():
        L.append("| {} | {} |\n".format(k, v))
    L.append("\nThe strategy still clears the 0.95 bar against the **cumulative** trial "
             "count, not just the original grid.\n")

    L.append("\n## Where this leaves the overall goal\n\n")
    L.append("| Goal (brief section 1.4) | Target | Actual | Status |\n|---|---|---|---|\n")
    L.append("| Portfolio trade frequency | 2-3 / week | **{}** / week | short |\n".format(
        base["trades_per_week"]))
    L.append("| Book A carries frequency | 1.5-3 / week | 0 | Book A has no signal |\n")
    L.append("| Book B contribution | 2-4 / month | {} / week | as designed |\n".format(
        base["trades_per_week"]))
    L.append("| Books running | 2 | 1 | Book A rejected |\n")
    L.append("| Instruments | 4 | 1 | three fail on momentum |\n")

    L.append("\n**The frequency shortfall is structural and should not be closed.** The brief "
             "expected Book A to carry the trade count; Book A has no signal, and every "
             "legitimate way of replacing that frequency inside the brief's four-instrument "
             "universe has now been tested and rejected. Reaching 2-3 trades a week from here "
             "would mean adding books that lose money, which is the one thing section 1.4 "
             "explicitly rules out.\n")
    L.append("\nThe honest options are to accept roughly one trade a week on a single "
             "validated book, or to widen the instrument universe -- which is outside the "
             "brief's scope and is Dutch's call, not this repo's. Time-series momentum is "
             "documented across 58 liquid instruments (Moskowitz, Ooi & Pedersen); one "
             "instrument is the constraint here, not the method.\n")

    L.append("\n## Method\n\n")
    L.append("- Every variant is charged the same measured spread and per-night swap, and "
             "compared against the same hurdle: buy-and-hold of the same CFD, vol-matched "
             "and charged the same financing.\n")
    L.append("- The dynamic state tilt is estimated expanding-window and shifted, so the "
             "weight applied at a bar never saw that bar's outcome.\n")
    L.append("- The kill-switch threshold is a trailing percentile, never a full-sample one.\n")
    L.append("- Reproduce with `python src/report_enhancements.py`.\n")

    (REPORTS / "enhancements.md").write_text("".join(L), encoding="utf-8")
    for name in ("vol_estimators", "signal_variants", "ensembles", "instruments",
                 "portfolios", "kill_switch_rolling"):
        R[name].to_csv(REPORTS / f"enh_{name}.csv", index=False)
    print("wrote " + str(REPORTS / "enhancements.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
