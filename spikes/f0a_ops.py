"""Spikes F0-a y F0-e con EPO OPS.

  volume   F0-a: documentos por mes (muestras 2015-06, 2020-06, 2025-06) por frente y por
           campo padre, con `cl` (CPC ∪ IPC); estima bytes y semanas de cuota del backfill.
  english  F0-e: % de documentos CN/JP/KR con título y resumen en inglés (muestra de 200).

Uso:  uv run python spikes/f0a_ops.py volume|english
Salida: data/spikes/f0a/<fase>-<timestamp>.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from radar import PROJECT_ROOT
from radar.connectors.epo_ops import WEEKLY_QUOTA_STOP, OpsClient, OpsError, frente_cql
from radar.core.config import HISTORY_START
from radar.domains.loader import load_domains

MONTHS = {
    "2015-06": ("20150601", "20150630"),
    "2020-06": ("20200601", "20200630"),
    "2025-06": ("20250601", "20250630"),
}
PARENTS = {  # campos padre del ADR F0-f
    "agua": "cl=/low C02F",
    "agrobiotech": "(cl=/low A01N63 or cl=/low A01N65 or cl=/low A01H or cl=/low C12N15/82 "
    "or cl=/low C05F)",
    "control": "cl=/low H01M",
}
BYTES_PER_DOC = 9.5 * 1024  # medido: search/biblio JSON, 25 documentos C02F1/44
TRUNCATION = 10_000  # total-result-count se trunca en 10.000


def volume(client: OpsClient) -> dict:
    out: dict = {}
    targets = [
        (f"{d.domain}/{f.id}", lambda a, b, f=f: frente_cql(f, a, b))
        for d in load_domains().values()
        for f in d.frentes
    ] + [
        (f"PADRE {dom}", lambda a, b, q=q: f'{q} and pd within "{a} {b}"')
        for dom, q in PARENTS.items()
    ]
    years = datetime.now().year - HISTORY_START.year + 1
    for name, build in targets:
        try:
            counts = {m: client.count(build(a, b)) for m, (a, b) in MONTHS.items()}
        except OpsError as exc:  # se registra el fallo; nunca se rellena un número
            out[name] = {"error": str(exc)[:300]}
            print(f"{name:42s} ERROR {str(exc)[:120]}", flush=True)
            continue
        monthly_avg = sum(counts.values()) / len(counts)
        docs_backfill = monthly_avg * 12 * years
        out[name] = {
            "docs_per_month": counts,
            "truncated": any(n >= TRUNCATION for n in counts.values()),
            "max_month_over_2000": max(counts.values()) > 2000,
            "docs_backfill_est": round(docs_backfill),
            "gb_backfill_est": round(docs_backfill * BYTES_PER_DOC / 1024**3, 2),
        }
        print(f"{name:42s} {counts}  backfill≈{out[name]['gb_backfill_est']} GB", flush=True)
    total_gb = sum(v.get("gb_backfill_est", 0) for v in out.values())
    out["_total"] = {
        "gb_backfill_est": round(total_gb, 2),
        "weeks_at_3_5gb": round(total_gb / (WEEKLY_QUOTA_STOP / 1024**3), 1),
        "note": "suma bruta: los frentes se solapan con su padre; el padre domina",
    }
    return out


def _as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def english(client: OpsClient) -> dict:
    out: dict = {}
    pd = 'pd within "20250601 20250630"'
    for cc, n in (("CN", 100), ("JP", 50), ("KR", 50)):
        q = f"pn={cc} and (cl=/low C02F or cl=/low A01N or cl=/low C12N or cl=/low H01M) and {pd}"
        body = client.search_biblio(q, 1, n)
        docs = _as_list(
            body.get("ops:world-patent-data", {})
            .get("ops:biblio-search", {})
            .get("ops:search-result", {})
            .get("exchange-documents")
        )
        stats = {"n": 0, "title_en": 0, "abstract_en": 0, "abstract_any": 0, "families": set()}
        abstract_langs: dict[str, int] = {}
        for item in docs:
            doc = item["exchange-document"]
            stats["n"] += 1
            stats["families"].add(doc.get("@family-id"))
            bib = doc.get("bibliographic-data", {})
            titles = _as_list(bib.get("invention-title"))
            if any(t.get("@lang") == "en" for t in titles):
                stats["title_en"] += 1
            abstracts = _as_list(doc.get("abstract"))
            if abstracts:
                stats["abstract_any"] += 1
            for a in abstracts:
                lang = a.get("@lang", "?")
                abstract_langs[lang] = abstract_langs.get(lang, 0) + 1
            if any(a.get("@lang") == "en" for a in abstracts):
                stats["abstract_en"] += 1
        n = max(stats["n"], 1)
        out[cc] = {
            "n": stats["n"],
            "distinct_families": len(stats["families"]),
            "pct_title_en": round(100 * stats["title_en"] / n, 1),
            "pct_abstract_en": round(100 * stats["abstract_en"] / n, 1),
            "pct_abstract_any": round(100 * stats["abstract_any"] / n, 1),
            "abstract_langs": abstract_langs,
        }
        print(cc, out[cc])
    return out


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "volume"
    runners = {"volume": volume, "english": english}
    if phase not in runners:
        raise SystemExit(f"fase desconocida: {phase}")
    client = OpsClient.from_env()
    client.verbose = True
    result = runners[phase](client)
    report = {
        "phase": phase,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "n_calls": len(client.log),
        "bytes_this_run": sum(c["bytes"] for c in client.log),
        "week_bytes_used": client.week_bytes_used,
        "non_200": [c for c in client.log if c["status"] != 200],
        "result": result,
    }
    out_dir = PROJECT_ROOT / "data" / "spikes" / "f0a"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{phase}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
    print(
        f"\nllamadas={report['n_calls']} bytes={report['bytes_this_run']} "
        f"semana={report['week_bytes_used']}\nGuardado en {path}"
    )


if __name__ == "__main__":
    main()
