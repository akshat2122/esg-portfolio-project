# ESG-Tilted vs. Mean-Variance Portfolio: A French Equities Case Study

This project builds two portfolios out of 28 SBF 120 (French large/mid-cap)
stocks and asks a simple question: **if you screen out the worst governance
performers before running a standard portfolio optimizer, what do you give
up — or gain — in risk-adjusted return?**

It's a self-contained Python pipeline: point it at Yahoo Finance, and it
downloads five years of prices, builds both portfolios, backtests them
out-of-sample, and drops a results table and a chart into `outputs/`.

```
python main.py            # uses cached data after the first run
python main.py --refresh  # force a clean re-download from Yahoo
```

---

## 1. What's being compared

Four "lines," all built from the same 28-stock universe:

| Line | What it is |
|---|---|
| **Portfolio A** | Standard max-Sharpe mean-variance optimization. No ESG input at all. |
| **Portfolio B** | The identical optimizer, run on the same universe *minus the bottom 25% by governance/ESG score*. |
| **Equal-Weight Benchmark** | 1/28 in every name — the "do nothing clever" baseline. |
| **Cap-Weighted Benchmark** | Weighted by current market capitalization — a proxy for how the broad index itself is weighted. |

Both optimized portfolios (A and B) are built under the *same* position
limits, so any difference between them comes from the ESG screen, not from
different rules:

- No single stock above **20%** of the portfolio.
- No single sector above **35%** of the portfolio.
- Long-only, fully invested (weights sum to 100%).

## 2. The universe

28 SBF 120 constituents spanning **11 sectors** (Financials, Industrials,
Consumer Discretionary, Consumer Staples, Health Care, Utilities, Energy,
Materials, Technology, Communication Services, Real Estate) — see
`config.py` for the full list of tickers and sector labels.

The candidate list was deliberately built a little larger than the 20–30
target so that the "at least 3 years of price history" rule has real work to
do: `data_fetch.filter_by_min_history()` checks the *actual* number of
trading days Yahoo returns for each ticker (not just the requested 5-year
window) and drops anything short of it. In the run that produced the
outputs checked into this repo, all 28 candidates had a full history, so
nothing was dropped on that basis — but the mechanism is real and will kick
in if you swap in newer or thinly-traded names. Whenever a name *is*
dropped — for history or for ESG data — it's named explicitly in
`outputs/universe_and_esg_report.txt`, never silently excluded.

## 3. The ESG data source — and its real limitation

This is the part worth reading carefully before you trust any ESG-tilt
result, from this project or anyone else's.

**The plan was:** pull each company's Environmental + Social + Governance
score from `yfinance`'s `Ticker.sustainability` field (which wraps Yahoo
Finance's ESG data, originally licensed from Sustainalytics).

**What actually happened when this was built (September 2026):** that field
came back **empty for every single one of the 28 tickers** — and, out of
curiosity, for US mega-caps like Apple and Microsoft too. Yahoo's ESG
`quoteSummary` module now returns an HTTP 404 for effectively everyone.
This isn't a France-specific or small-cap-specific gap — the free data
source the assignment specified has, in practice, stopped serving this
field.

Rather than quietly leaving Portfolio B's screen empty (or, worse, making up
plausible-looking numbers), the code detects this, prints an explicit
warning, and falls back to the one ESG-adjacent field Yahoo *does* still
serve for free: **ISS governance risk sub-scores**
(`auditRisk`, `boardRisk`, `compensationRisk`, `shareHolderRightsRisk`,
`overallRisk`), pulled from `Ticker.info`. These are real, live numbers on a
1 (lowest risk) to 10 (highest risk) scale; this project inverts and
averages them into a single "higher is better" **governance-risk proxy
score**.

**What this means for the results — please read this before sharing them:**

- This is a **Governance-only** proxy. It says nothing about a company's
  carbon footprint, labor practices, or supply-chain risk (the "E" and "S"
  in ESG). Calling Portfolio B "ESG-tilted" is shorthand for "tilted away
  from weak corporate governance," which is a real and useful thing to tilt
  towards — just not the full picture "ESG" usually implies.
- It's a **snapshot**. Yahoo serves today's governance score, not a
  five-year history of it. The screen is applied retroactively across the
  whole backtest, on the (imperfect) assumption that governance quality is
  reasonably stable over a few years.
- For a production version of this analysis, you'd want a licensed,
  point-in-time ESG dataset (MSCI, Sustainalytics, Refinitiv, ISS directly)
  rather than a free API's leftovers. This project uses what's actually
  reachable for free, and says so.

Every run writes the full coverage numbers (names with a real ESG score vs.
names using the proxy, and anything dropped outright) to
`outputs/universe_and_esg_report.txt` — that file is the audit trail, not
this README.

## 4. Method, step by step

1. **Prices.** Five years of daily prices per ticker (`yfinance`,
   dividend/split-adjusted), converted to daily simple returns.
2. **Risk & return inputs.** Annualized expected return per stock =
   historical daily mean return, compounded up to a year. Covariance matrix
   = daily return covariance, scaled by 252 trading days. (Historical means
   are a noisy estimate of *future* returns — the standard, well-known
   weakness of textbook mean-variance optimization. This project uses them
   because that's what "standard mean-variance optimization" means; a
   sturdier version would shrink these estimates or use a factor model.)
