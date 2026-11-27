import numpy as np
import pandas as pd

from motor_pricing.models import LossSummary, Quote

SUMMARY_COLUMNS = (
    "driver",
    "expected_claims",
    "expected_severity",
    "expected_cost",
    "premium",
    "sim_mean",
    "sim_median",
    "p90",
    "p99",
    "prob_no_claims",
    "prob_exceeds_premium",
)

_PERCENTILE_90 = 0.90
_PERCENTILE_99 = 0.99


def summarize_losses(
    driver_name: str,
    premium: float,
    claim_counts: np.ndarray,
    losses: np.ndarray,
) -> LossSummary:
    if claim_counts.shape != losses.shape:
        raise ValueError("claim counts and losses must have the same shape")
    if claim_counts.size == 0:
        raise ValueError("at least one policy-year is required")

    return LossSummary(
        driver_name=driver_name,
        mean_annual_loss=float(losses.mean()),
        median=float(np.median(losses)),
        percentile_90=float(np.quantile(losses, _PERCENTILE_90)),
        percentile_99=float(np.quantile(losses, _PERCENTILE_99)),
        probability_no_claims=float(np.mean(claim_counts == 0)),
        probability_exceeds_premium=float(np.mean(losses > premium)),
    )


def summary_frame(quotes: tuple[Quote, ...], summaries: tuple[LossSummary, ...]) -> pd.DataFrame:
    """One row per driver. This is the priced summary, not the simulated years."""
    if len(quotes) != len(summaries):
        raise ValueError("each quote needs one loss summary")

    rows = []
    for quote, summary in zip(quotes, summaries, strict=True):
        if quote.driver.name != summary.driver_name:
            raise ValueError(
                f"quote for {quote.driver.name!r} does not match summary for {summary.driver_name!r}"
            )
        driver = quote.driver
        rows.append(
            {
                "driver": driver.name,
                "expected_claims": driver.claim_frequency,
                "expected_severity": driver.severity,
                "expected_cost": quote.expected_claims,
                "premium": quote.premium,
                "sim_mean": summary.mean_annual_loss,
                "sim_median": summary.median,
                "p90": summary.percentile_90,
                "p99": summary.percentile_99,
                "prob_no_claims": summary.probability_no_claims,
                "prob_exceeds_premium": summary.probability_exceeds_premium,
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
