"""Watch the Book B demo and raise findings -- build step 9.

`demo_monitor.py` shows the account. This checks it. Every run:

  1. HEALTH     terminal running; EA still logging decisions.
  2. PARITY     the EA's latest decision per sleeve, recomputed independently in
                Python from bars pulled fresh from the terminal. Tester parity
                proved the logic on history; this proves it on the bars the demo
                is actually trading, one decision at a time.
  3. EXECUTION  lots held equal the EA's own target.
  4. RISK       drawdown from the equity peak since deployment, against the
                -9.0% backtested maximum at the 10% vol target.
  5. EVENTS     signal flips, regime-flat and kill-switch changes, fills.
  6. WEEKEND    the EA runs on the XAUUSD chart's ticks, so while gold is shut
                BTC is not rebalanced. When that leaves BTC's held position away
                from what the signal now wants, it is reported with the size of
                the gap (see reports/demo_journal.md, 2026-09-23).

Lines starting "FINDING" are the ones worth a human's attention. Each run is
appended to reports/demo_journal.md; state between runs lives in
reports/demo_watch_state.json.

READ-ONLY against MT5: account, positions, history and rates only.

Run: python src/watch_book_b.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.parity as par  # noqa: E402
from src.demo_monitor import MAGIC, TERMINAL  # noqa: E402

REPORTS = REPO / "reports"
STATE = REPORTS / "demo_watch_state.json"
JOURNAL = REPORTS / "demo_journal.md"
DEPLOYED = dt.datetime(2026, 9, 22, tzinfo=dt.UTC)

BACKTEST_MAX_DD = -0.090      # reports/drawdown.md, 10% vol target
WARN_DD = BACKTEST_MAX_DD / 2
STALE_HOURS = 5.0             # one H4 bar plus slack
# The log prints scale to 3 dp and w to 4 dp; allow for the rounding.
TOL = {"scale": 6e-4, "w": 6e-5}

DECISION = re.compile(
    r"(?P<bar>\d{4}\.\d\d\.\d\d \d\d:\d\d) (?P<tag>\S+) \| slow (?P<slow>-?\d+) "
    r"fast (?P<fast>-?\d+) \| flat (?P<flat>[YN]) \| scale (?P<scale>[\d.]+) \| "
    r"w (?P<w>-?[\d.]+) \| killed (?P<killed>[YN]) \| want (?P<want>-?[\d.]+) lots "
    r"-> target (?P<target>[\d.]+) \(have (?P<have>[\d.]+), min (?P<min>[\d.]+)\)")


def ea_decisions() -> pd.DataFrame:
    """Every decision line the EA has logged since deployment."""
    rows = []
    for f in sorted((TERMINAL / "MQL5" / "Logs").glob("*.log")):
        day = dt.datetime.strptime(f.stem, "%Y%m%d").date()
        if day < DEPLOYED.date():
            continue
        for line in f.read_text(encoding="utf-16", errors="ignore").splitlines():
            if "TSMOM_Blend_EA" not in line:
                continue
            parts = line.split("\t")
            m = DECISION.search(parts[-1])
            if not m:
                continue
            d = m.groupdict()
            sig, _, ex = d["tag"].partition("->")
            rows.append({
                "logged": dt.datetime.combine(
                    day, dt.datetime.strptime(parts[2][:8], "%H:%M:%S").time()),
                "bar": pd.Timestamp(dt.datetime.strptime(d["bar"], "%Y.%m.%d %H:%M"), tz="UTC"),
                "symbol": sig, "exec": ex or sig,
                "slow": int(d["slow"]), "fast": int(d["fast"]),
                "flat": d["flat"] == "Y", "scale": float(d["scale"]), "w": float(d["w"]),
                "killed": d["killed"] == "Y", "want": float(d["want"]),
                "target": float(d["target"]), "have": float(d["have"]),
            })
    return pd.DataFrame(rows)


def live_state(mt5, symbol: str) -> pd.DataFrame:
    """Python's decision state for `symbol`, from bars pulled now."""
    need = par.SPEC[symbol]["regimelb"] + par.SPEC[symbol]["volwin"] + 600
    r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, need)
    df = pd.DataFrame(r)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return par.python_state(symbol, df.set_index("timestamp"))


