"""Precisión y recall de las definiciones de frente a partir de los sets etiquetados.

precision  = si / (si + no) en el estrato `nucleo` (muestra aleatoria de lo asignado);
             los "dudoso" se reportan aparte, no se cuentan.
recall     ≈ TP / (TP + FN), con TP = precision × M (asignados 2016–2025) y
             FN = p_adj × U, donde p_adj = % de "si" en el estrato `adyacente` y U = tamaño del
             universo adyacente que el filtro dejó fuera (conteo en la API − asignados).
Los intervalos son de Wilson al 95%. Con 8 casos por frente son anchos: sirven para ordenar
y decidir qué revisar, no como cifras finales.
"""

from __future__ import annotations

import math

import polars as pl

from radar.connectors.openalex import OpenAlexClient
from radar.domains.loader import Domain
from radar.evals.paper_sets import ADJ_YEARS, EVALS, adjacent_filter
from radar.staging.openalex import STAGING


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _counts(df: pl.DataFrame) -> dict:
    vc = dict(df["pertenece"].value_counts().iter_rows())
    si, no, dud = vc.get("si", 0), vc.get("no", 0), vc.get("dudoso", 0)
    lo, hi = wilson(si, si + no)
    return {
        "si": si,
        "no": no,
        "dudoso": dud,
        "rate": si / (si + no) if si + no else None,
        "ci_low": lo,
        "ci_high": hi,
    }


def evaluate(domain: Domain, client: OpenAlexClient | None = None) -> pl.DataFrame:
    key = pl.read_csv(EVALS / f"papers_{domain.domain}.key.csv")
    labels = pl.read_csv(EVALS / f"papers_{domain.domain}.labels.csv")
    df = key.join(labels.select("n", "pertenece", "frente_correcto", "labeler"), on="n")
    members = pl.read_parquet(STAGING / "work_frente.parquet").join(
        pl.read_parquet(STAGING / "works.parquet").select("work_id", "publication_year"),
        on="work_id",
    )
    rows = []
    for f in domain.frentes:
        mine = df.filter(pl.col("frente") == f.id)
        core = _counts(mine.filter(pl.col("estrato") == "nucleo"))
        border = _counts(mine.filter(pl.col("estrato") == "frontera"))
        adj = _counts(mine.filter(pl.col("estrato") == "adyacente"))
        m = members.filter(
            (pl.col("domain") == domain.domain)
            & (pl.col("frente") == f.id)
            & pl.col("publication_year").is_between(*ADJ_YEARS)
        ).height
        recall = universe = None
        if client is not None and core["rate"] is not None and adj["rate"] is not None:
            total = (
                client.get("/works", {"filter": adjacent_filter(f), "per_page": 1}).get("meta")
                or {}
            ).get("count")
            if total is not None:
                universe = max(total - m, 0)
                tp, fn = core["rate"] * m, adj["rate"] * universe
                recall = tp / (tp + fn) if tp + fn else None
        rows.append(
            {
                "frente": f.id,
                "labeler": mine["labeler"].unique().to_list()[0] if mine.height else None,
                "precision": core["rate"],
                "precision_ci_low": core["ci_low"],
                "precision_ci_high": core["ci_high"],
                "nucleo_si_no_dudoso": f"{core['si']}/{core['no']}/{core['dudoso']}",
                "frontera_si_no_dudoso": f"{border['si']}/{border['no']}/{border['dudoso']}",
                "adyacente_si_no_dudoso": f"{adj['si']}/{adj['no']}/{adj['dudoso']}",
                "asignados_2016_2025": m,
                "universo_excluido": universe,
                "recall_estimado": recall,
                "reasignados_a": ", ".join(
                    sorted(
                        {
                            r
                            for r in mine.filter(pl.col("pertenece") == "no")["frente_correcto"]
                            .drop_nulls()
                            .to_list()
                        }
                    )
                ),
            }
        )
    out = pl.DataFrame(rows)
    out.write_csv(EVALS / f"papers_{domain.domain}.metrics.csv")
    return out
