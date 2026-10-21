"""Ingesta raw de EPO OPS: documentos con biblio por frente × trimestre (ADR F0-a).

Estructura (data/raw/epo_ops/, no versionada; licencia OPS: no redistribuir):
  biblio/<dominio>/<frente>/<AAAAQn>/<run_id>/page-0001.json.gz ... + _SUCCESS.json

Cada trimestre se consulta por fecha de publicación (`pd`). Si una ventana supera los 2.000
resultados que OPS permite recorrer, se parte en dos mitades (recursivo) hasta que quepa.
Una partición sin `_SUCCESS.json` está incompleta y se ignora. La cuota semanal frena la
corrida con `QuotaExceeded`; lo pendiente queda listado y se reanuda en la siguiente.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from radar import PROJECT_ROOT
from radar.connectors.epo_ops import (
    MAX_RESULTS_PER_QUERY,
    OpsClient,
    OpsError,
    QuotaExceeded,
    frente_cql,
)
from radar.core.config import HISTORY_START
from radar.domains.loader import Domain, Frente

RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "epo_ops"
SUCCESS = "_SUCCESS.json"
PAGE = 100  # máximo por llamada en OPS


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def quarters(start: date, today: date) -> list[tuple[str, date, date]]:
    out = []
    y, q = start.year, (start.month - 1) // 3 + 1
    while date(y, 3 * q - 2, 1) <= today:
        first = date(y, 3 * q - 2, 1)
        last = (date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1)) - timedelta(days=1)
        out.append((f"{y}Q{q}", first, min(last, today)))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def _biblio(body: dict) -> tuple[int, list[dict]]:
    if not body:  # 404 de OPS = sin resultados
        return 0, []
    bs = body["ops:world-patent-data"]["ops:biblio-search"]
    docs = (bs.get("ops:search-result") or {}).get("exchange-documents") or []
    return int(bs["@total-result-count"]), docs if isinstance(docs, list) else [docs]


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


@dataclass
class Window:
    first: date
    last: date
    total: int
    pages: list[list[dict]] = field(default_factory=list)


def fetch_window(client: OpsClient, frente: Frente, first: date, last: date) -> list[Window]:
    """Baja todas las páginas de [first, last]; parte la ventana si supera el tope de OPS."""
    cql = frente_cql(frente, _fmt(first), _fmt(last))
    total, docs = _biblio(client.search_biblio(cql, 1, PAGE))
    if total > MAX_RESULTS_PER_QUERY:
        if first == last:
            raise OpsError(f"{total} resultados en un solo día ({first}): no se puede partir")
        mid = first + (last - first) // 2
        return fetch_window(client, frente, first, mid) + fetch_window(
            client, frente, mid + timedelta(days=1), last
        )
    w = Window(first, last, total, [docs] if docs else [])
    for start in range(PAGE + 1, total + 1, PAGE):
        _, more = _biblio(client.search_biblio(cql, start, min(start + PAGE - 1, total)))
        w.pages.append(more)
    return [w]


def ingest_quarter(
    client: OpsClient,
    domain: Domain,
    frente: Frente,
    label: str,
    first: date,
    last: date,
    run_id: str,
) -> dict:
    out_dir = RAW_ROOT / "biblio" / domain.domain / frente.id / label / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = fetch_window(client, frente, first, last)
    n_pages = n_docs = 0
    for w in windows:
        for docs in w.pages:
            n_pages += 1
            n_docs += len(docs)
            with gzip.open(out_dir / f"page-{n_pages:04d}.json.gz", "wt", encoding="utf-8") as fh:
                json.dump(
                    {
                        "cql": frente_cql(frente, _fmt(w.first), _fmt(w.last)),
                        "window": [w.first.isoformat(), w.last.isoformat()],
                        "fetched_at": _now(),
                        "documents": docs,
                    },
                    fh,
                    ensure_ascii=False,
                )
    manifest = {
        "source": "epo_ops",
        "domain": domain.domain,
        "domain_version": domain.version,
        "frente": frente.id,
        "quarter": label,
        "windows": [[w.first.isoformat(), w.last.isoformat(), w.total] for w in windows],
        "total_result_count": sum(w.total for w in windows),
        "n_documents": n_docs,
        "n_pages": n_pages,
        "run_id": run_id,
        "completed_at": _now(),
    }
    (out_dir / SUCCESS).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def latest_complete(parent):
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
    pending: list[str] = field(default_factory=list)
    quota_exceeded: bool = False


def ingest_biblio(
    client: OpsClient,
    domains: list[Domain],
    run_id: str,
    since: date = HISTORY_START,
    today: date | None = None,
) -> IngestReport:
    """Baja los trimestres que faltan, frente por frente, en orden cronológico."""
    today = today or date.today()
    report = IngestReport(run_id)
    todo = [
        (d, f, label, first, last)
        for d in domains
        for f in d.frentes
        for label, first, last in quarters(since, today)
    ]
    for i, (d, f, label, first, last) in enumerate(todo):
        key = f"{d.domain}/{f.id}/{label}"
        if latest_complete(RAW_ROOT / "biblio" / d.domain / f.id / label) is not None:
            report.skipped.append(key)
            continue
        try:
            m = ingest_quarter(client, d, f, label, first, last, run_id)
            report.done.append(key)
            print(
                f"{key}: {m['n_documents']} docs (total {m['total_result_count']}, "
                f"{len(m['windows'])} ventanas) semana={client.week_bytes_used / 1e9:.2f} GB",
                flush=True,
            )
        except QuotaExceeded as exc:
            report.quota_exceeded = True
            report.pending = [f"{x[0].domain}/{x[1].id}/{x[2]}" for x in todo[i:]]
            print(f"FRENO DE CUOTA: {exc}. Pendientes: {len(report.pending)}", flush=True)
            break
        except OpsError as exc:
            report.errors.append({"partition": key, "error": str(exc)[:500]})
            print(f"{key}: ERROR {str(exc)[:150]}", flush=True)
    return report
