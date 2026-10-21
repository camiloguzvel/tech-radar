import re
from datetime import date

import pytest

from radar.connectors.epo_ops import QuotaExceeded
from radar.domains.loader import Domain
from radar.ingest import epo_ops_biblio as ing

DOMAIN = Domain.model_validate(
    {
        "domain": "agua",
        "name": "Agua",
        "version": "9",
        "thesis": "t",
        "frentes": [
            {
                "id": "f1",
                "name": "F1",
                "rule": "cpc",
                "cpc_any": ["C02F"],
                "science": {"rule": "keyword", "keywords_any": ["x"]},
            }
        ],
    }
)
FRENTE = DOMAIN.frentes[0]


class FakeOps:
    """Documentos por día; responde como search/biblio con total y rango."""

    def __init__(self, per_day: dict[date, int], quota_after: int | None = None):
        self.per_day = per_day
        self.calls = 0
        self.quota_after = quota_after
        self.week_bytes_used = 0
        self.log: list = []

    def search_biblio(self, cql: str, start: int, end: int) -> dict:
        self.calls += 1
        if self.quota_after is not None and self.calls > self.quota_after:
            raise QuotaExceeded("cuota")
        a, b = re.search(r'pd within "(\d{8}) (\d{8})"', cql).groups()
        lo, hi = (
            date.fromisoformat(f"{a[:4]}-{a[4:6]}-{a[6:]}"),
            date.fromisoformat(f"{b[:4]}-{b[4:6]}-{b[6:]}"),
        )
        docs = [
            {"exchange-document": {"@family-id": f"{d}-{i}"}}
            for d, n in sorted(self.per_day.items())
            if lo <= d <= hi
            for i in range(n)
        ]
        if not docs:
            return {}  # OPS responde 404 => el cliente devuelve {}
        page = docs[start - 1 : end]
        return {
            "ops:world-patent-data": {
                "ops:biblio-search": {
                    "@total-result-count": str(len(docs)),
                    "ops:search-result": {"exchange-documents": page},
                }
            }
        }


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "RAW_ROOT", tmp_path / "raw")
    return tmp_path / "raw"


def test_quarters_cover_range_and_cut_at_today():
    qs = ing.quarters(date(2025, 1, 1), date(2025, 5, 10))
    assert [q[0] for q in qs] == ["2025Q1", "2025Q2"]
    assert qs[0][1:] == (date(2025, 1, 1), date(2025, 3, 31))
    assert qs[1][2] == date(2025, 5, 10)
    assert ing.quarters(date(2024, 10, 1), date(2025, 1, 2))[0][2] == date(2024, 12, 31)


def test_paginates_within_a_window(raw):
    ops = FakeOps({date(2025, 2, 1): 250})
    m = ing.ingest_quarter(ops, DOMAIN, FRENTE, "2025Q1", date(2025, 1, 1), date(2025, 3, 31), "r1")
    assert m["n_documents"] == 250 and m["n_pages"] == 3 and len(m["windows"]) == 1
    assert (raw / "biblio/agua/f1/2025Q1/r1/_SUCCESS.json").exists()


def test_splits_windows_over_2000(raw):
    ops = FakeOps({date(2025, 1, 10): 1500, date(2025, 3, 10): 1500})
    m = ing.ingest_quarter(ops, DOMAIN, FRENTE, "2025Q1", date(2025, 1, 1), date(2025, 3, 31), "r1")
    assert m["total_result_count"] == 3000 and m["n_documents"] == 3000
    assert len(m["windows"]) == 2


def test_empty_quarter_is_complete(raw):
    m = ing.ingest_quarter(
        FakeOps({}), DOMAIN, FRENTE, "2015Q1", date(2015, 1, 1), date(2015, 3, 31), "r1"
    )
    assert m["n_documents"] == 0 and m["total_result_count"] == 0


def test_quota_stops_and_lists_pending_then_resumes(raw):
    per_day = {date(2025, 1, 5): 10, date(2025, 4, 5): 10, date(2025, 7, 5): 10}
    ops = FakeOps(per_day, quota_after=1)
    r = ing.ingest_biblio(ops, [DOMAIN], "r1", since=date(2025, 1, 1), today=date(2025, 8, 1))
    assert r.quota_exceeded and r.done == ["agua/f1/2025Q1"]
    assert r.pending == ["agua/f1/2025Q2", "agua/f1/2025Q3"]
    r2 = ing.ingest_biblio(
        FakeOps(per_day), [DOMAIN], "r2", since=date(2025, 1, 1), today=date(2025, 8, 1)
    )
    assert r2.skipped == ["agua/f1/2025Q1"] and r2.done == ["agua/f1/2025Q2", "agua/f1/2025Q3"]
