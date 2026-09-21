# Quant Two-Book Project — Full Handoff

Carry this into Claude Code. It contains the reasoning, the design decisions and the reasons behind them, the literature, and the build spec. Read section 1 before writing any code — most implementation mistakes on this project come from forgetting *why* a rule is there.

**Instruments:** US100, US500, XAUUSD, XAGUSD
**Confirmed:** US Tech 100 = US100 (same instrument, one ticker)
**Platform:** MT5 execution via MQL5 EA. Research in Python.
**Status:** Pre-data. Nothing here is validated.

---

## START HERE — current task

We are on **build steps 1-2 only** (section 8). In this session:

1. Set up a Python environment and project structure: `data/`, `src/`, `notebooks/`, `reports/`, `mql5/`
2. Pull price history per section 3.1 via the `MetaTrader5` package. Report how much history actually arrived.
3. Build `data/costs.csv` per section 3.2, including session-split spread estimates from tick history
4. Run the section 3.3 cost screen for US100/US500 and XAUUSD/XAGUSD, **at both H1 and H4 bar horizons** (see section 1.4)
5. Write `reports/cost_screen.md` with pass/fail per pair per horizon against the kill rule and half-life rule, plus the expected trades per week from the half-life

Then **STOP**. No strategy, backtest or EA code. Do not relax any threshold. Read-only — see section 2. Ask Dutch before anything outside this scope.

When a later phase begins, Dutch will update this block.

---

## 1. Why this design

### 1.1 Strategy selection

Four candidates were considered: statistical arbitrage, mean reversion, realised volatility, momentum.

- **Momentum** fits XAUUSD. Gold trends on macro and real-rate flows rather than reverting. Strongest research base of the four and the only one whose academic evidence transfers cleanly to a small, liquid instrument set.
- **Statistical arbitrage** has the strongest institutional track record but the weakest fit here. It needs cross-sectional breadth; this book has at most two genuine spreads. Included deliberately, with a high bar to clear.
- **Mean reversion** is subsumed into the stat arb book — the spread residual *is* the mean-reverting series.
- **Realised volatility** is not a standalone strategy on CFDs (no tradeable variance). It is infrastructure: position sizing and regime gating.

### 1.2 Structural decisions and their reasons

**US100/US30 was dropped.** It shares a leg with US100/US500 and is driven by the same thing — tech versus the rest of the market. Residuals would be ~80-90% correlated. Running both is one position in a trenchcoat. Keep it only as a substitute if A1's spreads are bad at the broker.

**No trend filter on the spread itself.** A trend filter on a mean-reverting series blocks exactly the dislocations that are the best entries. Gate on *leg* conditions instead. This is the single easiest mistake to make when "apply trend and regime filters to both books" is read literally.

**One kill switch, not two.** Both books fail on the same event: a vol spike breaks cointegration and whipsaws trend simultaneously. Scaling each book separately leaves the portfolio correlated exactly when it costs money.

**US100 appears in both books** and can be long in one, short in the other. Decide gross vs net before writing execution. Recommended: net.

### 1.3 What the recent literature changed (final research check)

**Momentum's edge on a single instrument is thinner than the headline papers suggest.** Kim, Tse & Wald (2016) found the large TSMOM alphas are mostly driven by volatility scaling — unscaled momentum performs about like buy-and-hold. Huang, Li, Wang & Zhou (2020, JFE) found little asset-by-asset evidence of TSMOM, in- or out-of-sample. Consequence: Book B must be benchmarked against *vol-scaled buy-and-hold* of the same instrument, not against zero. If it can't beat that, the signal is adding nothing (see section 7, item 6).

**Blend slow and fast signals.** Goulding, Harvey & Mazzoleni (2023, JFE) show a single slow signal is weak at turning points. Crossing a 12-month and 1-month signal gives four states — Bull, Correction, Bear, Rebound — and blended intermediate-speed strategies beat pure slow or fast on Sharpe, drawdown and skew. This replaces the plain 12-month signal as Book B's baseline.

