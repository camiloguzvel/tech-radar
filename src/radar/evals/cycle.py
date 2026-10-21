"""Ciclo de evaluación de definiciones: ingesta → staging → sets → etiquetas → métricas.

Se detiene antes de etiquetar si la ingesta dejó particiones pendientes (freno de presupuesto),
para no medir con datos incompletos. Vuelve a correr el comando después del reinicio del cupo.
"""

from __future__ import annotations

import polars as pl

from radar.connectors.openalex import OpenAlexClient
from radar.core import runlog
from radar.domains.loader import Domain, load_hubs
from radar.evals.llm_labeler import label_domain
from radar.evals.metrics import evaluate
from radar.evals.paper_sets import build_sets
from radar.ingest.openalex_works import ingest_institutions, ingest_works
from radar.staging import openalex as st


def run_cycle(domains: list[Domain], model: str = "opus") -> dict[str, pl.DataFrame] | None:
    client = OpenAlexClient.from_env()
    report = ingest_works(client, domains, runlog.new_run_id("openalex"), refresh_recent_years=0)
    runlog.append("openalex_runs", [report.__dict__ | {"spent_today_usd": client.spent_today_usd}])
    if report.pending or report.errors:
        print(
            f"PENDIENTE: {len(report.pending)} particiones, {len(report.errors)} errores. "
            "No se etiqueta con datos incompletos.",
            flush=True,
        )
        return None
    works, members, auths = st.build_works(domains)
    for df, name in ((works, "works"), (members, "work_frente"), (auths, "authorships")):
        st.write(df, name)
    ingest_institutions(
        client,
        auths["institution_id"].drop_nulls().unique().to_list(),
        runlog.new_run_id("openalex-inst"),
    )
    st.write(st.build_institutions(load_hubs().hubs), "institutions")
    build_sets(domains, client)
    results = {}
    for d in domains:
        label_domain(d, model=model)
        results[d.domain] = evaluate(d, client)
    runlog.append("openalex_calls", client.calls)
    print(f"CICLO COMPLETO; gastado hoy US${client.spent_today_usd:.3f}", flush=True)
    return results
