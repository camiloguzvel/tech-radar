"""Ingesta raw de OpenAlex: works por frente × año, totales anuales e instituciones.

Estructura (todo bajo data/raw/openalex/, no versionado):
  works/<dominio>/<frente>/<año>/<run_id>/page-0001.json.gz ... + _SUCCESS.json
  totals/<run_id>/by_year.json.gz, by_country_year.json.gz + _SUCCESS.json
  institutions/<run_id>/batch-0001.json.gz ... + _SUCCESS.json

Una partición sin `_SUCCESS.json` está incompleta y se ignora. Cada corrida escribe en su propia
carpeta (vintages): staging usa la última completa. Los años recientes se vuelven a bajar en cada
corrida porque OpenAlex sigue agregando trabajos.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from radar import PROJECT_ROOT
from radar.connectors.openalex import (
    WORK_TYPES,
    BudgetExhausted,
    OpenAlexClient,
    OpenAlexError,
    works_filter,
)
from radar.core.config import HISTORY_START
from radar.domains.loader import Domain

RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "openalex"
WORKS_SELECT = (
    "id,doi,title,publication_date,publication_year,type,primary_topic,topics,"
    "cited_by_count,fwci,abstract_inverted_index,authorships"
)
PER_PAGE = 200
SUCCESS = "_SUCCESS.json"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_json_gz(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def read_json_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def latest_complete(parent: Path) -> Path | None:
    """Última carpeta de corrida con `_SUCCESS.json` dentro de `parent`."""
    if not parent.exists():
        return None
    done = sorted(p for p in parent.iterdir() if (p / SUCCESS).exists())
    return done[-1] if done else None


@dataclass
class IngestReport:
    run_id: str
    done: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)  # quedaron sin bajar (freno de presupuesto)
    budget_exhausted: bool = False


def works_partitions(
    domains: Iterable[Domain], since_year: int, today: date
) -> list[tuple[Domain, str, int]]:
    return [
        (d, f.id, year)
        for d in domains
        for f in d.frentes
        for year in range(since_year, today.year + 1)
    ]


def ingest_partition(
    client: OpenAlexClient, domain: Domain, frente_id: str, year: int, run_id: str, today: date
) -> dict:
    frente = next(f for f in domain.frentes if f.id == frente_id)
    until = min(date(year, 12, 31), today)
    flt = works_filter(frente.science, since=date(year, 1, 1), until=until)
    out_dir = RAW_ROOT / "works" / domain.domain / frente_id / str(year) / run_id
    n_records, n_pages, expected, cost = 0, 0, None, 0.0
    params = {"filter": flt, "per_page": PER_PAGE, "select": WORKS_SELECT}
    for body in client.paginate("/works", params):
        meta = body.get("meta") or {}
        if expected is None:
            expected = meta.get("count")
        results = body.get("results") or []
        if not results:
            break
        n_pages += 1
        n_records += len(results)
        cost += meta.get("cost_usd") or 0.0
        _write_json_gz(
            out_dir / f"page-{n_pages:04d}.json.gz",
            {"request": params, "fetched_at": _now(), "meta": meta, "results": results},
        )
    manifest = {
        "source": "openalex",
        "domain": domain.domain,
        "domain_version": domain.version,
        "frente": frente_id,
        "year": year,
        "filter": flt,
        "url": f"https://api.openalex.org/works?filter={flt}",
        "run_id": run_id,
        "n_pages": n_pages,
        "n_records": n_records,
        "meta_count": expected,
        "cost_usd": round(cost, 6),
        "completed_at": _now(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)  # también para particiones vacías
    (out_dir / SUCCESS).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def ingest_works(
    client: OpenAlexClient,
    domains: list[Domain],
    run_id: str,
    since_year: int = HISTORY_START.year,
    refresh_recent_years: int = 2,
    today: date | None = None,
) -> IngestReport:
    """Baja las particiones faltantes y vuelve a bajar los últimos `refresh_recent_years` años."""
    today = today or date.today()
    report = IngestReport(run_id)
    partitions = works_partitions(domains, since_year, today)
    for i, (domain, frente_id, year) in enumerate(partitions):
        key = f"{domain.domain}/{frente_id}/{year}"
        parent = RAW_ROOT / "works" / domain.domain / frente_id / str(year)
        is_recent = year > today.year - refresh_recent_years
        if latest_complete(parent) is not None and not is_recent:
            report.skipped.append(key)
            continue
        try:
            m = ingest_partition(client, domain, frente_id, year, run_id, today)
            report.done.append(key)
            print(
                f"{key}: {m['n_records']} works ({m['n_pages']} pág.) "
                f"hoy=US${client.spent_today_usd:.3f}",
                flush=True,
            )
        except BudgetExhausted as exc:
            report.budget_exhausted = True
            report.pending = [f"{d.domain}/{f}/{y}" for d, f, y in partitions[i:]]
            print(f"FRENO DE PRESUPUESTO: {exc}. Pendientes: {len(report.pending)}", flush=True)
            break
        except OpenAlexError as exc:
            report.errors.append({"partition": key, "error": str(exc)[:500]})
            print(f"{key}: ERROR {str(exc)[:150]}", flush=True)
    return report


def ingest_totals(client: OpenAlexClient, run_id: str, today: date | None = None) -> Path:
    """Denominadores: trabajos por año y por país×año (mismos tipos y fechas que los frentes)."""
    today = today or date.today()
    out_dir = RAW_ROOT / "totals" / run_id
    base = (
        f"from_publication_date:{HISTORY_START.isoformat()},"
        f"to_publication_date:{today.isoformat()},type:{'|'.join(WORK_TYPES)}"
    )
    by_year = client.get("/works", {"filter": base, "group_by": "publication_year"})
    _write_json_gz(out_dir / "by_year.json.gz", {"filter": base, "fetched_at": _now(), **by_year})
    country_rows = []
    types = "|".join(WORK_TYPES)
    for year in range(HISTORY_START.year, today.year + 1):
        flt = f"publication_year:{year},to_publication_date:{today.isoformat()},type:{types}"
        for body in client.paginate(
            "/works", {"filter": flt, "group_by": "authorships.countries", "per_page": 200}
        ):
            for g in body.get("group_by") or []:
                country_rows.append({"year": year, "key": g["key"], "count": g["count"]})
    _write_json_gz(
        out_dir / "by_country_year.json.gz", {"fetched_at": _now(), "rows": country_rows}
    )
    (out_dir / SUCCESS).write_text(
        json.dumps({"run_id": run_id, "completed_at": _now()}), encoding="utf-8"
    )
    return out_dir


def known_institution_ids() -> set[str]:
    """Instituciones ya bajadas en cualquier corrida completa."""
    ids: set[str] = set()
    root = RAW_ROOT / "institutions"
    if not root.exists():
        return ids
    for run_dir in root.iterdir():
        if not (run_dir / SUCCESS).exists():
            continue
        for batch in run_dir.glob("batch-*.json.gz"):
            ids.update(r["id"].rsplit("/", 1)[-1] for r in read_json_gz(batch)["results"])
    return ids


def ingest_institutions(client: OpenAlexClient, ids: Iterable[str], run_id: str) -> Path | None:
    """Geo (lat/long, ciudad) de las instituciones nuevas, de a 100 por llamada."""
    todo = sorted(set(ids) - known_institution_ids())
    if not todo:
        return None
    out_dir = RAW_ROOT / "institutions" / run_id
    for n, start in enumerate(range(0, len(todo), 100), start=1):
        chunk = todo[start : start + 100]
        body = client.get(
            "/institutions",
            {
                "filter": "openalex:" + "|".join(chunk),
                "per_page": 100,
                "select": "id,ror,display_name,type,country_code,geo,lineage",
            },
        )
        _write_json_gz(out_dir / f"batch-{n:04d}.json.gz", {"fetched_at": _now(), **body})
    (out_dir / SUCCESS).write_text(
        json.dumps({"run_id": run_id, "n_requested": len(todo), "completed_at": _now()}),
        encoding="utf-8",
    )
    return out_dir