**Vol management helps momentum specifically, not everything.** Cederburg et al. (2020, JFE) tested 103 strategies: out of sample, vol management does not systematically help, but it does help momentum. So the overlay is well-founded for Book B and unproven for Book A — test Book A with and without it. Wang & Yan (2021, JBF) find scaling by *downside* volatility beats total volatility; test it as a variant.

**Gold/silver cointegration still holds, but the evidence is weaker than it looks.** Batten, Ciner & Lucey (2013) document mean reversion in the spread. A 2025 SSRN preprint (Mittal & Mittal) finds the pair cointegrated over 2015-2025 with a Kalman hedge ratio drifting between 1.2 and 1.6 — but it's not peer-reviewed, uses futures rather than CFDs, and leans on ML regime filters, which carry overfitting risk. Treat it as a sanity check on your beta range, not a target.

### 1.4 Trade frequency target

Target: **2-3 trades per week across the whole portfolio.**

- **Book A carries the frequency.** Stat arb is naturally medium-frequency. Run spreads on H1/H4 bars and aim for a residual half-life of roughly 0.5-2 days, which gives about one round trip per pair per week. Two pairs ≈ 1.5-3 trades a week on their own.
- **Book B is sped up modestly, not rebuilt.** H4 bars with a medium slow/fast blend adds roughly 2-4 trades a month across XAUUSD and US100.
- **Combined:** roughly 2-4 trades a week.

**The trade-off:** at shorter horizons residual swings shrink while spreads stay fixed, so costs bite harder. A pair that passes the cost screen on daily bars can fail on H1. That's why the screen runs at H1 and H4.

**The rule: frequency is a target for design, never for tuning.** If a pair only reaches 2-3 trades a week by lowering thresholds until it fails costs, the answer is fewer trades, not a weaker filter. Never relax a cost, half-life or validation threshold to hit the frequency target. Report actual frequency honestly, including if it falls short.

**Realistic expectation:** XAUUSD/XAGUSD survives, US100/US500 is marginal, Book B carries the portfolio. Build for that outcome rather than being surprised by it.

---

## 2. Environment and safety rules

Claude Code runs on the PC and is connected to the MT5 terminal through the `MetaTrader5` Python package. It can:
- pull price history directly (`copy_rates_range`) and tick history (`copy_ticks_range`)
- read contract specifications (`symbol_info`): swap, contract size, lot limits, point value
- run the full Python research stack
- write, and iterate on, the MQL5 EA

It *could* also place orders. It must not, in this phase.

**HARD RULE — READ-ONLY UNTIL STEP 8.** Never call `order_send`, `order_check`, or any function that places, modifies or closes orders or positions. No exceptions for "testing". Live or demo execution only begins at build step 8, and only with explicit instruction from Dutch in that session.

Before pulling data:
- The MT5 terminal must be open and logged in to the broker account that will actually be traded
- Set **Tools → Options → Charts → Max bars in chart** to unlimited, or history will be truncated
- Report how much history the broker actually provides for each symbol and timeframe — do not assume 5 years arrived

The production EA must still be self-contained: all trading logic in MQL5, no dependency on Python running alongside it.

---

## 3. Gate — run before any strategy code

### 3.1 Data pull

Pull via the `MetaTrader5` package from the broker account that will be traded. Do not substitute Yahoo, TradingView or any third-party feed — CFD prices differ from the underlying index, and that gap is where backtests lie.

| Instrument | Timeframe | Minimum history |
|---|---|---|
| US100 | D1 + H4 + H1 | 5 years |
| US500 | D1 + H4 + H1 | 5 years |
| XAUUSD | D1 + H4 + H1 | 5 years |
| XAGUSD | D1 + H4 + H1 | 5 years |

Save each to `data/` as CSV (e.g. `US100_D1.csv`). Record the broker server timezone offset in a config file. Align pair legs on common timestamps and report gaps or missing bars.

### 3.2 Cost table

Build `data/costs.csv` from `symbol_info` for each symbol, with the date the values were read. Swaps change; the date matters.

