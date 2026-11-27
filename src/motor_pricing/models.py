from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Driver:
    name: str
    age: int
    experience: int
    car_type: str
    area: str
    claim_frequency: float
    severity: float


@dataclass(frozen=True, slots=True)
class Loadings:
    expense: float
    risk_profit: float


@dataclass(frozen=True, slots=True)
class Portfolio:
    drivers: tuple[Driver, ...]
    loadings: Loadings


@dataclass(frozen=True, slots=True)
class Quote:
    driver: Driver
    expected_claims: float
    premium: float


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    seed: int
    policy_years: int
    severity_cv: float


@dataclass(frozen=True, slots=True)
class LossSummary:
    driver_name: str
    mean_annual_loss: float
    median: float
    percentile_90: float
    percentile_99: float
    probability_no_claims: float
    probability_exceeds_premium: float
