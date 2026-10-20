import zipfile

import pytest

from radar.domains.cpc import CpcScheme, FrenteCpcMatcher, canonical
from radar.domains.loader import Frente

# Extracto con la forma real del CPCTitleList: símbolo<TAB>nivel<TAB>título, en orden.
TITLE_LIST = """C02F\t\tTREATMENT OF WATER
C02F1/00\t0\tTreatment of water
C02F1/28\t1\tby sorption
C02F1/42\t1\tby ion-exchange
C02F1/44\t1\tby dialysis, osmosis or reverse osmosis
C02F1/441\t2\t{by reverse osmosis}
C02F1/4418\t3\t{deeper}
C02F1/442\t2\t{by nanofiltration}
C02F1/46\t1\tby electrochemical methods
C02F3/00\t0\tBiological treatment
B01D\t\tSEPARATION
B01D69/00\t0\tSemi-permeable membranes
B01D69/02\t1\tcharacterised by their properties
B01D71/00\t0\tSemi-permeable membranes by material
"""

SCIENCE = {"rule": "keyword", "keywords_any": ["x"]}


@pytest.fixture
def scheme(tmp_path):
    path = tmp_path / "titles.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("cpc-section-C.txt", TITLE_LIST)
    return CpcScheme.from_title_list(path)


def test_canonical_main_group():
    assert canonical("B01J20") == "B01J20/00"
    assert canonical("C02F1/44") == "C02F1/44"
    assert canonical("A01P") == "A01P"


def test_expand_uses_levels_not_text_prefix(scheme):
    assert scheme.expand("C02F1/44") == {"C02F1/44", "C02F1/441", "C02F1/4418", "C02F1/442"}
    # C02F1/4 sería prefijo de C02F1/42 y C02F1/46, pero no son descendientes de C02F1/44
    assert "C02F1/42" not in scheme.expand("C02F1/44")


def test_expand_main_group_and_subclass(scheme):
    assert scheme.expand("C02F1") >= {"C02F1/28", "C02F1/46", "C02F1/4418"}
    assert "C02F3/00" not in scheme.expand("C02F1")
    assert "C02F3/00" in scheme.expand("C02F")


def test_expand_unknown_code_raises(scheme):
    with pytest.raises(KeyError):
        scheme.expand("C02F9/99")


def test_matcher_any_and_qualified(scheme):
    frente = Frente(
        id="desal",
        name="d",
        rule="cpc",
        cpc_any=["C02F1/44"],
        cpc_qualified=[{"codes": ["B01D69"], "with_any": ["C02F"]}],
        science=SCIENCE,
    )
    m = FrenteCpcMatcher(frente, scheme)
    assert m.matches({"C02F1/4418"})  # descendiente de cpc_any
    assert not m.matches({"B01D69/02"})  # membrana sin contexto de agua
    assert m.matches({"B01D69/02", "C02F3/00"})  # membrana + tratamiento de agua
    assert not m.matches({"C02F1/28"})
