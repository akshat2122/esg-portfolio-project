"""
config.py
=========
Central configuration for the ESG-tilted vs. mean-variance portfolio project.

Everything that a reader might reasonably want to change (universe, dates,
constraints, assumptions) lives here so the rest of the codebase never
hardcodes a "magic number".
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CACHE_DIR = PROJECT_ROOT / "data_cache"
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Universe: 28 SBF 120 constituents across 11 GICS-style sectors.
#
# Tickers use the ".PA" (Euronext Paris) suffix expected by Yahoo Finance /
# yfinance. The list was deliberately built wider than the 20-30 target so
# that the automatic "at least 3 years of price history" filter in
# data_fetch.py has real names to exclude if Yahoo's data for a given ticker
# turns out to be short or broken -- nothing here is pre-filtered by hand.
# ---------------------------------------------------------------------------
UNIVERSE = {
    # ticker: (company name, sector)
    "BNP.PA":  ("BNP Paribas",              "Financials"),
    "GLE.PA":  ("Societe Generale",         "Financials"),
    "ACA.PA":  ("Credit Agricole",          "Financials"),
    "CS.PA":   ("AXA",                      "Financials"),

    "DG.PA":   ("Vinci",                    "Industrials"),
    "SAF.PA":  ("Safran",                   "Industrials"),
    "AIR.PA":  ("Airbus",                   "Industrials"),
    "SU.PA":   ("Schneider Electric",       "Industrials"),

    "MC.PA":   ("LVMH",                     "Consumer Discretionary"),
    "KER.PA":  ("Kering",                   "Consumer Discretionary"),
    "RMS.PA":  ("Hermes International",     "Consumer Discretionary"),
    "RNO.PA":  ("Renault",                  "Consumer Discretionary"),

    "BN.PA":   ("Danone",                   "Consumer Staples"),
    "CA.PA":   ("Carrefour",                "Consumer Staples"),
    "RI.PA":   ("Pernod Ricard",            "Consumer Staples"),
    "OR.PA":   ("L'Oreal",                  "Consumer Staples"),

    "SAN.PA":  ("Sanofi",                   "Health Care"),
    "EL.PA":   ("EssilorLuxottica",         "Health Care"),

    "ENGI.PA": ("Engie",                    "Utilities"),
    "VIE.PA":  ("Veolia Environnement",     "Utilities"),

    "TTE.PA":  ("TotalEnergies",            "Energy"),

    "AI.PA":   ("Air Liquide",              "Materials"),
    "SGO.PA":  ("Saint-Gobain",             "Materials"),

    "CAP.PA":  ("Capgemini",                "Technology"),
    "DSY.PA":  ("Dassault Systemes",        "Technology"),

    "PUB.PA":  ("Publicis Groupe",          "Communication Services"),
    "ORA.PA":  ("Orange",                   "Communication Services"),

    "LI.PA":   ("Klepierre",                "Real Estate"),
}

# ---------------------------------------------------------------------------
# Data window
# ---------------------------------------------------------------------------
HISTORY_PERIOD = "5y"          # passed straight to yfinance
MIN_YEARS_HISTORY = 3.0        # names with less real price history are dropped
TRADING_DAYS_PER_YEAR = 252

# Out-of-sample split: the last 12 months of the 5y window are held out as
# the test set; everything before that is the training set the optimizer
# sees. See README.md for the reasoning.
TEST_WINDOW_YEARS = 1.0

# ---------------------------------------------------------------------------
# ESG data
# ---------------------------------------------------------------------------
# Fraction of the universe that may be missing a *full* E/S/G score (via
# yfinance's Ticker.sustainability) before we fall back to the governance-risk
# proxy described in README.md. Set low on purpose: we want the fallback to
# trigger and be reported rather than silently produce an empty Portfolio B.
ESG_MISSING_FALLBACK_THRESHOLD = 0.40
ESG_BOTTOM_QUARTILE = 0.25      # fraction excluded from Portfolio B's universe

# ---------------------------------------------------------------------------
# Optimization constraints (applied identically to Portfolio A and B)
# ---------------------------------------------------------------------------
MAX_WEIGHT_PER_NAME = 0.20
MAX_WEIGHT_PER_SECTOR = 0.35
MIN_WEIGHT_PER_NAME = 0.0       # long-only

# Annual risk-free rate used in Sharpe-ratio calculations. There is no
# single "right" number here; ~2.5% is roughly in line with recent
# short-term euro-area rates (e.g. the ECB deposit facility / €STR) at the
# time this project was built. Change it here if you have a better estimate.
RISK_FREE_RATE_ANNUAL = 0.025

RANDOM_SEED = 42