def terminal_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
                         capture_output=True, text=True).stdout
    return "terminal64.exe" in out


def main() -> int:
    import MetaTrader5 as mt5

    now = dt.datetime.now()
    findings, notes = [], []
    state = json.loads(STATE.read_text()) if STATE.exists() else {}

    # 1. HEALTH ---------------------------------------------------------------
    if not terminal_running():
        findings.append("TERMINAL DOWN -- terminal64.exe is not running; the EA is not trading.")
    dec = ea_decisions()
    if dec.empty:
        findings.append("NO EA DECISIONS in the logs since deployment.")
    else:
        age = (now - dec["logged"].max()).total_seconds() / 3600
        # Friday 22:00 to Sunday 23:59 local, gold is shut and silence is expected.
        weekend = now.weekday() == 5 or (now.weekday() == 4 and now.hour >= 22) or now.weekday() == 6
        if age > STALE_HOURS and not weekend:
            findings.append(f"EA SILENT for {age:.1f}h on a trading day -- "
                            f"last decision logged {dec['logged'].max():%a %H:%M}.")

    if not mt5.initialize(timeout=60000):
        findings.append(f"MT5 NOT REACHABLE: {mt5.last_error()}")
        return report(now, findings, notes, state, None)
    try:
        acct = mt5.account_info()
        if acct.trade_mode != 0:
            findings.append("NOT A DEMO ACCOUNT -- the EA should be refusing to trade.")

        # 4. RISK ------------------------------------------------------------
        deals = [d for d in (mt5.history_deals_get(DEPLOYED, dt.datetime.now(dt.UTC)
                                                   + dt.timedelta(days=1)) or [])
                 if d.magic == MAGIC]
        realised = sum(d.profit + d.commission + d.swap + d.fee for d in deals)
        start = state.get("start_equity", round(acct.balance - realised, 2))
        peak = max(state.get("peak_equity", start), acct.equity)
        dd = acct.equity / peak - 1
        if dd <= BACKTEST_MAX_DD:
            findings.append(f"DRAWDOWN {dd:.2%} is beyond the backtest's worst "
                            f"({BACKTEST_MAX_DD:.1%}). Stop and review.")
        elif dd <= WARN_DD:
            findings.append(f"DRAWDOWN {dd:.2%} -- past half the backtest maximum.")

        new_deals = [d for d in deals if d.ticket > state.get("last_deal", 0)]
        for d in new_deals:
            notes.append(f"fill: {dt.datetime.fromtimestamp(d.time, dt.UTC):%a %d %H:%M} "
                         f"{d.symbol} {'buy' if d.type == 0 else 'sell'} {d.volume} "
                         f"@ {d.price:,.2f}  P/L {d.profit + d.commission + d.swap + d.fee:+.2f}")

        # 2/3/6. PARITY, EXECUTION, WEEKEND -------------------------------------
        held = {}
        for p in (mt5.positions_get() or []):
            if p.magic == MAGIC:
                held[p.symbol] = held.get(p.symbol, 0.0) + (p.volume if p.type == 0 else -p.volume)

        sleeves = {}
        for sym in par.SPEC:
            py = live_state(mt5, sym)
            last = dec[dec.symbol == sym].sort_values("logged")
            if last.empty:
                findings.append(f"{sym}: no decision logged yet.")
                continue
            ea = last.iloc[-1]
            ex = ea["exec"]
            sleeves[sym] = {"bar": str(ea["bar"])[:16], "slow": int(ea["slow"]),
                            "fast": int(ea["fast"]), "flat": bool(ea["flat"]),
                            "killed": bool(ea["killed"]), "w": float(ea["w"]),
                            "held": held.get(ex, 0.0)}

            if ea["bar"] not in py.index:
                findings.append(f"{sym}: EA bar {ea['bar']:%m-%d %H:%M} not in the "
                                f"terminal's history -- cannot verify.")
            else:
                p = py.loc[ea["bar"]]
                bad = []
                if int(p["slow_sig"]) != ea["slow"]: bad.append(f"slow {ea['slow']} vs {int(p['slow_sig'])}")
                if int(p["fast_sig"]) != ea["fast"]: bad.append(f"fast {ea['fast']} vs {int(p['fast_sig'])}")
                if bool(p["regime_flat"]) != ea["flat"]: bad.append(f"flat {ea['flat']} vs {bool(p['regime_flat'])}")
                if abs(p["vol_scale"] - ea["scale"]) > TOL["scale"]:
                    bad.append(f"scale {ea['scale']:.3f} vs {p['vol_scale']:.4f}")
                if not ea["killed"] and abs(p["pos_raw"] - ea["w"]) > TOL["w"]:
                    bad.append(f"w {ea['w']:.4f} vs {p['pos_raw']:.5f}")
                if bad:
                    findings.append(f"PARITY {sym} @ {ea['bar']:%m-%d %H:%M}: EA vs Python -- " + "; ".join(bad))
                else:
                    notes.append(f"parity {sym} @ {ea['bar']:%m-%d %H:%M}: EA == Python")

            if abs(held.get(ex, 0.0) - ea["target"]) > 1e-9:
                findings.append(f"EXECUTION {ex}: holding {held.get(ex, 0.0):.2f} lots, "
                                f"EA's last target was {ea['target']:.2f}.")

            # Events against the previous run.
            prev = state.get("sleeves", {}).get(sym)
            if prev:
                for k, label in (("slow", "slow signal"), ("fast", "fast signal")):
                    if prev[k] != sleeves[sym][k]:
                        notes.append(f"EVENT {sym}: {label} {prev[k]:+d} -> {sleeves[sym][k]:+d}")
                if prev["flat"] != sleeves[sym]["flat"]:
                    findings.append(f"{sym}: volatility-regime filter "
                                    f"{'ON (forced flat)' if sleeves[sym]['flat'] else 'OFF'}.")
                if prev["killed"] != sleeves[sym]["killed"]:
                    findings.append(f"KILL SWITCH {'FIRED' if sleeves[sym]['killed'] else 'released'}.")
                if (prev["w"] > 0) != (sleeves[sym]["w"] > 0):
                    notes.append(f"EVENT {sym}: {'entered' if sleeves[sym]['w'] > 0 else 'exited'} "
                                 f"(w {prev['w']:.3f} -> {sleeves[sym]['w']:.3f})")

            # Weekend gap: the latest closed-bar decision vs what the EA last did.
            latest = py.dropna(subset=["pos_raw"]).iloc[-1]
            if py.index[-1] > ea["bar"]:
                gap = latest["pos_raw"] - ea["w"]
                msg = (f"{sym} UNMANAGED since {ea['bar']:%a %H:%M}: signal now wants "
                       f"w {latest['pos_raw']:.3f}, EA last set {ea['w']:.3f}")
                if (ea["w"] > 0) != (latest["pos_raw"] > 0):
                    findings.append(msg + " -- the signal has flipped and the position has not.")
                elif abs(gap) > 0.10:
                    findings.append(msg + f" (gap {gap:+.3f}).")
    finally:
        mt5.shutdown()

    state.update({"start_equity": start, "peak_equity": round(peak, 2),
                  "last_deal": max([d.ticket for d in deals], default=state.get("last_deal", 0)),
                  "sleeves": sleeves or state.get("sleeves", {}),
                  "last_run": now.isoformat(timespec="minutes")})
    holding = ", ".join(f"{k} {v:.2f}" for k, v in held.items()) or "flat"
    acct_line = (f"equity {acct.equity:,.2f} (start {start:,.2f}, "
                 f"{acct.equity / start - 1:+.2%}) | peak {peak:,.2f} | DD {dd:.2%} | "
                 f"held: {holding}")
    return report(now, findings, notes, state, acct_line)


def report(now, findings, notes, state, acct_line) -> int:
    STATE.write_text(json.dumps(state, indent=1))
    out = [f"### {now:%a %Y-%m-%d %H:%M}"]
    if acct_line:
        out.append(acct_line)
    out += [f"- **FINDING** {f}" for f in findings]
    out += [f"- {n}" for n in notes]
    if not findings:
        out.append("- no findings")
    text = "\n".join(out)
    print(text.replace("**", ""))
    if not JOURNAL.exists():
        JOURNAL.write_text("# Book B demo journal\n\nOne entry per `src/watch_book_b.py` run. "
                           "FINDING lines are the ones that need attention.\n", encoding="utf-8")
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write("\n" + text + "\n")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
