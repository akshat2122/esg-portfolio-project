"""
report.py
=========
Turns the backtest results into the deliverables the assignment asks for:
a results table (CSV + console), a cumulative-return chart (PNG), and plain-
text transparency reports on what was excluded from the universe and why.

Chart styling follows a small fixed categorical palette (validated for
colorblind-safety) rather than default matplotlib colors, with direct
end-of-line labels so the lines are identifiable even without the legend.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

import config

# Fixed categorical color assignment -- same order/colors every run, chosen
# from a colorblind-validated 8-hue palette (see dataviz skill reference).
LINE_COLORS = {
    "Portfolio A (Mean-Variance)": "#2a78d6",   # blue
    "Portfolio B (ESG-Tilted)":    "#eb6834",   # orange
    "Equal-Weight Benchmark":      "#1baf7a",   # aqua
    "Cap-Weighted Benchmark":      "#c98500",   # yellow, darkened for contrast on white
}

LINE_ORDER = [
    "Portfolio A (Mean-Variance)",
    "Portfolio B (ESG-Tilted)",
    "Equal-Weight Benchmark",
    "Cap-Weighted Benchmark",
]


def build_results_table(results):
    """One row per line, columns = the five required metrics."""
    rows = {}
    for name in LINE_ORDER:
        rows[name] = results[name]["summary"]
    table = pd.DataFrame(rows).T
    table = table[["Cumulative Return", "Annualized Return", "Annualized Volatility",
                   "Sharpe Ratio", "Max Drawdown"]]
    return table


def save_results_table(table, path=config.OUTPUT_DIR / "results_table.csv"):
    table.to_csv(path, float_format="%.6f")

    pretty = table.copy()
    for col in ["Cumulative Return", "Annualized Return", "Annualized Volatility", "Max Drawdown"]:
        pretty[col] = pretty[col].map(lambda x: f"{x:.2%}")
    pretty["Sharpe Ratio"] = pretty["Sharpe Ratio"].map(lambda x: f"{x:.2f}")
    print("\n=== Out-of-sample performance, year 5 (test window) ===")
    print(pretty.to_string())
    return path


def plot_cumulative_returns(results, test_window, path=config.OUTPUT_DIR / "cumulative_returns_chart.png"):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    for name in LINE_ORDER:
        wealth = results[name]["wealth"]
        # Index to growth of 1 at the start of the test window (already the
        # case from metrics.performance_summary, but re-anchor defensively).
        series = wealth / wealth.iloc[0]
        ax.plot(series.index, series.values, label=name, color=LINE_COLORS[name],
                linewidth=2, solid_capstyle="round")
        ax.annotate(f"  {name.split(' (')[0]}: {series.iloc[-1]:.2f}x",
                    xy=(series.index[-1], series.iloc[-1]),
                    color=LINE_COLORS[name], fontsize=9, va="center",
                    fontweight="bold")

    ax.axhline(1.0, color="#c3c2b7", linewidth=1, linestyle="--", zorder=0)
    ax.set_title("Out-of-Sample Performance -- Year 5 Test Window\n"
                  "Growth of €1 invested at the start of the held-out period",
                  fontsize=13, color="#0b0b0b", loc="left")
    ax.set_xlabel("")
    ax.set_ylabel("Growth of €1", color="#52514e")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2fx"))
    ax.grid(True, axis="y", color="#e5e4df", linewidth=0.8, zorder=-1)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    ax.legend(loc="upper left", frameon=False, fontsize=9)

    start, end = test_window
    fig.text(0.99, 0.01, f"Test window: {start.date()} to {end.date()}",
              ha="right", fontsize=8, color="#8a8981")

    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_weights(results, path_prefix=config.OUTPUT_DIR):
    for name in ["Portfolio A (Mean-Variance)", "Portfolio B (ESG-Tilted)"]:
        w = results[name]["weights"].sort_values(ascending=False).round(6)
        fname = "weights_portfolio_a.csv" if "A" in name.split(" ")[1] else "weights_portfolio_b.csv"
        w[w > 0].to_csv(path_prefix / fname, header=["weight"])


def sector_breakdown(weights, sector_map):
    """Sector weight totals for a portfolio -- used to confirm the 35%
    per-sector cap actually held after optimization."""
    df = pd.DataFrame({"weight": weights})
    df["sector"] = df.index.map(sector_map)
    return df.groupby("sector")["weight"].sum().sort_values(ascending=False)


def save_universe_report(backtest_output, universe, history_drops, esg_report, sector_map=None, results=None, path=config.OUTPUT_DIR / "universe_and_esg_report.txt"):
    lines = []
    lines.append("UNIVERSE CONSTRUCTION AND DATA-QUALITY REPORT")
    lines.append("=" * 60)
    lines.append(f"Candidate SBF 120 names considered: {len(universe)}")
    lines.append("")

    lines.append("-- Price history filter (need >= {:.0f} years) --".format(config.MIN_YEARS_HISTORY))
    if history_drops:
        for d in history_drops:
            lines.append(f"  DROPPED {d['ticker']}: {d['reason']}")
    else:
        lines.append("  No names dropped -- all candidates had sufficient price history.")
    lines.append("")

    lines.append("-- ESG data coverage (yfinance) --")
    lines.append(f"  Names with a full Environmental+Social+Governance score: {esg_report['n_with_full_esg']}/{esg_report['n_tickers']}")
    lines.append(f"  Fallback to governance-risk proxy triggered: {esg_report['fallback_triggered']}")
    lines.append(f"  Score source actually used for the bottom-quartile screen: {esg_report['source_used']}")
    for note in esg_report["notes"]:
        lines.append(f"  NOTE: {note}")
    lines.append("")

    lines.append("-- Portfolio B ESG screen outcome --")
    excluded = backtest_output["esg_excluded_bottom_quartile"]
    unscored = backtest_output["esg_unscored"]
    lines.append(f"  Excluded (bottom {config.ESG_BOTTOM_QUARTILE:.0%} by ESG/governance-proxy score): {excluded if excluded else 'none'}")
    lines.append(f"  Excluded (no ESG score obtainable at all): {unscored if unscored else 'none'}")
    lines.append(f"  Final Portfolio B eligible universe ({len(backtest_output['portfolio_b_universe'])} names): "
                 f"{backtest_output['portfolio_b_universe']}")
    lines.append("")

    lines.append("-- Backtest windows --")
    train_start, train_end = backtest_output["train_window"]
    test_start, test_end = backtest_output["test_window"]
    lines.append(f"  Training window (in-sample, used to fit weights): {train_start.date()} to {train_end.date()}")
    lines.append(f"  Test window (out-of-sample, weights held fixed):  {test_start.date()} to {test_end.date()}")
    lines.append("")

    if sector_map is not None and results is not None:
        lines.append("-- Sector allocation check (cap = {:.0%} per sector) --".format(config.MAX_WEIGHT_PER_SECTOR))
        for name in ["Portfolio A (Mean-Variance)", "Portfolio B (ESG-Tilted)"]:
            lines.append(f"  {name}:")
            sb = sector_breakdown(results[name]["weights"], sector_map)
            for sector, w in sb.items():
                if w > 1e-6:
                    lines.append(f"    {sector:<28s} {w:6.1%}")
        lines.append("")

    text = "\n".join(lines)
    with open(path, "w") as f:
        f.write(text)
    print("\n" + text)
    return path
