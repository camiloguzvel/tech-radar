from datetime import date

import pytest
from pydantic import ValidationError

from radar.connectors.openalex import search_expression, works_filter
from radar.domains.loader import ScienceDef, load_domains


def test_topic_rule_filter():
    science = ScienceDef(
        rule="topic", topics=[{"id": "T1", "name": "a"}, {"id": "T2", "name": "b"}]
    )
    assert works_filter(science, types=()) == "primary_topic.id:T1|T2"


def test_topic_keyword_filter_with_dates_and_types():
    science = ScienceDef(
        rule="topic+keyword",
        topics=[{"id": "T11869", "name": "PFAS"}],
        keywords_any=["removal", "reverse osmosis", "plant growth-promoting"],
    )
    assert works_filter(science, since=date(2014, 1, 1), until=date(2026, 10, 19)) == (
        "primary_topic.id:T11869,"
        'title_and_abstract.search:(removal OR "reverse osmosis" OR "plant growth-promoting"),'
        "from_publication_date:2014-01-01,to_publication_date:2026-10-19,"
        "type:article|review|preprint"
    )


def test_keyword_groups_are_anded():
    science = ScienceDef(rule="keyword", keyword_groups=[["dsRNA"], ["spray", "crop protection"]])
    assert search_expression(science) == '(dsRNA) AND (spray OR "crop protection")'


def test_unresolved_topic_rejected_in_filter():
    science = ScienceDef(rule="topic", topics=[{"name": "sin id"}])
    with pytest.raises(ValueError, match="sin resolver"):
        works_filter(science)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rule": "topic"}, "requiere topics"),
        ({"rule": "topic+keyword", "topics": [{"id": "T1", "name": "a"}]}, "requiere keywords"),
        (
            {"rule": "keyword", "keywords_any": ["a"], "topics": [{"id": "T1", "name": "a"}]},
            "no usa topics",
        ),
        ({"rule": "keyword", "keywords_any": ["a"], "keyword_groups": [["b"]]}, "no ambos"),
    ],
)
def test_science_rule_validation(kwargs, message):
    with pytest.raises(ValidationError, match=message):
        ScienceDef(**kwargs)


def test_all_pilot_frentes_build_filters():
    for domain in load_domains().values():
        assert not domain.unresolved_topics()
        for frente in domain.frentes:
            assert works_filter(frente.science)
