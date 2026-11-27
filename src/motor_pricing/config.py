import math
from pathlib import Path

import yaml

from motor_pricing.analytical import validate_claim_inputs, validate_loadings
from motor_pricing.models import Driver, Loadings, Portfolio, SimulationSettings

MIN_POLICY_YEARS = 10_000


def load_portfolio(path: Path) -> Portfolio:
    raw = _read_config(path)

    loadings_raw = raw.get("loadings")
    drivers_raw = raw.get("drivers")
    if not isinstance(loadings_raw, dict):
        raise TypeError(f"{path} is missing a 'loadings' mapping")
    if not isinstance(drivers_raw, list):
        raise TypeError(f"{path} is missing a 'drivers' list")
    if not drivers_raw:
        raise ValueError(f"{path} must include at least one driver")

    loadings = Loadings(
        expense=_require_number(loadings_raw, "expense", "loadings"),
        risk_profit=_require_number(loadings_raw, "risk_profit", "loadings"),
    )
    try:
        validate_loadings(loadings)
    except ValueError as exc:
        raise ValueError(f"loadings: {exc}") from exc
    drivers = tuple(_driver(item) for item in drivers_raw)
    return Portfolio(drivers=drivers, loadings=loadings)


def load_simulation_settings(path: Path) -> SimulationSettings:
    raw = _read_config(path).get("simulation")
    if not isinstance(raw, dict):
        raise TypeError(f"{path} is missing a 'simulation' mapping")

    seed = _require_int(raw.get("seed"), "simulation.seed")
    policy_years = _require_int(raw.get("policy_years"), "simulation.policy_years")
    severity_cv = _require_number(raw, "severity_cv", "simulation")
    if seed < 0:
        raise ValueError("simulation.seed must be zero or positive")
    if policy_years < MIN_POLICY_YEARS:
        raise ValueError(f"simulation.policy_years must be at least {MIN_POLICY_YEARS}")
    if severity_cv <= 0:
        raise ValueError("simulation.severity_cv must be positive")
    return SimulationSettings(seed=seed, policy_years=policy_years, severity_cv=severity_cv)


def _read_config(path: Path) -> dict[str, object]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise TypeError(f"{path} must contain a mapping")
    return raw


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


_DRIVER_FIELDS = ("name", "age", "experience", "car_type", "area", "lambda", "severity")


def _driver(item: object) -> Driver:
    if not isinstance(item, dict):
        raise TypeError("each driver must be a mapping")
    name = item.get("name", "<unnamed>")
    missing = [field for field in _DRIVER_FIELDS if field not in item]
    if missing:
        listed = ", ".join(repr(field) for field in missing)
        raise ValueError(f"driver {name!r} is missing {listed}")

    driver = Driver(
        name=str(item["name"]),
        age=_require_int_field(item["age"], f"driver {name!r} field 'age'"),
        experience=_require_int_field(item["experience"], f"driver {name!r} field 'experience'"),
        car_type=str(item["car_type"]),
        area=str(item["area"]),
        claim_frequency=_require_number(item, "lambda", f"driver {name!r}"),
        severity=_require_number(item, "severity", f"driver {name!r}"),
    )
    try:
        validate_claim_inputs(driver.claim_frequency, driver.severity)
    except ValueError as exc:
        raise ValueError(f"driver {driver.name!r}: {exc}") from exc
    return driver


def _require_number(mapping: dict[str, object], key: str, label: str) -> float:
    if key not in mapping:
        raise ValueError(f"{label} is missing '{key}'")
    value = mapping[key]
    field = f"{label} field '{key}'" if label.startswith("driver") else f"{label}.{key}"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number, got {value!r}")
    return number


def _require_int_field(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer, got {value!r}")
    return value
