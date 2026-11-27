import math
from pathlib import Path

import numpy as np
import pytest

from motor_pricing.analytical import annual_premium, price_driver, price_portfolio
from motor_pricing.config import load_portfolio
from motor_pricing.models import Driver, Loadings, SimulationSettings
from motor_pricing.simulation import simulate_annual_losses, simulate_quotes

# Project loadings: premium = expected claims * (1 + expense) * (1 + risk/profit).
LOADINGS = Loadings(expense=0.2, risk_profit=0.1)
LOADING_FACTOR = (1 + LOADINGS.expense) * (1 + LOADINGS.risk_profit)
POLICY_YEARS = 10_000
CONVERGENCE_YEARS = 100_000
SEED = 20261125
SEVERITY_CV = 1.0
PORTFOLIO = load_portfolio(Path(__file__).resolve().parents[1] / "config" / "drivers.yaml")


def _driver(frequency: float, severity: float) -> Driver:
    return Driver(
        name="T",
        age=40,
        experience=10,
        car_type="family car",
        area="rural",
        claim_frequency=frequency,
        severity=severity,
    )


def _settings(policy_years: int) -> SimulationSettings:
    return SimulationSettings(seed=SEED, policy_years=policy_years, severity_cv=SEVERITY_CV)


def _annual_loss_sd(frequency: float, severity: float) -> float:
    """Standard deviation of one compound Poisson-lognormal year.

    Claim size has mean `severity` and coefficient of variation 1, so its
    second moment is 2 * severity**2. A compound Poisson sum has variance
    frequency times that second moment.
    """
    return severity * math.sqrt(frequency * (1 + SEVERITY_CV**2))


# 1. A claim rate of 0.1 and an average claim of 8,000, with the 20% and 10% loadings.
# The expected cost should be 800 and the premium 800 x 1.2 x 1.1, the same sum done by hand.
def test_known_values_match_a_hand_calculation() -> None:
    quote = price_driver(_driver(frequency=0.1, severity=8_000), LOADINGS)

    assert quote.expected_claims == 800
    assert quote.premium == 800 * (1 + LOADINGS.expense) * (1 + LOADINGS.risk_profit)
    assert quote.premium / quote.expected_claims == LOADING_FACTOR


# 2. A claim rate of zero should cost nothing: expected cost 0, premium 0, and no simulated claims.
def test_zero_frequency_has_zero_cost_and_no_claims() -> None:
    quote = price_driver(_driver(frequency=0, severity=8_000), LOADINGS)
    simulated = simulate_quotes(
        (quote,),
        _settings(POLICY_YEARS),
    )[0]

    assert quote.expected_claims == 0
    assert quote.premium == 0
    assert simulated.claim_counts.shape == (POLICY_YEARS,)
    assert np.all(simulated.claim_counts == 0)
    assert np.all(simulated.losses == 0)


# 3. Over 100,000 years with a fixed seed, the average loss should land within 3 standard errors of 800.
def test_simulated_mean_is_within_three_standard_errors() -> None:
    quote = price_driver(_driver(frequency=0.1, severity=8_000), LOADINGS)
    simulated = simulate_quotes(
        (quote,),
        _settings(CONVERGENCE_YEARS),
    )[0]
    tolerance = 3 * _annual_loss_sd(quote.driver.claim_frequency, quote.driver.severity) / math.sqrt(
        CONVERGENCE_YEARS
    )

    assert quote.expected_claims == 800
    assert abs(float(simulated.losses.mean()) - quote.expected_claims) < tolerance


# 4. At a claim rate of 0.1, the share of years with no claim should be close to e^(-0.1), about 0.905.
def test_probability_of_no_claims_matches_the_poisson_formula() -> None:
    frequency = 0.1
    analytical = math.exp(-frequency)
    tolerance = 3 * math.sqrt(analytical * (1 - analytical)) / math.sqrt(CONVERGENCE_YEARS)
    claim_counts, _losses = simulate_annual_losses(
        claim_frequency=frequency,
        severity=8_000,
        severity_cv=SEVERITY_CV,
        n_years=CONVERGENCE_YEARS,
        rng=np.random.default_rng(SEED),
    )

    assert analytical == pytest.approx(0.905, abs=0.001)
    assert abs(float(np.mean(claim_counts == 0)) - analytical) < tolerance


# 5. The same seed should repeat the same years. A different seed should not.
def test_same_seed_matches_and_a_different_seed_does_not() -> None:
    quote = price_driver(_driver(frequency=0.1, severity=8_000), LOADINGS)
    first = simulate_quotes((quote,), _settings(POLICY_YEARS))[0]
    second = simulate_quotes((quote,), _settings(POLICY_YEARS))[0]
    other_seed = SimulationSettings(seed=SEED + 1, policy_years=POLICY_YEARS, severity_cv=SEVERITY_CV)
    other = simulate_quotes((quote,), other_seed)[0]

    np.testing.assert_array_equal(first.claim_counts, second.claim_counts)
    np.testing.assert_array_equal(first.losses, second.losses)
    assert not np.array_equal(first.losses, other.losses)


# 6. A negative claim rate, a claim size of zero, or a missing number should raise ValueError.
def test_invalid_claim_inputs_raise_value_error() -> None:
    invalid_inputs = (
        (-0.1, 8_000, "claim frequency"),
        (0.1, 0, "severity"),
        (float("nan"), 8_000, "claim frequency"),
        (0.1, float("nan"), "severity"),
    )
    for frequency, severity, message in invalid_inputs:
        with pytest.raises(ValueError, match=message):
            price_driver(_driver(frequency, severity), LOADINGS)


# 7. A loading of -100% or worse is rejected, because the premium would not be positive.
def test_loading_at_or_below_minus_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="would not be positive"):
        annual_premium(800, Loadings(expense=-1, risk_profit=0.1))
    with pytest.raises(ValueError, match="would not be positive"):
        annual_premium(800, Loadings(expense=0.1, risk_profit=-1.5))


# 8. Driver B claims more often and each claim costs more, so B's premium should be higher than A's.
def test_riskier_driver_costs_more() -> None:
    quotes = {quote.driver.name: quote for quote in price_portfolio(PORTFOLIO)}
    driver_a = quotes["A"].driver
    driver_b = quotes["B"].driver

    assert driver_b.claim_frequency > driver_a.claim_frequency
    assert driver_b.severity > driver_a.severity
    assert quotes["B"].premium > quotes["A"].premium
