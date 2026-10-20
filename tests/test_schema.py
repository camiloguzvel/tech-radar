from datetime import date, datetime

import pytest
from pydantic import ValidationError

from radar.core.schema import Family, Observation, stable_id


def _family(**overrides):
    base = dict(
        family_id="F1",
        earliest_priority_date=date(2022, 1, 1),
        first_pub_date=date(2023, 7, 1),
        offices=frozenset({"CN"}),
        has_pct=False,
        only_utility_models=False,
    )
    return Family(**(base | overrides))


def test_stable_id_is_deterministic():
    assert stable_id("agua", 2024, "Q1") == stable_id("agua", 2024, "Q1")
    assert stable_id("agua", 2024) != stable_id("agua", 2025)


def test_international_lens():
    assert not _family().is_international
    assert _family(offices=frozenset({"CN", "US"})).is_international
    assert _family(offices=frozenset({"CN", "WO"}), has_pct=True).is_international
    assert not _family(offices=frozenset({"CN", "DE"})).is_international  # DE no es IP5


def test_country_weights_must_sum_to_one():
    _family(applicant_country_weights={"CN": 0.5, "US": 0.5})
    with pytest.raises(ValidationError, match="deben sumar 1"):
        _family(applicant_country_weights={"CN": 0.5})


def test_observation_rejects_inverted_period():
    with pytest.raises(ValidationError):
        Observation(
            observation_id="o",
            period_start=date(2024, 4, 1),
            period_end=date(2024, 1, 1),
            granularity="Q",
            layer="patent",
            domain="agua",
            geo_type="global",
            geo="world",
            lens="all",
            variable="families",
            value=1,
            n_basis=1,
            provisional=False,
            source="epo_ops",
            method_version="0.1",
            run_id="r",
            computed_at=datetime(2026, 10, 19),
        )
