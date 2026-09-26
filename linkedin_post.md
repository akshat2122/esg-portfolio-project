# LinkedIn post draft

---

I built a small backtest to answer a question I kept seeing debated with no
data behind it: **if you screen out weak-governance companies before running
a portfolio optimizer, what does it actually cost you (or save you)?**

The setup: 28 SBF 120 stocks (French large/mid-caps) across 11 sectors, 5
years of daily prices. Two portfolios, both built with the same optimizer
and the same constraints (max 20% in any one name, max 35% in any one
sector) — the only difference is that one of them excludes the bottom
quartile by ESG score first. I optimized on 4 years of data and tested both,
completely out-of-sample, on the 5th.

Here's the part I didn't expect to be the most interesting finding: **the
free ESG data I planned to use doesn't really exist anymore.** I went in
assuming I'd pull sustainability scores from Yahoo Finance like a lot of
tutorials show you. When I actually queried it, the field came back empty —
for all 28 of my stocks, and for Apple and Microsoft when I tried them out
of curiosity too. Yahoo's ESG data module now just 404s. It's not a "small
company" or "European stock" gap, it's the whole endpoint.

So rather than fake it or quietly drop the ESG angle, the code detects that,
prints an explicit warning, and falls back to something narrower but real:
governance-risk scores that Yahoo still serves. That means my "ESG-tilted"
portfolio is honestly a **governance-tilted** portfolio — no claim about
environmental or social performance, because I don't have that data. I'd
rather ship a project that's upfront about what it's actually measuring than
one that looks more complete than it is.

The result, for what one 28-stock universe and one test year is worth:

| | Cumulative Return | Sharpe | Max Drawdown |
|---|---|---|---|
| Mean-Variance (no screen) | 18.7% | 1.13 | -10.5% |
| Governance-Tilted | 13.4% | 0.81 | -11.0% |
| Equal-Weight Benchmark | 5.3% | 0.20 | -11.3% |
| Cap-Weighted Benchmark | 8.0% | 0.37 | -11.4% |

Both optimized portfolios beat the passive benchmarks by a wide margin — no
surprise, that's what a constrained optimizer is supposed to do. The
governance screen gave up some return here, mostly because it excluded a
couple of the unconstrained portfolio's biggest winners (LVMH, Hermès). That
tells you something about *this* year and *this* universe. It tells you
nothing reliable about whether ESG/governance investing "costs you" in
general — one backtest never does, no matter how clean the code is.

Full method, code, and the "here's exactly what got dropped and why" data
report are on GitHub: [link]

#quant #portfoliomanagement #ESG #python #opendata

---

*Notes for posting: swap `[link]` for
https://github.com/akshat2122/esg-portfolio-project, and consider attaching
`outputs/cumulative_returns_chart.png` as the post image.*
