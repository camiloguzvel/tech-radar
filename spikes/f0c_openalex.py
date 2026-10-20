"""Spike F0-c: resolver topics de OpenAlex por frente y medir límites/costos de la API.

Fases:
  discover  Busca candidatos de topics por frente (nombres del YAML + consultas en inglés).
  limits    Prueba cuántos valores OR acepta un filtro (`primary_topic.id:A|B|...`).
  series    Serie anual desde 2014 por frente con `group_by=publication_year`,
            usando los ids ya resueltos en los YAML (primary_topic vs topics).

Uso:  uv run python spikes/f0c_openalex.py discover|limits|series
Salida: data/spikes/f0c/<fase>-<timestamp>.json ; registra meta.cost_usd de cada llamada.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime

import httpx
from dotenv import load_dotenv

from radar import PROJECT_ROOT
from radar.connectors.openalex import works_filter
from radar.core.config import HISTORY_START
from radar.domains.loader import load_domains

BASE = "https://api.openalex.org"

# Consultas de descubrimiento en inglés por frente (complementan los nombres del YAML).
DISCOVERY = {
    "pfas_remocion": ["PFAS removal water treatment", "perfluoroalkyl degradation"],
    "desalinizacion_membranas": ["reverse osmosis desalination membrane", "membrane separation"],
    "agua_atmosferica": ["atmospheric water harvesting", "metal-organic framework water sorption"],
    "reutilizacion_avanzada": ["advanced oxidation processes wastewater", "water reuse"],
    "redes_inteligentes": ["water distribution network leak detection", "smart water monitoring"],
    "edicion_genica_vegetal": ["CRISPR plant genome editing", "crop gene editing"],
    "biopesticidas": ["biological control plant pathogens", "entomopathogenic biopesticide"],
    "bioestimulantes_fijacion_n": [
        "plant growth-promoting rhizobacteria",
        "biostimulants",
        "biological nitrogen fixation",
    ],
    "rnai_spray": ["RNA interference pest control", "dsRNA spray crop protection"],
    "agricultura_precision": ["precision agriculture", "soil health monitoring"],
    "ion_sodio": ["sodium-ion battery", "battery materials"],
}


class Client:
    def __init__(self) -> None:
        load_dotenv(PROJECT_ROOT / ".env")
        key = os.environ.get("OPENALEX_API_KEY")
        if not key:
            raise SystemExit("Falta OPENALEX_API_KEY en .env")
        self._http = httpx.Client(base_url=BASE, timeout=60, params={"api_key": key})
        self.calls: list[dict] = []

    def get(self, path: str, **params) -> dict:
        # Espaciado + backoff: los filtros con muchos OR reciben 429 si van en ráfaga.
        for wait in (0, 5, 15, 45):
            time.sleep(max(wait, 1.0))
            resp = self._http.get(path, params=params)
            if resp.status_code != 429:
                break
        entry = {"path": path, "params": params, "status": resp.status_code}
        try:
            body = resp.json()
        except ValueError:
            body = {"error_text": resp.text[:500]}
        entry["cost_usd"] = (body.get("meta") or {}).get("cost_usd")
        if resp.status_code != 200:
            entry["error"] = body.get("error") or body.get("message") or body.get("error_text")
        self.calls.append(entry)
        return body | {"_status": resp.status_code}

    @property
    def total_cost(self) -> float:
        return round(sum(c["cost_usd"] or 0 for c in self.calls), 6)


def short_id(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def discover(client: Client) -> dict:
    out: dict = {}
    for domain in load_domains().values():
        for frente in domain.frentes:
            queries = [t.name for t in frente.science.topics] + DISCOVERY.get(frente.id, [])
            seen: dict[str, dict] = {}
            for q in queries:
                body = client.get("/topics", search=q, per_page=5)
                for t in body.get("results", []):
                    tid = short_id(t["id"])
                    if tid not in seen:
                        seen[tid] = {
                            "id": tid,
                            "name": t["display_name"],
                            "works_count": t.get("works_count"),
                            "subfield": (t.get("subfield") or {}).get("display_name"),
                            "query": q,
                        }
            out[f"{domain.domain}/{frente.id}"] = {
                "yaml_names": [t.name for t in frente.science.topics],
                "candidates": list(seen.values()),
            }
    return out


def limits(client: Client) -> dict:
    body = client.get("/topics", per_page=200, select="id")
    ids = [short_id(t["id"]) for t in body.get("results", [])]
    results = {}
    for n in (25, 50, 100, 101, 150, 200):
        if n > len(ids):
            break
        body = client.get("/works", filter="primary_topic.id:" + "|".join(ids[:n]), per_page=1)
        results[n] = {
            "status": body["_status"],
            "count": (body.get("meta") or {}).get("count"),
            "error": body.get("error") or body.get("message"),
        }
    return results


def series(client: Client) -> dict:
    """Serie anual por frente según su bloque `science` + muestra de títulos para revisar."""
    out: dict = {}
    for domain in load_domains().values():
        for frente in domain.frentes:
            flt = works_filter(frente.science, since=HISTORY_START, until=date.today())
            body = client.get("/works", filter=flt, group_by="publication_year")
            by_year = {
                g["key"]: g["count"]
                for g in sorted(body.get("group_by", []), key=lambda g: g["key"])
            }
            sample = client.get(
                "/works", filter=flt, sample=8, seed=42, select="title,publication_year"
            )
            out[f"{domain.domain}/{frente.id}"] = {
                "rule": frente.science.rule,
                "filter": flt,
                "total": sum(by_year.values()),
                "by_year": by_year,
                "sample_titles": [
                    f"{w.get('publication_year')}: {w.get('title')}"
                    for w in sample.get("results", [])
                ],
            }
    return out


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "discover"
    runners = {"discover": discover, "limits": limits, "series": series}
    if phase not in runners:
        raise SystemExit(f"fase desconocida: {phase} (opciones: {', '.join(runners)})")
    client = Client()
    result = runners[phase](client)
    report = {
        "phase": phase,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "n_calls": len(client.calls),
        "total_cost_usd": client.total_cost,
        "errors": [c for c in client.calls if c["status"] != 200],
        "result": result,
    }
    out_dir = PROJECT_ROOT / "data" / "spikes" / "f0c"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{phase}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nGuardado en {path}")


if __name__ == "__main__":
    main()
