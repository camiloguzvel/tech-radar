import pytest
from pydantic import ValidationError

from radar.domains.loader import (
    BacktestEvent,
    Domain,
    Frente,
    load_backtest,
    load_domains,
    load_hubs,
)

SCIENCE = {"rule": "keyword", "keywords_any": ["x"]}


def test_domains_load():
    domains = load_domains()
    assert set(domains) == {"agua", "agrobiotech", "alimentos_biotech", "control"}
    assert domains["control"].role == "calibration"
    for name in ("agua", "agrobiotech"):
        assert domains[name].role == "thesis"
        assert len(domains[name].frentes) >= 3


def test_backtest_window_must_be_within_history():
    event = {
        "id": "e",
        "domain": "agua",
        "frente": "pfas_remocion",
        "description": "d",
        "expected_window": (2010, 2012),
    }
    with pytest.raises(ValidationError, match="antes del histórico"):
        BacktestEvent.model_validate(event)
    with pytest.raises(ValidationError, match="invertida"):
        BacktestEvent.model_validate(event | {"expected_window": (2020, 2018)})


def test_hubs_and_backtest_load():
    hubs = load_hubs()
    assert "eindhoven" in {h.id for h in hubs.hubs}
    backtest = load_backtest(load_domains())
    assert backtest.events


@pytest.mark.parametrize("code", ["C02F", "B01J20", "C02F1/28", "C02F2103/08", "C12R2001"])
def test_valid_cpc_codes(code):
    Frente(id="x", name="x", science=SCIENCE, rule="cpc", cpc_any=[code])


@pytest.mark.parametrize("code", ["c02f1/28", "C2F1/28", "C02F1/", "Z99A1/00", "C02F 1/28"])
def test_invalid_cpc_codes(code):
    with pytest.raises(ValidationError):
        Frente(id="x", name="x", science=SCIENCE, rule="cpc", cpc_any=[code])


def test_keyword_rule_requires_keywords():
    with pytest.raises(ValidationError, match="requiere keywords"):
        Frente(id="x", name="x", science=SCIENCE, rule="cpc+keyword", cpc_any=["C02F1/28"])


def test_rule_requires_cpc():
    with pytest.raises(ValidationError, match="requiere cpc_any"):
        Frente(id="x", name="x", science=SCIENCE, rule="cpc|keyword", keywords_any=["PFAS"])


def test_duplicate_frentes_rejected():
    frente = {"id": "a", "name": "a", "rule": "cpc", "cpc_any": ["C02F"], "science": SCIENCE}
    with pytest.raises(ValidationError, match="duplicados"):
        Domain(domain="d", name="d", version="0", thesis="t", frentes=[frente, frente])


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        Frente(
            id="x",
            name="x",
            science=SCIENCE,
            rule="cpc",
            cpc_any=["C02F"],
            keywords_all_any=[["a"]],
        )
