"""
metrics.py
==========
Return/risk statistics shared by every stage of the pipeline: turning a
price panel into daily returns, annualizing, building the covariance matrix,
and computing the standard backtest scorecard (cumulative return, annualized
return, volatility, Sharpe ratio, max drawdown) for a return series.
"""

import numpy as np
import pandas as pd

import config


def compute_daily_returns(prices):
    """Simple (not log) daily returns -- simple returns are what you want
    when you're about to weight-and-sum them into a portfolio return."""
    return prices.pct_change().dropna(how="all")


def annualize_return(daily_mean_return, periods_per_year=config.TRADING_DAYS_PER_YEAR):
    return (1 + daily_mean_return) ** periods_per_year - 1


def annualize_volatility(daily_std, periods_per_year=config.TRADING_DAYS_PER_YEAR):
    return daily_std * np.sqrt(periods_per_year)


def annualized_mean_returns(daily_returns):
    """Per-asset annualized expected return, estimated from the historical
    daily mean. This is the textbook approach; it's also a well-known weak
    spot of mean-variance optimization (historical means are noisy and
    unstable) -- flagged again in README.md."""
    return daily_returns.mean().apply(annualize_return)


def annualized_covariance(daily_returns):
    return daily_returns.cov() * config.TRADING_DAYS_PER_YEAR


def portfolio_daily_returns(weights, daily_returns):
    """weights: pd.Series indexed by ticker. daily_returns: DataFrame with
    those same tickers as columns. Returns a single portfolio return series,
    aligned and re-normalized in case a column is missing on some dates."""
    w = weights.reindex(daily_returns.columns).fillna(0.0)
    return daily_returns.mul(w, axis=1).sum(axis=1)


def max_drawdown(cumulative_wealth):
    """cumulative_wealth: a series starting at 1.0 (growth of $1)."""
    running_max = cumulative_wealth.cummax()
    drawdown = cumulative_wealth / running_max - 1.0
    return drawdown.min()


def performance_summary(daily_returns, risk_free_rate=config.RISK_FREE_RATE_ANNUAL,
                         periods_per_year=config.TRADING_DAYS_PER_YEAR):
    """
    Compute the standard scorecard for a single return series over whatever
    window it spans (used here for the year-5 out-of-sample test window).
    """
    daily_returns = daily_returns.dropna()
    n_days = len(daily_returns)
    wealth = (1 + daily_returns).cumprod()
    wealth = pd.concat([pd.Series([1.0], index=[wealth.index[0] - pd.Timedelta(days=1)]), wealth])

    cumulative_return = wealth.iloc[-1] / wealth.iloc[0] - 1.0
    ann_return = (1 + cumulative_return) ** (periods_per_year / n_days) - 1 if n_days > 0 else np.nan
    ann_vol = annualize_volatility(daily_returns.std(), periods_per_year)
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol not in (0, np.nan) else np.nan
    mdd = max_drawdown(wealth)

    return {
        "Cumulative Return": cumulative_return,
        "Annualized Return": ann_return,
        "Annualized Volatility": ann_vol,
        "Sharpe Ratio": sharpe,
        "Max Drawdown": mdd,
    }, wealth
