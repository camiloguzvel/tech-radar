import pytest

from radar.domains.loader import load_domains
from radar.evals.criteria import CRITERIA
from radar.evals.llm_labeler import Batch, instruction, schema
from radar.evals.metrics import wilson
from radar.evals.paper_sets import adjacent_filter


def test_wilson_interval():
    lo, hi = wilson(8, 8)
    assert hi == pytest.approx(1.0) and lo == pytest.approx(0.676, abs=0.01)
    assert wilson(0, 0) == (None, None)
    lo, hi = wilson(4, 8)
    assert lo < 0.5 < hi


def test_every_focus_frente_has_criteria_and_adjacent_filter():
    for d in load_domains().values():
        if d.role != "thesis":
            continue
        for f in d.frentes:
            assert f.id in CRITERIA, f.id
            assert "publication_year:2016-2025" in adjacent_filter(f)
            assert f.name in instruction(d, f.id)


def test_label_schema_accepts_only_known_frentes():
    s = schema(["a", "b"])
    enum = s["properties"]["labels"]["items"]["properties"]["frente_correcto"]["enum"]
    assert enum == ["a", "b", "otro_dominio", "ninguno", None]
    ok = Batch.model_validate(
        {"labels": [{"n": 1, "pertenece": "si", "frente_correcto": None, "justificacion": "x"}]}
    )
    assert ok.labels[0].pertenece == "si"
