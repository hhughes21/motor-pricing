import argparse
from pathlib import Path

from motor_pricing.analytical import price_portfolio
from motor_pricing.config import load_portfolio, load_simulation_settings
from motor_pricing.metrics import summarize_losses, summary_frame
from motor_pricing.simulation import simulate_quotes


def main() -> None:
    parser = argparse.ArgumentParser(description="Price motor policies from a driver config.")
    parser.add_argument(
        "config",
        nargs="?",
        default="config/drivers.yaml",
        type=Path,
        help="path to the drivers YAML (default: config/drivers.yaml)",
    )
    args = parser.parse_args()

    portfolio = load_portfolio(args.config)
    settings = load_simulation_settings(args.config)
    quotes = price_portfolio(portfolio)
    simulated = simulate_quotes(quotes, settings)
    summaries = tuple(
        summarize_losses(run.quote.driver.name, run.quote.premium, run.claim_counts, run.losses)
        for run in simulated
    )
    frame = summary_frame(quotes, summaries)

    print("motor-pricing engine")
    print()
    print(f"Expense loading: {portfolio.loadings.expense}")
    print(f"Risk/profit loading: {portfolio.loadings.risk_profit}")
    print(f"Monte Carlo: {settings.policy_years} policy-years per driver, seed {settings.seed}")
    print(
        "Claim counts are Poisson. Each claim cost is lognormal with the driver's mean severity "
        f"and coefficient of variation {settings.severity_cv}."
    )
    print()
    print(frame.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print()
    print("Currency in CHF")
