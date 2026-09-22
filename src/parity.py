"""Build step 7 -- Python/MQL5 parity.

Reconciles the EA's per-bar state against the Python backtest, bar by bar, for
both sleeves. The brief calls this the classic backtest-to-live failure and
says it is worth more effort than it looks; it has already earned that here by
catching a hedging-account bug that blew the tester account up.

The EA dumps its state at each new H4 bar (see mql5/TSMOM_Blend_EA.mq5). A row
stamped time T holds the decision applied OVER bar T, computed from bars closed
at or before T-1 -- which is exactly Python's `pos.shift(1)`. That is the
alignment used below; getting it wrong by one bar is the single easiest way to
fake a passing parity test.

Run: python src/parity.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
import src.holdout as ho  # noqa: E402

REPORTS = REPO / "reports"
COMMON_FILES = Path(os.environ["APPDATA"]) / "MetaQuotes" / "Terminal" / "Common" / "Files"
EA_CSV = COMMON_FILES / "tsmom_parity_ea.csv"

# Exactly the constants compiled into the EA inputs.
SPEC = {
    "XAUUSD": dict(slow=308, fast=51, volwin=103, regimelb=2586, ppy=1584.1),
    "BTCUSD": dict(slow=251, fast=42, volwin=84, regimelb=2108, ppy=1508.3),
}
VOL_TARGET, MAX_LEV, REGIME_DECILE = 0.15, 3.0, 0.90


def python_state(symbol: str) -> pd.DataFrame:
    """Reproduce the EA's per-bar state from the Python implementation."""
    s = SPEC[symbol]
    df = pd.read_csv(ho.DEEP_DIR / f"{symbol}_H4.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
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
    flat = (rv > thr).fillna(False)
    pos = pos.where(~flat, 0.0)

    rv_ann = rv * np.sqrt(s["ppy"])
    scale = (VOL_TARGET / rv_ann).replace([np.inf, -np.inf], np.nan)
    scale = scale.clip(upper=MAX_LEV).fillna(0.0)
    pos = (pos * scale).clip(lower=0.0, upper=MAX_LEV)

    out = pd.DataFrame({"slow_sig": slow_sig, "fast_sig": fast_sig, "rv": rv,
                        "thr": thr, "regime_flat": flat.astype(int),
                        "vol_scale": scale, "pos_raw": pos})
    # The decision applied over bar T was computed from data closed at T-1.
    return out.shift(1)


def main() -> int:
    if not EA_CSV.exists():
        print(f"EA dump not found at {EA_CSV}. Run the Strategy Tester first.",
              file=sys.stderr)
        return 1
    ea = pd.read_csv(EA_CSV)
    ea["bar_time"] = pd.to_datetime(ea["bar_time"], format="%Y.%m.%d %H:%M", utc=True)

    fields = ["slow_sig", "fast_sig", "rv", "thr", "regime_flat", "vol_scale", "pos_raw"]
    tol = {"slow_sig": 0, "fast_sig": 0, "regime_flat": 0,
           "rv": 1e-9, "thr": 1e-9, "vol_scale": 1e-6, "pos_raw": 1e-6}

    rows, details, warm = [], {}, {}
    for sym in SPEC:
        e = ea[ea.symbol == sym].set_index("bar_time").sort_index()
        p = python_state(sym)
        idx = e.index.intersection(p.index)
        e, p = e.loc[idx], p.loc[idx]
        # Only compare bars where Python has a defined decision.
        ok = p["pos_raw"].notna()
        e, p = e[ok], p[ok]

        # WARM-UP. The regime filter takes the 90th percentile of the last
        # `regimelb` realised-vol windows. Python has the full history on disk;
        # inside the Strategy Tester the EA can only see bars back to the test
        # start, so early in the run it computes that percentile from a smaller
        # sample and gets a different threshold. That is a property of the test
        # harness, not a difference in logic -- but it is also exactly what a
        # freshly deployed EA with a cold history cache would do, so it is
        # measured and reported rather than quietly skipped.
        n_warm = SPEC[sym]["regimelb"] + SPEC[sym]["volwin"]
        warm_cut = e.index[min(n_warm, len(e) - 1)]
        warm[sym] = {"bars": int(min(n_warm, len(e))), "until": str(warm_cut)[:16]}
        e_w, p_w = e.loc[:warm_cut], p.loc[:warm_cut]
        e, p = e.loc[warm_cut:], p.loc[warm_cut:]

        for f in fields:
            d = (e_w[f].astype(float) - p_w[f].astype(float)).abs()
            d = d[np.isfinite(d)]
            rows.append({"symbol": sym, "phase": "warm-up", "field": f,
                         "bars": len(d), "mismatches": int((d > tol[f]).sum()),
                         "match_rate": round(1 - int((d > tol[f]).sum()) / max(len(d), 1), 6),
                         "max_abs_diff": float(d.max()) if len(d) else np.nan})

        for f in fields:
            d = (e[f].astype(float) - p[f].astype(float)).abs()
            d = d[np.isfinite(d)]
            n_bad = int((d > tol[f]).sum())
            rows.append({"symbol": sym, "phase": "steady state", "field": f,
                         "bars": len(d), "mismatches": n_bad,
                         "match_rate": round(1 - n_bad / max(len(d), 1), 6),
                         "max_abs_diff": float(d.max()) if len(d) else np.nan})
        # Trade-level agreement: do both sides change direction on the same bars?
        ea_tr = (np.sign(e["target_w"]).diff().fillna(0) != 0)
        py_w = p["pos_raw"].where(e["killed"] == 0, 0.0)
        py_tr = (np.sign(py_w).diff().fillna(0) != 0)
        details[sym] = {
            "ea_trades": int(ea_tr.sum()), "py_trades": int(py_tr.sum()),
            "same_bar_trades": int((ea_tr & py_tr).sum()),
            "ea_only": int((ea_tr & ~py_tr).sum()), "py_only": int((py_tr & ~ea_tr).sum()),
            "bars": len(e),
        }

    res = pd.DataFrame(rows)
    res.to_csv(REPORTS / "parity.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False))
    print("\nwarm-up spans:", warm)
    print()
    for k, v in details.items():
        print(k, v)

    steady = res[res.phase == "steady state"]
    bad = steady[steady.mismatches > 0]
    print("\nSTEADY-STATE PARITY:",
          "CLEAN -- every field matches bar for bar" if bad.empty
          else f"{len(bad)} field(s) mismatch")
    return 0 if bad.empty else 2


if __name__ == "__main__":
    raise SystemExit(main())
