"""How much of the strategy survives LOT QUANTISATION at the demo's equity?

The backtest holds a continuous weight. A real account holds whole lot steps.
On this demo that is not a rounding detail:

    XAUUSD  min lot 0.01 = 100 oz = ~$4,350 of notional
    at $10,000 equity and a 0.5 sleeve allocation, the smallest tradable
    gold position is a weight of 0.871

So any gold target weight below 0.871 floors to ZERO. Gold becomes close to
binary, and -- because weight is inversely proportional to volatility -- the
quantisation silently adds a "only trade when volatility is low enough" filter
that the strategy was never designed to have and was never validated with.

BTCUSD is far finer (min lot = ~$865 of notional, smallest weight 0.173).

This simulates the account as it will actually behave: equity-scaled lots,
floored to the lot step, minimum lot enforced, costs charged on the lots
actually traded, financing on the lots actually held, equity compounding. Run
before committing to a demo configuration, because the answer decides whether
the gold sleeve is tradable at this size at all.

Run: python src/demo_sim.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
import src.deploy_config as dc  # noqa: E402
import src.holdout as ho  # noqa: E402
import src.screen_universe as su  # noqa: E402
from common.financing import rollover_nights  # noqa: E402
from common.portfolio import summarize  # noqa: E402

SLEEVES = {
    # symbol: (contract_size, min_lot, lot_step)  -- read from symbol_info
    "XAUUSD": (100.0, 0.01, 0.01),
    "BTCUSD": (1.0, 0.01, 0.01),
}
ALLOC = 0.5
START_EQUITY = 10_000.0


def weights(sym: str, costs: dict):
    df = pd.read_csv(ho.DEEP_DIR / f"{sym}_H4.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    bpd = bb.bars_per_day(df)
    r = bb.run(df, costs, slow_bars=max(2, int(round(su.SLOW_D * bpd))),
               fast_bars=max(1, int(round(su.FAST_D * bpd))),
               mode="blend5050", direction=su.DIRECTION,
               vol_target=dc.DEPLOY_VOL_TARGET, max_leverage=dc.DEPLOY_MAX_LEVERAGE)
    return df, r["weights"]


def simulate(start_equity: float, quantise: bool, costs_map: dict,
             sleeves=None, mode: str = "floor", start=None, end=None) -> dict:
    """Bar-by-bar account simulation on the union clock.

    `mode` decides what happens when the target position is smaller than the
    broker's minimum lot:

      "floor"    hold nothing. This is what the EA actually does, and it is the
                 safe behaviour: a position you cannot size is a position you
                 should not take.
      "forcemin" take the minimum lot anyway. Not the deployed behaviour -- it
                 is here to answer "what if I trade a small account regardless",
                 by measuring the leverage and drawdown it produces rather than
                 asserting they would be bad.

    `start`/`end` restrict the simulation to one price regime. That matters:
    run from 2011 the minimums look affordable because gold was $1,400 and BTC
    was $5, which tells you nothing about what an account can do today.
    """
    sleeves = sleeves or list(SLEEVES)
    px, w, nights = {}, {}, {}
    for s in sleeves:
        df, ws = weights(s, costs_map[s])
        if start or end:
            df, ws = df.loc[start:end], ws.loc[start:end]
        px[s] = df["close"].astype(float)
        w[s] = ws
        nights[s] = rollover_nights(df.index, costs_map[s]["triple_weekday"])

    idx = None
    for s in sleeves:
        idx = px[s].index if idx is None else idx.union(px[s].index)
    idx = idx.sort_values()
    start = max(px[s].index.min() for s in sleeves)
    idx = idx[idx >= start]

    P = {s: px[s].reindex(idx).ffill() for s in sleeves}
    W = {s: w[s].reindex(idx).ffill().fillna(0.0) for s in sleeves}
    N = {s: nights[s].reindex(idx).fillna(0.0) for s in sleeves}

    equity = start_equity
    lots = {s: 0.0 for s in sleeves}
    eq_curve, flat_bars, traded_bars = [], {s: 0 for s in sleeves}, 0
    leverage, ruined = [], False

    for i in range(1, len(idx)):
        pnl = 0.0
        for s in sleeves:
            cs, minlot, step = SLEEVES[s]
            p_now, p_prev = P[s].iloc[i], P[s].iloc[i - 1]
            if lots[s] != 0.0 and np.isfinite(p_now) and np.isfinite(p_prev):
                pnl += lots[s] * cs * (p_now - p_prev)
                # financing on held notional
                rate = costs_map[s]["swap_long_annual"]
                pnl += lots[s] * cs * p_now * rate * N[s].iloc[i] / 365.0
        equity += pnl
        if equity <= 0:
            ruined = True
            eq_curve.append(0.0)
            break

        gross = 0.0
        for s in sleeves:
            cs, minlot, step = SLEEVES[s]
            p_now = P[s].iloc[i]
            if not np.isfinite(p_now) or p_now <= 0:
                continue
            target_notional = W[s].iloc[i] * ALLOC * equity
            raw = target_notional / (p_now * cs)
            if quantise:
                tgt = np.floor(raw / step) * step
                if tgt < minlot:
                    # The whole question in one line: refuse the trade, or take
                    # a position larger than the strategy asked for.
                    tgt = minlot if (mode == "forcemin" and W[s].iloc[i] > 0) else 0.0
            else:
                tgt = raw
            if tgt != lots[s]:
                d = abs(tgt - lots[s])
                equity -= d * cs * (costs_map[s]["typical_spread_price"] / 2.0)
                lots[s] = tgt
                traded_bars += 1
            if tgt == 0.0 and W[s].iloc[i] > 0:
                flat_bars[s] += 1
            gross += lots[s] * cs * p_now
        leverage.append(gross / equity if equity > 0 else np.nan)
        eq_curve.append(equity)

    eq = pd.Series(eq_curve, index=idx[1:1 + len(eq_curve)])
    ret = eq.pct_change().fillna(0.0)
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    s = summarize(ret, periods_per_year=int(round(ppy))) or {}
    years = (idx[-1] - idx[0]).days / 365.25
    lev = np.array([x for x in leverage if np.isfinite(x)])
    return {
        "quantised": quantise, "mode": mode, "start_equity": start_equity,
        "sleeves": "+".join(sleeves),
        "final_equity": round(float(eq.iloc[-1]), 2),
        "cagr": round(s.get("cagr", 0), 4), "sharpe": round(s.get("sharpe", 0), 3),
        "max_dd": round(s.get("max_drawdown", 0), 3),
        "ruined": ruined,
        "avg_leverage": round(float(lev.mean()), 2) if len(lev) else np.nan,
        "peak_leverage": round(float(lev.max()), 2) if len(lev) else np.nan,
        "lost_bars_gold": flat_bars.get("XAUUSD", 0),
        "lost_bars_btc": flat_bars.get("BTCUSD", 0),
        "trades_per_week": round(traded_bars / years / 52, 2),
    }


def main() -> int:
    costs = pd.read_csv(ho.DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}

    rows = []
    for eq in (10_000.0, 50_000.0, 100_000.0):
        rows.append(simulate(eq, True, cmap))
    rows.append(simulate(10_000.0, False, cmap))          # continuous reference
    rows.append(simulate(10_000.0, True, cmap, ["BTCUSD"]))
    rows.append(simulate(10_000.0, True, cmap, ["XAUUSD"]))

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(res.to_string(index=False))
    res.to_csv(ho.REPORTS / "demo_sim.csv", index=False)

    q10 = res[(res.quantised) & (res.start_equity == 10_000) &
              (res.sleeves == "XAUUSD+BTCUSD")].iloc[0]
    cont = res[~res.quantised].iloc[0]
    print(f"\nlot quantisation at $10k costs "
          f"{cont['sharpe'] - q10['sharpe']:+.3f} Sharpe "
          f"({cont['sharpe']} -> {q10['sharpe']})")
    print(f"gold bars where the signal wanted a position but the lot floor "
          f"forced flat: {q10['lost_bars_gold']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
