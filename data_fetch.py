"""
data_fetch.py
=============
All network I/O lives here: price history, ESG/sustainability data, and
market caps, all pulled via yfinance. Everything is cached to CSV/JSON in
data_cache/ so re-running the pipeline doesn't re-hit Yahoo every time (and
so the run is reproducible if Yahoo's servers are having a bad day).

Two things in this module exist specifically because of how Yahoo's data
actually behaves in practice (verified empirically while building this
project, September 2026), not because the assignment asked for them:

1. `filter_by_min_history` -- some tickers on Yahoo have shorter series than
   their `period="5y"` request implies (index/listing changes, gaps, etc).
   We check real row counts rather than trusting the requested period.

2. `fetch_esg_scores` -- Yahoo's `Ticker.sustainability` endpoint (the "real"
   E/S/G score) currently returns nothing for essentially every ticker we
   tried, including US mega-caps, not just European mid-caps. Rather than
   silently leaving Portfolio B empty, this function detects that, reports
   it explicitly, and falls back to a clearly-labeled governance-risk proxy
   built from real (non-fabricated) fields yfinance still serves. See
   README.md -> "ESG data source and its limitations" for the full story.
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import config

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
def fetch_prices(tickers, period=config.HISTORY_PERIOD, use_cache=True):
    """
    Download daily adjusted close prices for `tickers` over `period`.

    Returns a DataFrame indexed by date, one column per ticker. Uses
    auto_adjust=True so the "Close" column already reflects dividends and
    splits (yfinance's modern equivalent of the old "Adj Close" column).
    """
    cache_file = config.CACHE_DIR / f"prices_{period}.csv"
    if use_cache and cache_file.exists():
        cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if set(tickers).issubset(set(cached.columns)):
            print(f"[data_fetch] Using cached prices from {cache_file}")
            return cached[tickers]

    print(f"[data_fetch] Downloading {len(tickers)} tickers, period={period} ...")
    raw = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="ticker",
    )

    prices = pd.DataFrame({t: raw[t]["Close"] for t in tickers if t in raw.columns.get_level_values(0)})
    prices = prices.sort_index()
    prices.to_csv(cache_file)
    return prices


def filter_by_min_history(prices, min_years=config.MIN_YEARS_HISTORY):
    """
    Drop any ticker whose *actual* non-missing price series (start to end,
    on Yahoo's own calendar) is shorter than `min_years`.

    Returns (kept_tickers, drop_report) where drop_report is a list of dicts
    describing exactly why each dropped ticker was excluded -- this feeds
    straight into the transparency report in outputs/.
    """
    min_days = int(min_years * config.TRADING_DAYS_PER_YEAR)
    kept, drops = [], []

    for t in prices.columns:
        series = prices[t].dropna()
        n_obs = len(series)
        if n_obs == 0:
            drops.append({
                "ticker": t, "n_observations": 0, "years_of_history": 0.0,
                "reason": "No price data returned by Yahoo Finance at all.",
            })
            continue

        span_years = (series.index.max() - series.index.min()).days / 365.25
        if span_years < min_years or n_obs < min_days:
            drops.append({
                "ticker": t,
                "n_observations": n_obs,
                "years_of_history": round(span_years, 2),
                "reason": (
                    f"Only {span_years:.2f} years of price history available "
                    f"(need >= {min_years})."
                ),
            })
        else:
            kept.append(t)

    return kept, drops


# ---------------------------------------------------------------------------
# ESG / sustainability data
# ---------------------------------------------------------------------------
def _try_full_sustainability(ticker):
    """
    Attempt to pull yfinance's "real" ESG data (Ticker.sustainability), which
    wraps Yahoo's `esgScores` quoteSummary module (originally sourced from
    Sustainalytics). Returns a dict of {totalEsg, environmentScore,
    socialScore, governanceScore} if present, else None.
    """
    try:
        tk = yf.Ticker(ticker)
        sus = tk.sustainability
    except Exception:
        return None

    if sus is None or sus.empty:
        return None

    # yfinance has changed the shape of this frame across versions; handle
    # both a single-column frame indexed by metric name, and a dict-like row.
    try:
        flat = sus.iloc[:, 0].to_dict() if sus.shape[1] >= 1 else {}
    except Exception:
        flat = {}

    total = flat.get("totalEsg")
    if total is None:
        return None

    return {
        "total_esg_raw": total,
        "environment_score": flat.get("environmentScore"),
        "social_score": flat.get("socialScore"),
        "governance_score": flat.get("governanceScore"),
    }


def _try_governance_proxy(ticker):
    """
    Fallback: yfinance's `Ticker.info` still exposes ISS governance
    "risk" sub-scores (auditRisk, boardRisk, compensationRisk,
    shareHolderRightsRisk, overallRisk), each on a 1 (lowest risk) to 10
    (highest risk) scale, even when the full ESG module is empty. These are
    real, live values -- not invented -- but they only cover Governance,
    not Environment or Social. Returns None if even these are missing.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None

    fields = ["auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk", "overallRisk"]
    values = {f: info.get(f) for f in fields}
    if values.get("overallRisk") is None:
        return None
    return values


def fetch_esg_scores(tickers, use_cache=True):
    """
    Build a per-ticker ESG score usable for the bottom-quartile screen in
    Portfolio B, being explicit about where each number actually came from.

    Returns (esg_df, report) where:
      - esg_df has columns [ticker, esg_score, esg_source] and one row per
        ticker for which *some* score could be built (higher esg_score is
        always "better", regardless of source, so downstream code never has
        to think about direction).
      - report is a dict summarizing coverage and, crucially, which source
        ended up being used and why -- printed to console and saved to
        outputs/esg_data_report.txt by report.py.
    """
    cache_file = config.CACHE_DIR / "esg_raw.json"
    if use_cache and cache_file.exists():
        with open(cache_file) as f:
            raw = json.load(f)
        if set(tickers).issubset(raw.keys()):
            print(f"[data_fetch] Using cached ESG data from {cache_file}")
        else:
            raw = None
    else:
        raw = None

    if raw is None:
        raw = {}
        for t in tickers:
            full = _try_full_sustainability(t)
            raw[t] = {"full": full}
            time.sleep(0.05)  # be polite to Yahoo's endpoint
        with open(cache_file, "w") as f:
            json.dump(raw, f, indent=2)

    n = len(tickers)
    have_full = [t for t in tickers if raw.get(t, {}).get("full") is not None]
    missing_full = [t for t in tickers if t not in have_full]
    missing_frac = len(missing_full) / n if n else 0.0

    report = {
        "n_tickers": n,
        "n_with_full_esg": len(have_full),
        "n_missing_full_esg": len(missing_full),
        "missing_full_esg_tickers": missing_full,
        "fallback_triggered": False,
        "source_used": "full_esg",
        "notes": [],
    }

    rows = []

    if missing_frac <= config.ESG_MISSING_FALLBACK_THRESHOLD and have_full:
        # Enough real E/S/G coverage: use it, and simply drop names with no
        # score (matches the assignment's instruction to report drops
        # explicitly rather than silently excluding names).
        for t in have_full:
            rows.append({"ticker": t, "esg_score": raw[t]["full"]["total_esg_raw"], "esg_source": "full_esg"})
        for t in missing_full:
            report["notes"].append(f"{t}: dropped from ESG screen - no full ESG score available from yfinance.")
        report["fallback_triggered"] = False
    else:
        # Full ESG data is too sparse to be usable at all (this is what we
        # actually observed for this universe: 0/28 names had a populated
        # Ticker.sustainability frame -- Yahoo's ESG module returns HTTP 404
        # for effectively every ticker as of this build). Fall back to the
        # governance-risk proxy, computed for every ticker independently.
        report["fallback_triggered"] = True
        report["source_used"] = "governance_risk_proxy"
        report["notes"].append(
            f"{len(missing_full)}/{n} names ({missing_frac:.0%}) had no full ESG score from "
            "yfinance (Ticker.sustainability empty / HTTP 404 on Yahoo's quoteSummary ESG "
            "module). Falling back to a GOVERNANCE-ONLY proxy score built from "
            "Ticker.info risk sub-scores (auditRisk, boardRisk, compensationRisk, "
            "shareHolderRightsRisk, overallRisk). This is real live data, but it is NOT "
            "a full Environmental+Social+Governance score -- see README.md limitations."
        )

        gov_cache_file = config.CACHE_DIR / "governance_raw.json"
        if use_cache and gov_cache_file.exists():
            with open(gov_cache_file) as f:
                gov_raw = json.load(f)
        else:
            gov_raw = {}
            for t in tickers:
                gov_raw[t] = _try_governance_proxy(t)
                time.sleep(0.05)
            with open(gov_cache_file, "w") as f:
                json.dump(gov_raw, f, indent=2)

        dropped_no_governance = []
        for t in tickers:
            g = gov_raw.get(t)
            if g is None or g.get("overallRisk") is None:
                dropped_no_governance.append(t)
                continue
            # overallRisk: 1 (best/lowest risk) .. 10 (worst/highest risk).
            # Composite of the four sub-risk scores where available, else
            # just overallRisk. Inverted (11 - risk) so higher = better,
            # matching the convention of the real ESG score above.
            sub_scores = [g.get(k) for k in ["auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk"]]
            sub_scores = [s for s in sub_scores if s is not None]
            composite_risk = np.mean(sub_scores) if sub_scores else g["overallRisk"]
            proxy_score = 11 - composite_risk  # rescale: higher = better governance
            rows.append({"ticker": t, "esg_score": proxy_score, "esg_source": "governance_risk_proxy"})

        for t in dropped_no_governance:
            report["notes"].append(f"{t}: dropped from ESG screen - no governance-risk data available either.")

    esg_df = pd.DataFrame(rows)
    return esg_df, report


# ---------------------------------------------------------------------------
# Market capitalization (for the cap-weighted benchmark)
# ---------------------------------------------------------------------------
def fetch_market_caps(tickers, use_cache=True):
    """
    Current market capitalization per ticker, used as static weights for the
    cap-weighted benchmark. NOTE: this is a live snapshot (today's market
    cap), not a historical time series of float-adjusted index weights --
    see README.md for why, and what that simplification means.
    """
    cache_file = config.CACHE_DIR / "market_caps.json"
    if use_cache and cache_file.exists():
        with open(cache_file) as f:
            caps = json.load(f)
        if set(tickers).issubset(caps.keys()):
            return {t: caps[t] for t in tickers}

    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).info.get("marketCap")
        except Exception:
            caps[t] = None
        time.sleep(0.05)

    with open(cache_file, "w") as f:
        json.dump(caps, f, indent=2)
    return caps
