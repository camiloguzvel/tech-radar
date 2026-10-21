"""Etiquetado de los sets de publicaciones con Claude (decisión de Camilo, 2026-10-21).

Las etiquetas quedan marcadas `labeler=claude-<modelo>`: miden el acuerdo de las definiciones
con el criterio de Claude, NO una validación humana. Un lote por frente, con los criterios
de inclusión y exclusión de ese frente (src/radar/evals/criteria.py).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

import polars as pl
from pydantic import BaseModel, ConfigDict

from radar.domains.loader import Domain
from radar.evals.criteria import CRITERIA, GENERAL
from radar.evals.paper_sets import EVALS
from radar.llm.claude_code import check_subscription_auth, run_structured

PROMPT_VERSION = "papers-v1"


class Label(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    pertenece: Literal["si", "no", "dudoso"]
    frente_correcto: str | None
    justificacion: str


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: list[Label]


def schema(frente_ids: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["labels"],
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["n", "pertenece", "frente_correcto", "justificacion"],
                    "properties": {
                        "n": {"type": "integer"},
                        "pertenece": {"type": "string", "enum": ["si", "no", "dudoso"]},
                        "frente_correcto": {
                            "type": ["string", "null"],
                            "enum": [*frente_ids, "otro_dominio", "ninguno", None],
                        },
                        "justificacion": {"type": "string"},
                    },
                },
            }
        },
    }


def instruction(domain: Domain, frente_id: str) -> str:
    f = next(x for x in domain.frentes if x.id == frente_id)
    others = "\n".join(
        f"- {x.id}: {x.name}. Incluye: {CRITERIA[x.id]['incluye']}"
        for x in domain.frentes
        if x.id != frente_id
    )
    rules = "\n".join(f"- {r}" for r in GENERAL)
    c = CRITERIA[frente_id]
    return f"""Eres evaluador de un radar tecnológico. Decide si cada publicación (JSON en stdin,
con n, título y resumen) pertenece al frente «{f.name}» ({frente_id}) del dominio
«{domain.name}».

Incluye: {c["incluye"]}
Excluye: {c["excluye"]}

Reglas:
{rules}

Si respondes "no" y la publicación encaja en otro frente del dominio, pon su id en
frente_correcto; si es de otro tema pon "otro_dominio" o "ninguno"; si respondes "si" o
"dudoso", frente_correcto = null. Otros frentes del dominio:
{others}

justificacion: una frase corta en español con el motivo concreto. Devuelve una etiqueta por
cada n de la entrada."""


def label_domain(domain: Domain, model: str = "opus") -> pl.DataFrame:
    check_subscription_auth()
    items = [
        json.loads(line)
        for line in (EVALS / f"papers_{domain.domain}.items.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    rows = []
    frente_ids = [f.id for f in domain.frentes]
    for frente_id in frente_ids:
        batch = [
            {"n": it["n"], "titulo": it["titulo"], "resumen": it["resumen"]}
            for it in items
            if it["frente"] == frente_id
        ]
        if not batch:
            continue
        out, meta = run_structured(
            instruction(domain, frente_id), batch, schema(frente_ids), model=model
        )
        wanted = {b["n"] for b in batch}
        labels = [lab for lab in Batch.model_validate(out).labels if lab.n in wanted]
        missing = wanted - {lab.n for lab in labels}
        if missing:  # el modelo omitió filas: se piden solo esas, una vez
            retry = [b for b in batch if b["n"] in missing]
            out2, _ = run_structured(
                instruction(domain, frente_id), retry, schema(frente_ids), model=model
            )
            labels += [lab for lab in Batch.model_validate(out2).labels if lab.n in missing]
            missing = wanted - {lab.n for lab in labels}
        if missing:
            raise ValueError(f"{frente_id}: faltan etiquetas para n={sorted(missing)}")
        labels = list({lab.n: lab for lab in labels}.values())  # sin duplicados
        print(
            f"{domain.domain}/{frente_id}: {len(labels)} etiquetas (caché={meta['cache']})",
            flush=True,
        )
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for lab in labels:
            rows.append(
                lab.model_dump()
                | {
                    "frente": frente_id,
                    "labeler": f"claude-{model}",
                    "prompt_version": PROMPT_VERSION,
                    "labeled_at": now,
                }
            )
    df = pl.DataFrame(rows).sort("n")
    df.write_csv(EVALS / f"papers_{domain.domain}.labels.csv")
    return df
