"""Step 3 -- build data/costs.csv: contract specs, swaps, and session-split
spread estimates measured from tick history.

READ-ONLY (brief section 2): symbol_info, symbol_info_tick, copy_ticks_range.
No order functions of any kind.

Three things here are deliberate and worth reading before changing them.

1. The spread does NOT come from `symbol_info().spread`.
   The brief forbids it (section 3.2) and it is right to: that field is the
   spread at one instant. Read it at 03:00 and US100 looks wide; read it
   mid-New-York and it looks tight. Neither number is what a strategy pays on
   average. So spreads are measured from the actual tick stream, split by
   session, reported as a median and a 95th percentile.

2. Ticks are sampled in weekly chunks and subsampled, not loaded whole.
   XAUUSD alone produces ~2.5M ticks a week; the full window across four
   symbols would be tens of millions of rows and gigabytes of RAM. Every
   SUBSAMPLE-th tick is retained instead. A percentile taken from a systematic
   1-in-5 sample of two million observations is accurate far beyond the
   precision this screen needs -- the sampling error is orders of magnitude
   smaller than the demo-vs-live difference already acknowledged.

3. Swap is converted to PRICE UNITS PER UNIT HELD PER NIGHT.
   That is the form the cost screen needs, because the residual it compares
   against is in price units too. The two swap conventions on this account
   must not be conflated, and the arithmetic below is inherited from
   common/costs.py where it was derived and sanity-checked:
     mode 1 (SYMBOL_SWAP_MODE_POINTS, the metals) -- money per lot per night
         is swap * point * contract_size, so per single unit it is simply
         swap * point.
     mode 5 (SYMBOL_SWAP_MODE_INTEREST_CURRENT, the indices) -- the value IS
         an annual percent already, so per unit per night it is
         price * swap/100 / 365.
   Reading a mode-5 value as points (or vice versa) changes financing by
   orders of magnitude and would silently decide the screen's verdict.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DATA = REPO / "data"
REPORTS = REPO / "reports"

SYMBOLS = ["US100", "US500", "XAUUSD", "XAGUSD"]

# Tick sampling window. 30 calendar days is a compromise: long enough that a
# single quiet or stressed week cannot dominate the median, short enough to
# stay inside the broker's tick retention and this machine's memory. It is a
# RECENT-CONDITIONS estimate by design -- these are the costs a strategy
# starting today would pay. The long-history cross-check below exists because
# that recency is also its weakness.
TICK_WINDOW_DAYS = 30
CHUNK_DAYS = 7
SUBSAMPLE = 5

# Trading sessions in UTC. Safe to state directly: the server clock was
# measured at offset 0.0 h from UTC (see data/broker_config.json), so no
# conversion is applied. If that offset ever changes, these bounds must move
# with it -- they are wall-clock session bounds, not server-local ones.
SESSIONS = {
    "Asia": (23, 7),       # wraps midnight
    "London": (7, 13),
    "NewYork": (13, 21),
    "Rollover": (21, 23),  # daily break / financing stamp; thin and wide
}

SWAP_MODE_POINTS = 1
SWAP_MODE_INTEREST_CURRENT = 5

# Confirmed by the user 2026-09-21: Deriv prices these CFDs spread-only and
# charges no separate commission. Recorded rather than assumed -- the brief
# (section 3.2) specifically says to ask rather than default to zero.
COMMISSION_PER_SIDE = 0.0
COMMISSION_SOURCE = "zero, spread-only; confirmed by Dutch 2026-09-21"


def session_of(hours: np.ndarray) -> np.ndarray:
    out = np.full(hours.shape, "Unknown", dtype=object)
    for name, (lo, hi) in SESSIONS.items():
        mask = (hours >= lo) & (hours < hi) if lo < hi else ((hours >= lo) | (hours < hi))
        out[mask] = name
    return out


def sample_spreads(broker_symbol: str) -> pd.DataFrame:
    """Return a subsampled frame of (session, spread_price_units) from ticks."""
    end = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    start = end - dt.timedelta(days=TICK_WINDOW_DAYS)
    parts = []
    cursor = start
    while cursor < end:
        stop = min(cursor + dt.timedelta(days=CHUNK_DAYS), end)
        ticks = mt5.copy_ticks_range(broker_symbol, cursor, stop, mt5.COPY_TICKS_INFO)
        cursor = stop
        if ticks is None or len(ticks) == 0:
            continue
        ticks = ticks[::SUBSAMPLE]
        df = pd.DataFrame(ticks)
        # A tick with a zero bid or ask is a placeholder, not a quote. Keeping
        # them would drag the median toward a spread nobody could ever trade.
        df = df[(df["bid"] > 0) & (df["ask"] > 0)]
        if df.empty:
            continue
        spread = (df["ask"] - df["bid"]).to_numpy(dtype=float)
        hours = pd.to_datetime(df["time"], unit="s", utc=True).dt.hour.to_numpy()
        parts.append(pd.DataFrame({"session": session_of(hours), "spread": spread}))
    if not parts:
        return pd.DataFrame(columns=["session", "spread"])
    return pd.concat(parts, ignore_index=True)


def bar_spread_crosscheck(canonical: str) -> dict:
    """Median / p95 / p99 of the broker's own recorded per-bar spread, over the
    FULL history on disk rather than the recent tick window.

    This is the honesty check on the tick sample. The 30-day window says what
    costs look like now; this says what they looked like across every regime
    the broker has data for. If the two disagree badly, the recent window is
    flattering and the screen's verdict should not be trusted at face value.
    """
    path = DATA / f"{canonical}_H1.csv"
    if not path.exists():
        return {}
    s = pd.read_csv(path, usecols=["spread"])["spread"].dropna()
    s = s[s > 0]
    if s.empty:
        return {}
    return {
        "bar_spread_median": float(s.median()),
        "bar_spread_p95": float(s.quantile(0.95)),
        "bar_spread_p99": float(s.quantile(0.99)),
        "bar_spread_n_bars": int(len(s)),
    }


def swap_per_unit_per_night(info, price: float, swap_value: float) -> float:
    """Swap in PRICE UNITS, per one unit of the instrument, per night. Signed:
    negative is a cost to the holder."""
    if info.swap_mode == SWAP_MODE_POINTS:
        return swap_value * info.point
    if info.swap_mode == SWAP_MODE_INTEREST_CURRENT:
        return price * (swap_value / 100.0) / 365.0
    raise ValueError(
        f"{info.name}: unhandled swap_mode {info.swap_mode}. Refusing to guess -- "
        "an incorrect swap convention changes financing by orders of magnitude "
        "and would silently decide the cost screen's verdict."
    )


def main() -> int:
    if not mt5.initialize():
        print(f"FATAL: MT5 initialize failed: {mt5.last_error()}", file=sys.stderr)
        return 1
    try:
        cfg = json.loads((DATA / "broker_config.json").read_text(encoding="utf-8"))
        smap = cfg["symbols"]
        read_utc = dt.datetime.now(dt.UTC)

        rows, session_rows = [], []
        for canon in SYMBOLS:
            broker = smap[canon]["broker_symbol"]
            info = mt5.symbol_info(broker)
            if info is None:
                print(f"FATAL: {canon} ({broker}) vanished from the account", file=sys.stderr)
                return 2
            if not info.visible:
                mt5.symbol_select(broker, True)
                info = mt5.symbol_info(broker)
            tick = mt5.symbol_info_tick(broker)
            price = (tick.bid + tick.ask) / 2.0 if tick and tick.bid else info.bid

            print(f"sampling ticks for {canon} ({broker}) ...", flush=True)
            sp = sample_spreads(broker)
            if sp.empty:
                print(f"WARN: no ticks for {canon}", file=sys.stderr)

            for sess in list(SESSIONS) + ["ALL"]:
                sub = sp if sess == "ALL" else sp[sp.session == sess]
                if sub.empty:
                    continue
                session_rows.append({
                    "symbol": canon, "session": sess, "n_ticks_sampled": len(sub),
                    "spread_median_price": round(float(sub.spread.median()), info.digits + 2),
                    "spread_p95_price": round(float(sub.spread.quantile(0.95)), info.digits + 2),
                    "spread_median_pts": round(float(sub.spread.median()) / info.point, 2),
                    "spread_p95_pts": round(float(sub.spread.quantile(0.95)) / info.point, 2),
                })

            all_sp = sp.spread if not sp.empty else pd.Series([np.nan])
            row = {
                "symbol": canon,
                "broker_symbol": broker,
                "read_utc": read_utc.isoformat(timespec="seconds"),
                "account": f"{cfg['account']['login']}@{cfg['account']['server']}",
                "account_type": cfg["account"]["trade_mode_label"],
                "provisional": cfg["provisional"],
                "typical_spread_pts": round(float(all_sp.median()) / info.point, 2),
                "worst_spread_pts": round(float(all_sp.quantile(0.95)) / info.point, 2),
                "typical_spread_price": round(float(all_sp.median()), info.digits + 2),
                "worst_spread_price": round(float(all_sp.quantile(0.95)), info.digits + 2),
                "spread_now_pts": info.spread,
                "commission_per_side": COMMISSION_PER_SIDE,
                "commission_source": COMMISSION_SOURCE,
                "swap_long_raw": info.swap_long,
                "swap_short_raw": info.swap_short,
                "swap_mode": info.swap_mode,
                "swap_mode_label": {1: "POINTS", 5: "INTEREST_CURRENT"}.get(info.swap_mode),
                "swap_3x_weekday": info.swap_rollover3days,
                "swap_long_price_per_unit_night": swap_per_unit_per_night(info, price, info.swap_long),
                "swap_short_price_per_unit_night": swap_per_unit_per_night(info, price, info.swap_short),
                "min_lot": info.volume_min,
                "lot_step": info.volume_step,
                "max_lot": info.volume_max,
                "contract_size": info.trade_contract_size,
                "point": info.point,
                "digits": info.digits,
                "tick_value": info.trade_tick_value,
                "tick_size": info.trade_tick_size,
                "price_at_read": round(price, info.digits),
            }
            # annualised financing, purely as a human sanity check on the above
            for side in ("long", "short"):
                per_night = row[f"swap_{side}_price_per_unit_night"]
                row[f"swap_{side}_annual_pct"] = round(100 * per_night * 365 / price, 3)
            row.update(bar_spread_crosscheck(canon))
            rows.append(row)

        costs = pd.DataFrame(rows)
        costs.to_csv(DATA / "costs.csv", index=False)
        sess_df = pd.DataFrame(session_rows)
        sess_df.to_csv(DATA / "spread_by_session.csv", index=False)
        write_report(costs, sess_df, cfg)

        print("\n" + costs[["symbol", "typical_spread_pts", "worst_spread_pts",
                            "swap_long_annual_pct", "swap_short_annual_pct"]].to_string(index=False))
        return 0
    finally:
        mt5.shutdown()


def write_report(costs: pd.DataFrame, sess: pd.DataFrame, cfg: dict) -> None:
    L = []
    L.append("# Cost table -- contract specs, swaps and measured spreads\n\n")
    L.append("Read {} UTC from `{}` ({}).\n\n".format(
        costs["read_utc"].iloc[0], costs["account"].iloc[0], costs["account_type"].iloc[0]))
    L.append("> **Provisional.** " + cfg["provisional_note"] + "\n")

    L.append("\n## The table (brief section 3.2)\n\n")
    L.append("| Instrument | Typical spread (pts) | Worst-case spread (pts) | Commission | "
             "Swap long | Swap short | Min lot | Lot step | Point value |\n")
    L.append("|---|---|---|---|---|---|---|---|---|\n")
    for _, r in costs.iterrows():
        L.append("| {} | {} | {} | {} | {} ({}%/yr) | {} ({}%/yr) | {} | {} | {} |\n".format(
            r["symbol"], r["typical_spread_pts"], r["worst_spread_pts"],
            "0.0", r["swap_long_raw"], r["swap_long_annual_pct"],
            r["swap_short_raw"], r["swap_short_annual_pct"],
            r["min_lot"], r["lot_step"], r["point"]))
    L.append("\nCommission: **{}**.\n".format(COMMISSION_SOURCE))
    L.append("\n`Point value` is the price increment of one point. Note the two swap "
             "conventions in play -- the raw swap numbers are NOT comparable across rows:\n\n")
    for _, r in costs.iterrows():
        L.append("- **{}**: `swap_mode={}` ({}), triple-swap on weekday {} -- "
                 "{} price units per unit held per night when long.\n".format(
                     r["symbol"], r["swap_mode"], r["swap_mode_label"], r["swap_3x_weekday"],
                     round(r["swap_long_price_per_unit_night"], 6)))

    L.append("\n## Spread by session\n\n")
    L.append("Measured from tick history, not from `symbol_info().spread` (which is a single "
             "instant and would misstate the cost depending on when it happened to be read). "
             "Sessions are UTC; the server clock sits at offset 0.0 h so no conversion applies.\n\n")
    L.append("| Symbol | Session | Median (pts) | p95 (pts) | Median (price) | p95 (price) | Ticks sampled |\n")
    L.append("|---|---|---|---|---|---|---|\n")
    for _, r in sess.iterrows():
        L.append("| {} | {} | {} | {} | {} | {} | {:,} |\n".format(
            r["symbol"], r["session"], r["spread_median_pts"], r["spread_p95_pts"],
            r["spread_median_price"], r["spread_p95_price"], r["n_ticks_sampled"]))

    L.append("\n## Long-history cross-check\n\n")
    L.append("The session table above measures the last {} days. The broker also records a "
             "spread on every H1 bar, which reaches back across the full history on disk. If "
             "the recent window were unusually calm, these columns would be visibly wider.\n\n"
             .format(TICK_WINDOW_DAYS))
    L.append("| Symbol | Tick median (price) | Bar median (price) | Bar p95 | Bar p99 | H1 bars |\n")
    L.append("|---|---|---|---|---|---|\n")
    for _, r in costs.iterrows():
        L.append("| {} | {} | {} | {} | {} | {:,} |\n".format(
            r["symbol"], r["typical_spread_price"],
            round(r.get("bar_spread_median", float("nan")), 5),
            round(r.get("bar_spread_p95", float("nan")), 5),
            round(r.get("bar_spread_p99", float("nan")), 5),
            int(r.get("bar_spread_n_bars", 0))))

    L.append("\n## Method\n\n")
    L.append("- Tick source: `copy_ticks_range(..., COPY_TICKS_INFO)` over the last {} days, "
             "pulled in {}-day chunks, retaining every {}th tick to bound memory. Ticks with a "
             "zero bid or ask are discarded as placeholders.\n".format(
                 TICK_WINDOW_DAYS, CHUNK_DAYS, SUBSAMPLE))
    L.append("- Spread per tick = `ask - bid`, in price units; the points column divides by "
             "the symbol's own `point`.\n")
    L.append("- Swap converted to price units per unit per night: mode 1 -> `swap * point`; "
             "mode 5 -> `price * swap/100 / 365`.\n")
    L.append("- Commission is recorded from the account owner, not defaulted (brief 3.2).\n")

    (REPORTS / "cost_table.md").write_text("".join(L), encoding="utf-8")
    print("wrote " + str(REPORTS / "cost_table.md"))


if __name__ == "__main__":
    raise SystemExit(main())