3. **Portfolio A.** `scipy.optimize.minimize` (SLSQP) maximizes the Sharpe
   ratio `(portfolio return − risk-free rate) / portfolio volatility`
   subject to the 20%-per-name / 35%-per-sector / fully-invested constraints,
   over the full 28-stock universe.
4. **Portfolio B.** Take the same universe, rank every stock by its ESG /
   governance-proxy score, drop the bottom 25%, and run the *identical*
   optimizer on the survivors.
5. **Benchmarks.** Equal-weight and current-market-cap-weight portfolios
   over the same 28 stocks. (Note: this cap-weighted line is a proxy built
   from this project's own 28-name universe using today's market caps held
   fixed — not the official, licensed SBF 120 index, which Yahoo does not
   serve as a usable daily time series. See the code comments in
   `data_fetch.fetch_market_caps` for details.)

## 5. The out-of-sample split — and why it matters

It's easy to build an optimizer that looks brilliant on the data it was
fitted to and tells you nothing about tomorrow. To avoid fooling ourselves:

- **Years 1–4** of the five-year window are the **training period**. Only
  data from this window is used to estimate expected returns, the
  covariance matrix, and therefore the optimal weights for Portfolio A and
  Portfolio B.
- **Year 5** is the **test period**. The weights computed in step above are
  frozen and simply *held* through this final year — no re-optimizing, no
  peeking at year-5 data when deciding the weights. All four lines' returns
  in the results table and chart are measured over this held-out year only.

This is a **static, buy-and-hold** backtest (weights are set once and not
rebalanced during the test year), which keeps the exercise simple and
transparent, but is itself a simplification — a real fund would typically
rebalance quarterly or when drift breaches a threshold.

## 6. Reading the results

Every run regenerates these files in `outputs/`:

| File | Contents |
|---|---|
| `results_table.csv` | Cumulative return, annualized return, annualized volatility, Sharpe ratio, and max drawdown for all 4 lines, over the year-5 test window. |
| `cumulative_returns_chart.png` | Growth-of-€1 chart for all 4 lines over the same window. |
| `weights_portfolio_a.csv` / `weights_portfolio_b.csv` | The actual optimized position sizes. |
| `universe_and_esg_report.txt` | The full transparency log: history-based drops, ESG coverage and fallback details, ESG-based exclusions, and a sector-allocation check confirming the 35% cap held. |

Sample results from one run of this pipeline (your numbers will differ
slightly each time you re-run with `--refresh`, since markets keep moving —
this is a live, not a static, backtest):

| Line | Cumulative Return | Annualized Return | Volatility | Sharpe | Max Drawdown |
|---|---|---|---|---|---|
| Portfolio A (Mean-Variance) | 18.7% | 18.4% | 14.1% | 1.13 | -10.5% |
| Portfolio B (ESG-Tilted) | 13.4% | 13.2% | 13.2% | 0.81 | -11.0% |
| Equal-Weight Benchmark | 5.3% | 5.2% | 13.4% | 0.20 | -11.3% |
| Cap-Weighted Benchmark | 8.0% | 7.9% | 14.6% | 0.37 | -11.4% |

The honest headline from *this* run: both optimized portfolios comfortably
beat both passive benchmarks out-of-sample — which is what a concentrated,
constraint-bound optimizer run on a calm-ish year should do. The
governance-screened portfolio (B) came in behind the unconstrained
optimizer (A) on both return and Sharpe ratio, though with a very similar
volatility. That's a real, plausible outcome of removing names from the
optimizer's opportunity set (here, the screen removed some of Portfolio A's
biggest winners, like LVMH and Hermès) — not a verdict on whether "ESG
investing" costs you money in general. One 28-stock universe, one test
year, and a governance-only proxy score is nowhere near enough data to
support that broader claim either way.

## 7. Assumptions worth knowing about

- **Risk-free rate:** a flat 2.5% annual, set in `config.py`
  (`RISK_FREE_RATE_ANNUAL`) — a rough stand-in for recent euro-area
  short-term rates. Change it and re-run if you have a better number.
- **No rebalancing** during the year-5 test window (see §5).
- **ESG score is Governance-only**, current-snapshot, and applied
  retroactively (see §3) — this is the single biggest caveat in the whole
  project.
- **Cap-weighted benchmark** uses today's market caps, held static, across
  this project's 28-name universe — not the official SBF 120 index.

## 8. Project layout

```
config.py       Universe, sectors, dates, constraints, all tunable constants
data_fetch.py   All Yahoo Finance I/O: prices, ESG data (+ fallback), market caps
metrics.py      Returns, annualization, covariance, the 5-metric scorecard
optimizer.py    Constrained max-Sharpe mean-variance optimization (scipy SLSQP)
backtest.py     Train/test split, builds all 4 portfolios, runs the backtest
report.py       Results table, chart, weight files, transparency report
main.py         Orchestrates the pipeline end to end
outputs/        Everything the pipeline generates (see §6)
data_cache/     Cached downloads, so re-runs don't have to hit Yahoo again
```

## 9. Running it yourself

```bash
pip install -r requirements.txt
python main.py
```

First run downloads ~5 years of daily data for 28 tickers plus governance
data, which takes a minute or two; every run after that uses the cache in
`data_cache/` unless you pass `--refresh`.