Spreads: do not use the single current spread from `symbol_info`. Estimate typical (median) and worst-case (95th percentile) spread from tick history, split by trading session (Asia / London / New York). Save the method alongside the results.

| Instrument | Typical spread (pts) | Worst-case spread (pts) | Commission | Swap long | Swap short | Min lot | Lot step | Point value |
|---|---|---|---|---|---|---|---|---|
| US100 | | | | | | | | |
| US500 | | | | | | | | |
| XAUUSD | | | | | | | | |
| XAGUSD | | | | | | | | |

Commission is not in `symbol_info` — if the account charges one, Dutch supplies it. Ask rather than assume zero.

### 3.3 The screen

For each candidate pair, **at both H1 and H4 bar horizons**:

1. Fit the hedge ratio (rolling OLS baseline, window in bars: start at 120 H1 bars / 60 H4 bars)
2. Compute the residual series and its standard deviation in price units
3. Round-trip cost of the pair = (spread + commission) on both legs, same units. Use the spread for the session the pair would actually trade in.
4. Estimate the Ornstein-Uhlenbeck half-life of the residual, in bars and in days
5. Expected financing = swap on both legs × number of rollovers expected over the half-life
6. Expected trade frequency ≈ implied round trips per week from the half-life

**Kill rule:** if `(round-trip cost + financing) / residual std dev > 0.33` → the pair is dead. Do not backtest it. Do not relax the threshold to save it.

**Half-life rule:** if half-life > 5 days → drop the pair. Financing decides P&L, not convergence.

**Frequency band:** half-life of 0.5-2 days = on target. 2-5 days = passes but below the frequency target; report it, don't force it. Under ~0.25 days = likely noise and spread-dominated; treat with suspicion even if it passes.

**Stop here and report results before continuing.**

---

## 4. Book A — Statistical arbitrage

### A1. US100 / US500 — index-tech spread
### A2. XAUUSD / XAGUSD — metals ratio

Both subject to the section 3.3 gate.

**Timeframe:** H1 or H4 — whichever horizon passed the cost screen for that pair. If both passed, prefer the one with the better cost ratio, not the one with more trades.

**Hedge ratio**
- Kalman filter, or rolling OLS as the simpler baseline (window in bars, per section 3.3)
- Never a fixed beta — static betas are how pairs books blow up
- Re-estimate every bar; log the beta series and inspect for instability before trusting anything downstream

**Signal**
- z-score of residual against a rolling window in bars (start at 60-120, test across that range)
- Entry: |z| > 2.0 baseline
- Variant: |z| > 1.5 to raise frequency — only if it still passes costs and the deflated Sharpe test. Never adopt it just to hit the trade count.
- Exit: |z| < 0.5 or z crosses 0
- Hard stop: |z| > 3.5 — treat as cointegration break. Close. Do not add.

**Filters**
- No trend filter on the spread (see 1.2)
- Leg-level gate: stand aside if either leg's realised vol (20-day equivalent, computed on the trading timeframe) is in its top decile versus its own 2-year history
- Rolling cointegration re-test (Engle-Granger or Johansen); suspend the pair if it fails at 5%

---

## 5. Book B — Momentum

### B1. XAUUSD — primary
### B2. US100 — secondary

**Timeframe:** H4 primary (for the frequency target). D1 kept as a slow comparison. Not lower than H4.

**Signal** (updated per Goulding, Harvey & Mazzoleni 2023)
- Compute slow signal = sign of trailing return over the slow lookback, fast signal = sign of trailing return over the fast lookback
- Primary (medium speed, H4): slow ≈ 60 trading days, fast ≈ 10 trading days, expressed in H4 bars. Test a range around these, pick from a plateau
- Slow comparison (D1): slow = 12 months, fast = 1 month — the published specification
- Evidence is strongest at the slow speed. The medium-speed version must still clear the vol-scaled buy-and-hold benchmark (section 7, item 6); if only the slow version does, report that plainly
- Classify each bar into four states: Bull (both +), Bear (both −), Correction (slow +, fast −), Rebound (slow −, fast +)
- Baseline: static 50/50 blend of slow and fast positions
- Variant 1: dynamic speed — tilt weights after Corrections/Rebounds based on historical state-conditional returns, estimated walk-forward only
- Variant 2: dual moving-average crossover (kept as a simple comparison)
- Pick parameters from a plateau, never a peak
- Note: the four-state evidence comes from equity markets. It should transfer to US100; for XAUUSD it is untested, so validate separately.

