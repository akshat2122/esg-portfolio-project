"""
backtest.py
===========
Wires everything together into the actual train/test experiment:

  - Train window = first 4 years of the 5-year history.
  - Test window  = final 1 year (held out, out-of-sample).

Portfolio weights (for A, B, and the cap-weighted benchmark) are computed
*once*, using only training-window data, then held fixed and applied to the
test-window daily returns -- a static buy-and-hold backtest, not a
periodically-rebalanced one. That simplification is called out in README.md.
"""

import numpy as np
import pandas as pd

import config
import metrics
import optimizer


def split_train_test(daily_returns, test_years=config.TEST_WINDOW_YEARS):
    """Calendar-based split: the last `test_years` of the sample is the
    out-of-sample test window; everything before it is training data."""
    end_date = daily_returns.index.max()
    test_start = end_date - pd.DateOffset(years=test_years)
    train = daily_returns[daily_returns.index <= test_start]
    test = daily_returns[daily_returns.index > test_start]
    return train, test


def equal_weights(tickers):
    return pd.Series(1.0 / len(tickers), index=tickers)


def cap_weights(tickers, market_caps):
    caps = pd.Series({t: market_caps.get(t) for t in tickers}, dtype="float64").dropna()
    if caps.empty:
        raise ValueError("No market cap data available to build the cap-weighted benchmark.")
    return caps / caps.sum()


def build_portfolios(train_returns, sector_map, esg_df, esg_bottom_quartile=config.ESG_BOTTOM_QUARTILE):
    """
    Runs the max-Sharpe optimizer twice:
      - Portfolio A: every ticker in train_returns (no ESG input at all).
      - Portfolio B: same universe minus the bottom quartile by ESG score.

    Returns (weights_A, weights_B, esg_excluded_tickers, b_universe).
    """
    full_universe = list(train_returns.columns)

    mean_A = metrics.annualized_mean_returns(train_returns[full_universe])
    cov_A = metrics.annualized_covariance(train_returns[full_universe])
    weights_A = optimizer.max_sharpe_weights(mean_A, cov_A, sector_map)

    # --- ESG screen for Portfolio B -------------------------------------
    scored = esg_df.set_index("ticker")["esg_score"].reindex(full_universe).dropna()
    cutoff = scored.quantile(esg_bottom_quartile)
    esg_excluded = sorted(scored[scored <= cutoff].index.tolist())
    # Names with no ESG score at all can't be screened -- they are excluded
    # from Portfolio B's eligible universe too, and reported separately.
    esg_unscored = sorted(set(full_universe) - set(scored.index))

    b_universe = [t for t in full_universe if t not in esg_excluded and t not in esg_unscored]

    mean_B = metrics.annualized_mean_returns(train_returns[b_universe])
    cov_B = metrics.annualized_covariance(train_returns[b_universe])
    weights_B = optimizer.max_sharpe_weights(mean_B, cov_B, sector_map)

    return weights_A, weights_B, esg_excluded, esg_unscored, b_universe


def run_backtest(prices, sector_map, esg_df, market_caps):
    """
    Full pipeline: split data, build all four portfolios' weights on the
    training window, evaluate all four on the held-out test window.

    Returns a dict with weights, per-line test-window daily returns, wealth
    curves, and the performance scorecard -- everything report.py needs.
    """
    daily_returns = metrics.compute_daily_returns(prices)
    train_returns, test_returns = split_train_test(daily_returns)

    weights_A, weights_B, esg_excluded, esg_unscored, b_universe = build_portfolios(
        train_returns, sector_map, esg_df
    )

    full_universe = list(prices.columns)
    weights_EW = equal_weights(full_universe)
    weights_CW = cap_weights(full_universe, market_caps)

    lines = {
        "Portfolio A (Mean-Variance)": weights_A,
        "Portfolio B (ESG-Tilted)": weights_B,
        "Equal-Weight Benchmark": weights_EW,
        "Cap-Weighted Benchmark": weights_CW,
    }

    results = {}
    for name, w in lines.items():
        port_returns = metrics.portfolio_daily_returns(w, test_returns)
        summary, wealth = metrics.performance_summary(port_returns)
        results[name] = {
            "weights": w,
            "test_returns": port_returns,
            "wealth": wealth,
            "summary": summary,
        }

    return {
        "results": results,
        "train_window": (train_returns.index.min(), train_returns.index.max()),
        "test_window": (test_returns.index.min(), test_returns.index.max()),
        "esg_excluded_bottom_quartile": esg_excluded,
        "esg_unscored": esg_unscored,
        "portfolio_b_universe": b_universe,
    }
