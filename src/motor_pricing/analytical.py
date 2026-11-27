import math

from motor_pricing.models import Driver, Loadings, Portfolio, Quote


def expected_annual_claims(claim_frequency: float, severity: float) -> float:
    """Expected annual claims cost.

    Claim count N is Poisson(claim_frequency), so E[N] = claim_frequency and
    the expected cost is E[N] * severity.
    """
    frequency, mean_severity = validate_claim_inputs(claim_frequency, severity)
    return frequency * mean_severity


def annual_premium(expected_claims: float, loadings: Loadings) -> float:
    """Premium after multiplicative expense and risk/profit loadings.

    premium = expected_claims * (1 + expense) * (1 + risk_profit)
    """
    claims = _require_finite(expected_claims, "expected claims")
    if claims < 0:
        raise ValueError(f"expected claims must be zero or positive, got {claims}")
    validate_loadings(loadings)
    return claims * (1 + loadings.expense) * (1 + loadings.risk_profit)


def validate_claim_inputs(claim_frequency: float, severity: float) -> tuple[float, float]:
    frequency = _require_finite(claim_frequency, "claim frequency")
    mean_severity = _require_finite(severity, "severity")
    if frequency < 0:
        raise ValueError(f"claim frequency must be zero or positive, got {frequency}")
    if mean_severity <= 0:
        raise ValueError(f"severity must be positive, got {mean_severity}")
    return frequency, mean_severity


def validate_loadings(loadings: Loadings) -> None:
    """Reject loadings that would make the premium factor zero or negative.

    The premium multiplies by (1 + expense) and (1 + risk/profit). It does not
    divide by (1 - expense - risk/profit), so loadings that sum to more than
    one are still valid.
    """
    for label, value in (
        ("expense loading", loadings.expense),
        ("risk/profit loading", loadings.risk_profit),
    ):
        number = _require_finite(value, label)
        if number <= -1:
            raise ValueError(
                f"{label} of {number} is impossible: the premium multiplies by "
                "(1 + loading), which would not be positive"
            )


def _require_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a finite number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    return float(value)


def price_driver(driver: Driver, loadings: Loadings) -> Quote:
    claims = expected_annual_claims(driver.claim_frequency, driver.severity)
    return Quote(
        driver=driver,
        expected_claims=claims,
        premium=annual_premium(claims, loadings),
    )


def price_portfolio(portfolio: Portfolio) -> tuple[Quote, ...]:
    return tuple(price_driver(driver, portfolio.loadings) for driver in portfolio.drivers)
