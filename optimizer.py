"""
optimizer.py
============
Constrained max-Sharpe mean-variance optimization, used identically for
Portfolio A (full universe) and Portfolio B (ESG-screened universe) -- the
only difference between the two portfolios is which tickers get *passed in*,
never the optimization logic itself.

Constraints applied to both portfolios:
  - long-only, 0% - 20% per name (MAX_WEIGHT_PER_NAME in config.py)
  - <= 35% per GICS-style sector (MAX_WEIGHT_PER_SECTOR in config.py)
  - fully invested: weights sum to 1
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import config


def _negative_sharpe(weights, mean_returns, cov_matrix, risk_free_rate):
    port_return = np.dot(weights, mean_returns)
    port_vol = np.sqrt(weights @ cov_matrix @ weights)
    if port_vol == 0:
        return 1e6
    return -(port_return - risk_free_rate) / port_vol


def _sector_constraints(tickers, sector_map, max_weight_per_sector):
    """One inequality constraint per sector: max_weight_per_sector - sum(w in sector) >= 0."""
    sectors = sorted(set(sector_map[t] for t in tickers))
    constraints = []
    for sector in sectors:
        idx = [i for i, t in enumerate(tickers) if sector_map[t] == sector]

        def make_fun(idx=idx):
            def fun(w):
                return max_weight_per_sector - w[idx].sum()
            return fun

        constraints.append({"type": "ineq", "fun": make_fun()})
    return constraints


def max_sharpe_weights(mean_returns, cov_matrix, sector_map,
                        max_weight_per_name=config.MAX_WEIGHT_PER_NAME,
                        max_weight_per_sector=config.MAX_WEIGHT_PER_SECTOR,
                        risk_free_rate=config.RISK_FREE_RATE_ANNUAL):
    """
    mean_returns: pd.Series (annualized), indexed by ticker.
    cov_matrix:  pd.DataFrame (annualized), same tickers as index/columns.
    sector_map:  dict ticker -> sector name.

    Returns a pd.Series of optimal weights, indexed by ticker, summing to 1.
    """
    tickers = list(mean_returns.index)
    n = len(tickers)
    mu = mean_returns.values
    sigma = cov_matrix.loc[tickers, tickers].values

    bounds = [(config.MIN_WEIGHT_PER_NAME, max_weight_per_name)] * n

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    constraints += _sector_constraints(tickers, sector_map, max_weight_per_sector)

    # Equal-weight start, respecting the per-name cap.
    x0 = np.full(n, 1.0 / n)

    result = minimize(
        _negative_sharpe,
        x0,
        args=(mu, sigma, risk_free_rate),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )

    if not result.success:
        raise RuntimeError(f"Optimizer failed to converge: {result.message}")

    weights = pd.Series(result.x, index=tickers)
    weights[weights.abs() < 1e-6] = 0.0
    weights = weights / weights.sum()  # renormalize away tiny numerical slack
    return weights
