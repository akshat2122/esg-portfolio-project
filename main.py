"""
main.py
=======
Entry point. Run with:

    python main.py

This will (re-)download data as needed (cached under data_cache/ after the
first run -- delete that folder, or pass --refresh, to force a clean pull),
run the full analysis, and write every deliverable into outputs/:

    outputs/results_table.csv               5-line-item x 4-portfolio scorecard
    outputs/cumulative_returns_chart.png     the 4-line out-of-sample chart
    outputs/weights_portfolio_a.csv          Portfolio A optimized weights
    outputs/weights_portfolio_b.csv          Portfolio B optimized weights
    outputs/universe_and_esg_report.txt      exactly which names were dropped
                                              and why (history + ESG data)
"""

import argparse

import config
import data_fetch
import backtest
import report


def main(refresh=False):
    tickers = list(config.UNIVERSE.keys())
    sector_map = {t: sector for t, (_, sector) in config.UNIVERSE.items()}

    print(f"[main] Candidate universe: {len(tickers)} names across "
          f"{len(set(sector_map.values()))} sectors.")

    # ---- 1. Prices + history filter ------------------------------------
    prices = data_fetch.fetch_prices(tickers, use_cache=not refresh)
    kept_tickers, history_drops = data_fetch.filter_by_min_history(prices)
    if history_drops:
        print(f"[main] Dropping {len(history_drops)} name(s) for insufficient price history: "
              f"{[d['ticker'] for d in history_drops]}")
    prices = prices[kept_tickers].dropna(how="any")
    sector_map = {t: s for t, s in sector_map.items() if t in kept_tickers}

    print(f"[main] Final priced universe: {len(kept_tickers)} names, "
          f"{prices.index.min().date()} to {prices.index.max().date()}.")

    # ---- 2. ESG data -----------------------------------------------------
    esg_df, esg_report = data_fetch.fetch_esg_scores(kept_tickers, use_cache=not refresh)
    print(f"[main] ESG data source used for the bottom-quartile screen: {esg_report['source_used']}")
    for note in esg_report["notes"]:
        print(f"[main]   NOTE: {note}")

    # ---- 3. Market caps (for the cap-weighted benchmark) -----------------
    market_caps = data_fetch.fetch_market_caps(kept_tickers, use_cache=not refresh)

    # ---- 4. Backtest: optimize on years 1-4, test on year 5 -------------
    backtest_output = backtest.run_backtest(prices, sector_map, esg_df, market_caps)
    results = backtest_output["results"]

    # ---- 5. Reports --------------------------------------------------------
    table = report.build_results_table(results)
    report.save_results_table(table)
    report.plot_cumulative_returns(results, backtest_output["test_window"])
    report.save_weights(results)
    report.save_universe_report(backtest_output, config.UNIVERSE, history_drops, esg_report,
                                 sector_map=sector_map, results=results)

    print(f"\n[main] Done. All outputs written to: {config.OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                         help="Ignore any cached data in data_cache/ and re-download everything.")
    args = parser.parse_args()
    main(refresh=args.refresh)
