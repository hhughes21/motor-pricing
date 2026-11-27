import math
from dataclasses import dataclass

import numpy as np

from motor_pricing.analytical import validate_claim_inputs
from motor_pricing.models import Quote, SimulationSettings


@dataclass(frozen=True, slots=True)
class SimulatedYearLosses:
    quote: Quote
    claim_counts: np.ndarray
    losses: np.ndarray


def lognormal_parameters(mean: float, cv: float) -> tuple[float, float]:
    """mu and sigma for a lognormal with this mean and coefficient of variation.

    sigma = sqrt(log(1 + cv^2)) and mu = log(mean) - sigma^2/2, so E[X] = mean and
    SD(X) = cv * mean. The inputs give the mean only, so cv is an assumption.
    """
    sigma = math.sqrt(math.log(1 + cv * cv))
    mu = math.log(mean) - 0.5 * sigma * sigma
    return mu, sigma


def simulate_annual_losses(
    claim_frequency: float,
    severity: float,
    severity_cv: float,
    n_years: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate one claims total per policy-year.

    The claim count is Poisson(claim_frequency). Each claim cost is lognormal
    with mean `severity` and coefficient of variation `severity_cv`.
    A year with no claims costs zero.
    """
    claim_frequency, severity = validate_claim_inputs(claim_frequency, severity)
    if isinstance(severity_cv, bool) or not isinstance(severity_cv, (int, float)):
        raise TypeError(f"severity coefficient of variation must be a number, got {severity_cv!r}")
    if not math.isfinite(severity_cv) or severity_cv <= 0:
        raise ValueError(
            f"severity coefficient of variation must be positive and finite, got {severity_cv}"
        )
    claim_counts = rng.poisson(claim_frequency, size=n_years)
    total_claims = int(claim_counts.sum())
    if total_claims == 0:
        return claim_counts, np.zeros(n_years, dtype=float)

    mu, sigma = lognormal_parameters(severity, float(severity_cv))
    claim_costs = rng.lognormal(mu, sigma, size=total_claims)
    losses = np.array(
        [costs.sum() for costs in np.split(claim_costs, np.cumsum(claim_counts)[:-1])],
        dtype=float,
    )
    return claim_counts, losses


def simulate_quotes(
    quotes: tuple[Quote, ...],
    settings: SimulationSettings,
) -> tuple[SimulatedYearLosses, ...]:
    """Simulate each quote from its own stream of the project seed."""
    sequences = np.random.SeedSequence(settings.seed).spawn(len(quotes))
    simulated = []
    for quote, sequence in zip(quotes, sequences, strict=True):
        rng = np.random.default_rng(sequence)
        claim_counts, losses = simulate_annual_losses(
            quote.driver.claim_frequency,
            quote.driver.severity,
            settings.severity_cv,
            settings.policy_years,
            rng,
        )
        simulated.append(
            SimulatedYearLosses(
                quote=quote,
                claim_counts=claim_counts,
                losses=losses,
            )
        )
    return tuple(simulated)
