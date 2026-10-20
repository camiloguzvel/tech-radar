"""CLI del radar: `uv run radar --help`."""

from __future__ import annotations

import typer

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

    if strict and (unresolved or pending):
        typer.echo("strict: hay topics sin resolver o eventos sin validar", err=True)
        raise typer.Exit(1)
    typer.echo("OK")


if __name__ == "__main__":
    app()
