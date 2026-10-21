"""CLI del radar: `uv run radar --help`."""

from __future__ import annotations

import typer

from radar.domains.cpc import DEFAULT_TITLE_LIST, CpcScheme, invalid_codes
from radar.domains.loader import load_backtest, load_domains, load_hubs

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Radar tecnológico."""


@app.command()
def validate(
    strict: bool = typer.Option(False, help="Fallar si hay topics de OpenAlex sin resolver."),
) -> None:
    """Valida dominios, hubs y eventos de backtest."""
    domains = load_domains()
    hubs = load_hubs()
    backtest = load_backtest(domains)

    unresolved = 0
    for domain in domains.values():
        role = " [calibración, fuera del memo]" if domain.role == "calibration" else ""
        typer.echo(f"{domain.domain} v{domain.version}: {len(domain.frentes)} frentes{role}")
        for frente_id, topic in domain.unresolved_topics():
            typer.echo(f"  topic sin resolver: {frente_id} -> {topic!r}")
            unresolved += 1
    typer.echo(f"hubs v{hubs.version}: {len(hubs.hubs)}")
    pending = sum(e.status == "propuesto" for e in backtest.events)
    typer.echo(
        f"backtest v{backtest.version}: {len(backtest.events)} eventos ({pending} sin validar)"
    )

    if DEFAULT_TITLE_LIST.exists():
        bad = invalid_codes(domains, CpcScheme.from_title_list())
        typer.echo(f"CPC ({DEFAULT_TITLE_LIST.stem}): {len(bad)} códigos inválidos")
        if bad:
            for item in bad:
                typer.echo(f"  CPC inexistente: {item}", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("CPC: lista oficial no descargada, se omite la validación (ver ADR F0-g)")

    if strict and (unresolved or pending):
        typer.echo("strict: hay topics sin resolver o eventos sin validar", err=True)
        raise typer.Exit(1)
    typer.echo("OK")


openalex_app = typer.Typer(no_args_is_help=True, help="Ciencia: ingesta y staging de OpenAlex.")
app.add_typer(openalex_app, name="openalex")

DOMAINS_OPT = typer.Option("agua,agrobiotech", help="Dominios separados por coma.")


def _select_domains(names: str):
    domains = load_domains()
    wanted = [n.strip() for n in names.split(",") if n.strip()]
    missing = [n for n in wanted if n not in domains]
    if missing:
        raise typer.BadParameter(f"dominios desconocidos: {missing}")
    return [domains[n] for n in wanted]


@openalex_app.command("ingest")
def openalex_ingest(
    domains: str = DOMAINS_OPT,
    since: int = typer.Option(2014, help="Primer año a bajar."),
    refresh_recent: int = typer.Option(2, help="Años recientes que se vuelven a bajar."),
    totals: bool = typer.Option(True, help="Bajar también los totales (denominador)."),
) -> None:
    """Baja works por frente × año a data/raw (reanudable; frena en US$0,80/día)."""
    from radar.connectors.openalex import BudgetExhausted, OpenAlexClient
    from radar.core import runlog
    from radar.ingest.openalex_works import ingest_totals, ingest_works

    client = OpenAlexClient.from_env()
    run_id = runlog.new_run_id("openalex")
    report = ingest_works(client, _select_domains(domains), run_id, since, refresh_recent)
    if totals and not report.budget_exhausted:
        try:
            ingest_totals(client, run_id)
        except BudgetExhausted as exc:
            report.budget_exhausted = True
            typer.echo(f"totales pendientes: {exc}")
    runlog.append("openalex_calls", [{"run_id": run_id, **c} for c in client.calls])
    runlog.append("openalex_runs", [report.__dict__ | {"spent_today_usd": client.spent_today_usd}])
    typer.echo(
        f"{run_id}: {len(report.done)} particiones bajadas, {len(report.skipped)} ya estaban, "
        f"{len(report.errors)} con error, {len(report.pending)} pendientes; "
        f"gastado hoy US${client.spent_today_usd:.3f}"
    )
    if report.budget_exhausted:
        typer.echo("Freno de presupuesto: vuelve a correr el comando después de medianoche UTC.")


@openalex_app.command("build")
def openalex_build(
    domains: str = DOMAINS_OPT,
    fetch_institutions: bool = typer.Option(True, help="Bajar geo de instituciones nuevas."),
) -> None:
    """Construye data/staging/openalex/*.parquet desde la última corrida completa."""
    from radar.connectors.openalex import BudgetExhausted, OpenAlexClient
    from radar.core import runlog
    from radar.ingest.openalex_works import ingest_institutions
    from radar.staging import openalex as st

    works, members, auths = st.build_works(_select_domains(domains))
    for df, name in ((works, "works"), (members, "work_frente"), (auths, "authorships")):
        typer.echo(f"{name}: {df.height} filas -> {st.write(df, name)}")
    if fetch_institutions:
        client = OpenAlexClient.from_env()
        ids = auths["institution_id"].drop_nulls().unique().to_list()
        try:
            ingest_institutions(client, ids, runlog.new_run_id("openalex-inst"))
        except BudgetExhausted as exc:
            typer.echo(f"instituciones pendientes (freno de presupuesto): {exc}")
        runlog.append("openalex_calls", client.calls)
    institutions = st.build_institutions(load_hubs().hubs)
    if not institutions.is_empty():
        typer.echo(
            f"institutions: {institutions.height} filas -> {st.write(institutions, 'institutions')}"
        )
    try:
        years, country_years = st.build_totals()
        st.write(years, "totals_year")
        st.write(country_years, "totals_country_year")
        typer.echo(f"totals: {years.height} años, {country_years.height} país×año")
    except FileNotFoundError as exc:
        typer.echo(f"totales: {exc}")


@openalex_app.command("run")
def openalex_run(domains: str = DOMAINS_OPT) -> None:
    """Ingesta + build."""
    openalex_ingest(domains=domains, since=2014, refresh_recent=2, totals=True)
    openalex_build(domains=domains, fetch_institutions=True)


epo_app = typer.Typer(no_args_is_help=True, help="Patentes: ingesta de EPO OPS.")
app.add_typer(epo_app, name="epo")


@epo_app.command("ingest")
def epo_ingest(domains: str = DOMAINS_OPT) -> None:
    """Baja biblio por frente × trimestre a data/raw (reanudable; frena en 3,5 GB/semana)."""
    from radar.connectors.epo_ops import OpsClient
    from radar.core import runlog
    from radar.ingest.epo_ops_biblio import ingest_biblio

    client = OpsClient.from_env()
    run_id = runlog.new_run_id("epo")
    report = ingest_biblio(client, _select_domains(domains), run_id)
    runlog.append("epo_calls", [{"run_id": run_id, **c} for c in client.log])
    runlog.append("epo_runs", [report.__dict__ | {"week_bytes_used": client.week_bytes_used}])
    typer.echo(
        f"{run_id}: {len(report.done)} trimestres bajados, {len(report.skipped)} ya estaban, "
        f"{len(report.errors)} con error, {len(report.pending)} pendientes; "
        f"semana={client.week_bytes_used / 1e9:.2f} GB"
    )
    if report.quota_exceeded:
        typer.echo("Freno de cuota semanal: vuelve a correr el comando el lunes (00:00 GMT).")


if __name__ == "__main__":
    app()