**Filters**
- Directional: long only above the long MA, short only below
- Regime: flat when realised vol (20-day equivalent) is in its top decile

**Holding cost:** XAUUSD swap is typically negative in both directions. Multi-day trend holds pay this nightly. Model it per bar held, not as an average.

**Behavioural note:** trend following produces long, ugly drawdowns — 18 months is normal, not a malfunction. The rules are the easy part. If the plan is to abandon the system during the flat stretch, the backtest is irrelevant.

---

## 6. Overlay — portfolio level, shared

**Vol targeting**
- Size each position inversely to its 20-day realised vol
- Use a crude, identical vol model across all instruments. Resist sophistication here — the published time-series momentum work uses a deliberately simple model for exactly this reason.
- Lag the vol estimate by one bar. No look-ahead.
- Estimator: start with close-to-close 20-day. Test Yang-Zhang (uses OHLC, more efficient — Baltas & Kosowski show better estimators cut turnover) and downside semi-volatility (Wang & Yan 2021) as variants.
- Apply to Book B by default. For Book A, run with and without — the evidence that vol management helps mean-reversion spreads is weak (Cederburg et al. 2020).

**Kill switch**
- Single portfolio-level trigger: aggregate realised vol above its 95th percentile → everything flat

**Netting**
- Net US100 exposure across books before sending orders
- Hardcode the gross/net decision; don't leave it implicit

---

## 7. Validation — non-negotiable

1. **Walk-forward**, not a single in-sample fit. Rolling train/test splits.
2. **Deflated Sharpe ratio.** Count every parameter combination tested — the count is the input. Be honest about it; this is the whole point of the metric.
3. **Cost sensitivity.** Re-run at 1.5× and 2× assumed spread. If the edge dies, it was never there.
4. **Parameter plateau check.** Plot performance across the grid. Sharp peak = overfitting. Broad plateau = signal.
5. **Python/MQL5 parity.** Run the same date range through both, reconcile trade by trade. Any discrepancy is a bug, not rounding. This is the classic backtest-to-live failure and it is worth more effort than it looks like it deserves.
6. **Benchmark Book B against vol-scaled buy-and-hold** of the same instrument, with the same vol target and costs. Per Kim, Tse & Wald (2016) and Huang et al. (2020), this is the honest hurdle. Gold's long uptrend will make almost any long-biased trend rule look good; this test tells you whether the signal or the drift is earning the money.
7. **Report realised trade frequency** per book and combined, per week, across the walk-forward periods. Compare to the 2-3/week target in section 1.4. Falling short is an acceptable result; hitting it by loosening filters is not.

---

## 8. Build sequence

1. Data loader + cost config
2. Cost screen (section 3.3) — **stop and report**
3. Book B backtest (stronger evidence base — build first)
4. Overlay + vol targeting
5. Book A backtest, surviving pairs only
6. MQL5 EA for Book B
7. Parity test
8. Book A paper-traded one quarter alongside live/demo Book B
9. Capitalise Book A only if it clears costs on paper

---

## 9. Literature

Read the overfitting papers **before** building, not after a backtest looks brilliant.

**Overfitting (first)**
- Bailey & López de Prado, *The Deflated Sharpe Ratio* — SSRN 2460551. Free at davidhbailey.com. Corrects for selection bias under multiple testing and non-normal returns.
- Harvey & Liu, *Backtesting* — SSRN 2345489
- Harvey & Liu, *Evaluating Trading Strategies* — SSRN 2474755
- Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and Financial Charlatanism*
- Python implementation: github.com/esvhd/pypbo

