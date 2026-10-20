from radar.connectors.epo_ops import classification_cql, frente_cql, keyword_cql
from radar.domains.loader import Frente, load_domains

SCIENCE = {"rule": "keyword", "keywords_any": ["x"]}


def test_cpc_rule_uses_combined_classification():
    f = Frente(id="a", name="a", rule="cpc", cpc_any=["E03B3/28"], science=SCIENCE)
    assert frente_cql(f, "20250601", "20250630") == (
        'cl=/low E03B3/28 and pd within "20250601 20250630"'
    )


def test_keyword_and_qualified_cql():
    f = Frente(
        id="a",
        name="a",
        rule="cpc+keyword",
        cpc_any=["C02F1/28"],
        cpc_qualified=[{"codes": ["B01D69", "B01D71"], "with_any": ["C02F"]}],
        keywords_any=["PFAS", "plant growth-promoting"],
        science=SCIENCE,
    )
    assert classification_cql(f) == (
        "(cl=/low C02F1/28 or ((cl=/low B01D69 or cl=/low B01D71) and cl=/low C02F))"
    )
    assert keyword_cql(f) == '(ta=PFAS or ta="plant growth-promoting")'
    assert frente_cql(f, "20250101", "20250131").startswith(
        "(cl=/low C02F1/28 or ((cl=/low B01D69 or cl=/low B01D71) and cl=/low C02F)) and "
        '((ta=PFAS or ta="plant growth-promoting")) and pd within'
    )


def test_or_rule_and_keyword_groups():
    f = Frente(
        id="a",
        name="a",
        rule="cpc|keyword",
        cpc_any=["A01N63/60"],
        keyword_groups=[["dsRNA"], ["spray", "crop"]],
        science=SCIENCE,
    )
    # CQL evalúa and/or de izquierda a derecha con igual precedencia: hacen falta paréntesis
    assert frente_cql(f, "20250101", "20250131") == (
        "(cl=/low A01N63/60 or (ta=dsRNA and (ta=spray or ta=crop))) "
        'and pd within "20250101 20250131"'
    )


def test_all_pilot_frentes_build_cql():
    for domain in load_domains().values():
        for frente in domain.frentes:
            assert "pd within" in frente_cql(frente, "20250101", "20250131")
