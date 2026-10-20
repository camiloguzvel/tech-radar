from datetime import date

import httpx
import pytest

from radar.connectors import openalex as oa
from radar.domains.loader import Domain
from radar.ingest import openalex_works as ing
from radar.staging import openalex as st

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
                "science": {"rule": "keyword", "keywords_any": ["water"]},
            },
            {
                "id": "f2",
                "name": "F2",
                "rule": "cpc",
                "cpc_any": ["C02F"],
                "science": {"rule": "keyword", "keywords_any": ["membrane"]},
            },
        ],
    }
)


def work(n: int, year: int = 2024) -> dict:
    return {
        "id": f"https://openalex.org/W{n}",
        "doi": None,
        "title": f"Work {n}",
        "publication_date": f"{year}-05-01",
        "publication_year": year,
        "type": "article",
        "primary_topic": {"id": "https://openalex.org/T1"},
        "topics": [{"id": "https://openalex.org/T1"}],
        "cited_by_count": 3,
        "fwci": 1.2,
        "abstract_inverted_index": {"hello": [0], "world": [1]},
        "authorships": [
            {
                "author": {"id": f"https://openalex.org/A{n}"},
                "author_position": "first",
                "is_corresponding": True,
                "countries": ["NL"],
                "institutions": [
                    {"id": "https://openalex.org/I9", "country_code": "NL", "type": "education"}
                ],
            }
        ],
    }


class FakeServer:
    """Simula /works con cursor, presupuesto en cabeceras y un 429 opcional."""

    def __init__(self, pages: dict[str, list[list[dict]]], spent: float = 0.0, fail_once=False):
        self.pages = pages  # término de búsqueda -> lista de páginas
        self.spent = spent
        self.fail_once = fail_once
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_once:
            self.fail_once = False
            return httpx.Response(429, json={"message": "Rate limit exceeded"})
        flt = request.url.params["filter"]
        term = next(k for k in self.pages if k in flt)
        cursor = request.url.params.get("cursor", "*")
        idx = 0 if cursor == "*" else int(cursor)
        pages = self.pages[term]
        results = pages[idx] if idx < len(pages) else []
        nxt = str(idx + 1) if idx + 1 < len(pages) else None
        self.spent += 0.001
        headers = {
            "x-ratelimit-limit-usd": "1",
            "x-ratelimit-remaining-usd": f"{1 - self.spent:.4f}",
        }
        meta = {"count": sum(len(p) for p in pages), "next_cursor": nxt, "cost_usd": 0.001}
        return httpx.Response(200, json={"meta": meta, "results": results}, headers=headers)


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "RAW_ROOT", tmp_path / "raw")
    monkeypatch.setattr(st, "RAW_ROOT", tmp_path / "raw")
    return tmp_path / "raw"


def client_for(server: FakeServer, **kw) -> oa.OpenAlexClient:
    return oa.OpenAlexClient(
        "k", transport=httpx.MockTransport(server), sleep=lambda s: None, min_interval_s=0, **kw
    )


def test_paginates_retries_429_and_tracks_budget(raw):
    server = FakeServer({"water": [[work(1), work(2)], [work(3)]]}, fail_once=True)
    client = client_for(server)
    m = ing.ingest_partition(client, DOMAIN, "f1", 2024, "run-1", date(2026, 10, 20))
    assert m["n_records"] == 3 and m["n_pages"] == 2 and m["meta_count"] == 3
    assert [c["status"] for c in client.calls][:2] == [429, 200]
    assert client.spent_today_usd == pytest.approx(0.002)
    assert (raw / "works/agua/f1/2024/run-1/_SUCCESS.json").exists()


def test_budget_brake_stops_and_reports_pending(raw):
    server = FakeServer({"water": [[work(1)]], "membrane": [[work(2)]]}, spent=0.799)
    client = client_for(server)
    report = ing.ingest_works(
        client, [DOMAIN], "run-1", since_year=2025, refresh_recent_years=1, today=date(2025, 6, 1)
    )
    # la 1.ª llamada lleva el gasto a 0,800 => el resto queda pendiente, sin inventar nada
    assert report.budget_exhausted
    assert report.done == ["agua/f1/2025"]
    assert report.pending == ["agua/f2/2025"]


def test_empty_partition_is_marked_complete(raw):
    client = client_for(FakeServer({"water": [[]]}))
    m = ing.ingest_partition(client, DOMAIN, "f1", 2015, "run-1", date(2026, 1, 1))
    assert m["n_records"] == 0
    assert ing.latest_complete(raw / "works/agua/f1/2015") is not None


def test_staging_dedupes_works_across_frentes_and_keeps_membership(raw):
    server = FakeServer({"water": [[work(1), work(2)]], "membrane": [[work(2), work(3)]]})
    client = client_for(server)
    for f in ("f1", "f2"):
        ing.ingest_partition(client, DOMAIN, f, 2024, "run-1", date(2026, 10, 20))
    works, members, auths = st.build_works([DOMAIN])
    assert works["work_id"].to_list() == ["W1", "W2", "W3"]
    assert members.height == 4  # W2 pertenece a ambos frentes
    assert works.filter(works["work_id"] == "W1")["abstract"].item() == "hello world"
    assert auths["institution_id"].unique().to_list() == ["I9"]


def test_incomplete_partition_is_ignored(raw):
    client = client_for(FakeServer({"water": [[work(1)]]}))
    ing.ingest_partition(client, DOMAIN, "f1", 2024, "run-1", date(2026, 10, 20))
    (raw / "works/agua/f1/2024/run-2").mkdir()  # corrida que se cortó: sin _SUCCESS
    assert ing.latest_complete(raw / "works/agua/f1/2024").name == "run-1"


def test_reconstruct_abstract_orders_positions():
    assert st.reconstruct_abstract({"b": [1], "a": [0, 2]}) == "a b a"
    assert st.reconstruct_abstract(None) is None