**Momentum**
- Moskowitz, Ooi & Pedersen, *Time Series Momentum* — SSRN 2089463. Effect documented across 58 liquid instruments; persistence 1-12 months, partial reversal beyond. Free PDF at NYU Stern. Original dataset on AQR's site.
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing*
- Lempérière et al., *Two Centuries of Trend Following*
- Baz, Granger, Harvey et al., *Dissecting Investment Strategies in the Cross Section and Time Series* — SSRN 2695101. The practical how-to.

**Statistical arbitrage**
- Avellaneda & Lee, *Statistical Arbitrage in the U.S. Equities Market* — SSRN 1153505. PCA/ETF residuals as mean-reverting, contrarian signals. Net of costs: Sharpe 1.44 over 1997-2007, but only 0.9 over 2003-2007. The decay is the lesson.
- Krauss, *Statistical Arbitrage Pairs Trading Strategies: Review and Outlook* — the literature map. Across 76 studies: ~10.8% annualised, Sharpe ~0.96, declining from 15.6% pre-2000 to 6.4% post-2010.
- Do & Faff, *Are Pairs Trading Profits Robust to Trading Costs?* — directly relevant to section 3.3
- Gatev, Goetzmann & Rouwenhorst (2006) — the canonical distance-method study

**Volatility overlay**
- Moreira & Muir, *Volatility-Managed Portfolios* — SSRN 2659431, free as NBER w22208. Scaling down when vol is high raises Sharpe because vol changes aren't offset by proportional expected-return changes.
- Cederburg et al. — the rebuttal, across 103 equity strategies
- Harvey et al. (2018), *The Impact of Volatility Targeting*

**Recent and critical work (2016-2025) — read alongside the classics**
- Kim, Tse & Wald, *Time Series Momentum and Volatility Scaling* (JFM 2016) — TSMOM alpha is mostly vol scaling
- Huang, Li, Wang & Zhou, *Time-Series Momentum: Is It There?* — SSRN 3165284, JFE 2020. Free PDF on SMU's repository.
- Goulding, Harvey & Mazzoleni, *Momentum Turning Points* — SSRN 3489539, JFE 2023. Free PDF on Harvey's Duke page. Basis of Book B's signal.
- Baltas & Kosowski, *Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and Pairwise Correlations* — vol estimator choice
- Cederburg, O'Doherty, Wang & Yan, *On the Performance of Volatility-Managed Portfolios* — SSRN 3357038, JFE 2020
- Wang & Yan, *Downside Risk and the Performance of Volatility-Managed Portfolios* (JBF 2021)
- Barroso & Detzel, *Do Limits to Arbitrage Explain the Benefits of Volatility-Managed Portfolios?*
- Batten, Ciner & Lucey (2013) — gold/silver spread mean reversion
- Mittal & Mittal, *Gold Silver Pair Trading — Mean Reversion Strategy Using Machine Learning* — SSRN 5710242 (2025 preprint, not peer-reviewed; use as a reference point only)
- Fil, *Gold Standard Pairs Trading Rules: Are They Valid?* (arXiv 2010.01157) — documents cost erosion of classic distance and cointegration rules

**Practitioner**
- Clenow, *Following the Trend* — implementation manual for Book B. Allocate by risk not cash; size from the volatility of the underlying price action.
- Carver, *Systematic Trading* — system design and overfitting discipline
- Thorp, *Statistical Arbitrage* (Wilmott series) — honest practitioner account

**SSRN browsing:** Financial Economics Network → Capital Markets: Asset Pricing & Valuation, and Econometric Modeling: Capital Markets. JEL codes G11, G12, G14, C22, C58.

---

## 10. What this does not promise

Not that the result is profitable. The honest ceiling is whether an edge survives realistic costs in-sample and holds out-of-sample.

Pairs-trading returns in the published literature have decayed materially since 2010. Stat arb's strongest results come from institutional settings — cross-sectional breadth, prime-broker financing, colocation — none of which exist on a retail CFD book. Research pedigree is not the same as edge on this book.

Build expecting Book B to carry the portfolio, and let Book A earn its capital on paper first.
