"""Métricas de la vista previa científica (solo OpenAlex; descriptivas, no son señales).

Todas las tasas se calculan sobre la **participación** del frente en el total anual de
OpenAlex (ADR F0-c), nunca sobre conteos crudos. El año en curso es parcial: se muestra en la
serie pero no entra en ninguna tasa.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from radar.staging.openalex import STAGING

COMPLETE_YEAR = 2025  # último año completo (fecha de datos: oct-2026)


@dataclass
class Staging:
    works: pl.DataFrame
    members: pl.DataFrame
    authorships: pl.DataFrame
    institutions: pl.DataFrame
    totals_year: pl.DataFrame

    @classmethod
    def load(cls, root=STAGING) -> Staging:
        return cls(
            works=pl.read_parquet(root / "works.parquet"),
            members=pl.read_parquet(root / "work_frente.parquet"),
            authorships=pl.read_parquet(root / "authorships.parquet"),
            institutions=pl.read_parquet(root / "institutions.parquet"),
            totals_year=pl.read_parquet(root / "totals_year.parquet"),
        )


def _cagr(start: float | None, end: float | None, years: int) -> float | None:
    if not start or end is None or start <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def frente_works(s: Staging) -> pl.DataFrame:
    """(domain, frente, work_id, year)."""
    return s.members.join(
        s.works.select("work_id", pl.col("publication_year").alias("year")), on="work_id"
    ).select("domain", "frente", "work_id", "year")


def share_series(s: Staging) -> pl.DataFrame:
    """Trabajos y participación (por millón de trabajos de OpenAlex) por frente y año."""
    counts = frente_works(s).group_by("domain", "frente", "year").len("works")
    return (
        counts.join(s.totals_year.select("year", pl.col("works").alias("total")), on="year")
        .with_columns((pl.col("works") / pl.col("total") * 1e6).alias("per_million"))
        .sort("domain", "frente", "year")
    )


def growth_table(series: pl.DataFrame, end: int = COMPLETE_YEAR) -> list[dict]:
    rows = []
    for (domain, frente), g in series.group_by("domain", "frente", maintain_order=True):
        share = dict(zip(g["year"].to_list(), g["per_million"].to_list(), strict=True))
        works = dict(zip(g["year"].to_list(), g["works"].to_list(), strict=True))
        recent = _cagr(share.get(end - 3), share.get(end), 3)
        previous = _cagr(share.get(end - 6), share.get(end - 3), 3)
        rows.append(
            {
                "domain": domain,
                "frente": frente,
                "works_end": works.get(end, 0),
                "cagr_5y": _cagr(share.get(end - 5), share.get(end), 5),
                "cagr_recent_3y": recent,
                "cagr_previous_3y": previous,
                "acceleration_pp": (recent - previous) * 100
                if recent is not None and previous is not None
                else None,
                "series": [
                    {"year": y, "works": works[y], "per_million": round(share[y], 3)}
                    for y in sorted(share)
                ],
            }
        )
    return sorted(
        rows, key=lambda r: r["cagr_5y"] if r["cagr_5y"] is not None else -9, reverse=True
    )


def work_countries(s: Staging) -> pl.DataFrame:
    """(work_id, country, weight): conteo fraccional, cada trabajo suma 1 entre sus países."""
    inst = s.authorships.select("work_id", pl.col("institution_country").alias("country"))
    auth = s.authorships.select("work_id", pl.col("author_countries").alias("country")).explode(
        "country"
    )
    both = pl.concat([inst, auth]).drop_nulls().unique()
    return both.with_columns((1 / pl.len().over("work_id")).alias("weight"))


def country_shares(s: Staging, years: tuple[int, int]) -> pl.DataFrame:
    """Participación fraccional de cada país en el frente para dos años (inicio, fin)."""
    fw = frente_works(s).filter(pl.col("year").is_in(years))
    wc = work_countries(s)
    frac = (
        fw.join(wc, on="work_id")
        .group_by("domain", "frente", "year", "country")
        .agg(pl.col("weight").sum().alias("frac"))
    )
    tot = fw.group_by("domain", "frente", "year").len("n")
    return frac.join(tot, on=["domain", "frente", "year"]).with_columns(
        (pl.col("frac") / pl.col("n")).alias("share")
    )


def top_countries(s: Staging, start: int = 2019, end: int = COMPLETE_YEAR, k: int = 6) -> dict:
    cs = country_shares(s, (start, end))
    out: dict = {}
    for (domain, frente), g in cs.group_by("domain", "frente"):
        wide = g.pivot(on="year", index="country", values="share").fill_null(0)
        wide = wide.rename({str(start): "start", str(end): "end"}).sort("end", descending=True)
        out[f"{domain}/{frente}"] = [
            {
                "country": r["country"],
                "share_end": round(r["end"], 4),
                "change_pp": round((r["end"] - r["start"]) * 100, 2),
            }
            for r in wide.head(k).iter_rows(named=True)
        ]
    return out


def _window(s: Staging, years: range) -> pl.DataFrame:
    return frente_works(s).filter(pl.col("year").is_in(list(years)))


def hubs_and_institutions(
    s: Staging, years: range = range(COMPLETE_YEAR - 2, COMPLETE_YEAR + 1), k: int = 8
) -> dict:
    """Conteo entero: % de trabajos del frente con ≥1 autor en el hub / la institución."""
    fw = _window(s, years)
    n = fw.group_by("domain", "frente").len("n")
    wi = s.authorships.select("work_id", "institution_id").drop_nulls().unique()
    inst = s.institutions.select("institution_id", "display_name", "country", "city", "hub", "type")
    joined = fw.join(wi, on="work_id").join(inst, on="institution_id", how="left")
    hubs = (
        joined.drop_nulls("hub")
        .select("domain", "frente", "work_id", "hub")
        .unique()
        .group_by("domain", "frente", "hub")
        .len("works")
        .join(n, on=["domain", "frente"])
        .with_columns((pl.col("works") / pl.col("n")).alias("share"))
    )
    insts = (
        joined.select("domain", "frente", "work_id", "institution_id", "display_name", "country")
        .unique()
        .group_by("domain", "frente", "institution_id", "display_name", "country")
        .len("works")
        .join(n, on=["domain", "frente"])
        .with_columns((pl.col("works") / pl.col("n")).alias("share"))
    )
    cities = (
        joined.drop_nulls("city")
        .select("domain", "frente", "work_id", "city", "country")
        .unique()
        .group_by("domain", "frente", "city", "country")
        .len("works")
        .join(n, on=["domain", "frente"])
        .with_columns((pl.col("works") / pl.col("n")).alias("share"))
    )
    out: dict = {}
    for (domain, frente), g in n.group_by("domain", "frente"):
        key = f"{domain}/{frente}"
        hg = hubs.filter((pl.col("domain") == domain) & (pl.col("frente") == frente))
        ig = insts.filter((pl.col("domain") == domain) & (pl.col("frente") == frente))
        cg = cities.filter((pl.col("domain") == domain) & (pl.col("frente") == frente))
        out[key] = {
            "n_works": g["n"].item(),
            "hubs": [
                {"hub": r["hub"], "works": r["works"], "share": round(r["share"], 4)}
                for r in hg.sort("works", descending=True).iter_rows(named=True)
            ],
            "cities": [
                {
                    "city": r["city"],
                    "country": r["country"],
                    "works": r["works"],
                    "share": round(r["share"], 4),
                }
                for r in cg.sort("works", descending=True).head(k).iter_rows(named=True)
            ],
            "institutions": [
                {
                    "name": r["display_name"],
                    "country": r["country"],
                    "works": r["works"],
                    "share": round(r["share"], 4),
                }
                for r in ig.sort("works", descending=True).head(k).iter_rows(named=True)
            ],
        }
    return out


def talent(s: Staging, years: range = range(COMPLETE_YEAR - 2, COMPLETE_YEAR + 1)) -> dict:
    """Autores recurrentes (≥2 trabajos en la ventana) y % de trabajos con afiliación de empresa."""
    fw = _window(s, years)
    wa = fw.join(s.authorships.select("work_id", "author_id", "institution_type"), on="work_id")
    per_author = (
        wa.drop_nulls("author_id")
        .select("domain", "frente", "author_id", "work_id")
        .unique()
        .group_by("domain", "frente", "author_id")
        .len("works")
    )
    repeat = per_author.group_by("domain", "frente").agg(
        pl.len().alias("authors"),
        (pl.col("works") >= 2).sum().alias("repeat_authors"),
    )
    company = (
        wa.group_by("domain", "frente", "work_id")
        .agg((pl.col("institution_type") == "company").any().alias("has_company"))
        .group_by("domain", "frente")
        .agg(pl.col("has_company").mean().alias("company_share"))
    )
    t = repeat.join(company, on=["domain", "frente"])
    return {
        f"{r['domain']}/{r['frente']}": {
            "authors": r["authors"],
            "repeat_authors": r["repeat_authors"],
            "repeat_share": round(r["repeat_authors"] / r["authors"], 4) if r["authors"] else None,
            "company_share": round(r["company_share"], 4),
        }
        for r in t.iter_rows(named=True)
    }


def top_recent_works(s: Staging, years: tuple[int, ...] = (2024, 2025), k: int = 5) -> dict:
    fw = frente_works(s).filter(pl.col("year").is_in(list(years)))
    ranked = fw.join(
        s.works.select("work_id", "title", "url", "doi", "cited_by_count", "publication_year"),
        on="work_id",
    ).sort("cited_by_count", descending=True)
    out: dict = {}
    for (domain, frente), g in ranked.group_by("domain", "frente", maintain_order=True):
        out[f"{domain}/{frente}"] = [
            {
                "title": r["title"],
                "year": r["publication_year"],
                "cited_by": r["cited_by_count"],
                "url": r["doi"] or r["url"],
            }
            for r in g.head(k).iter_rows(named=True)
        ]
    return out


def netherlands_lens(
    s: Staging,
    start: int = 2019,
    end: int = COMPLETE_YEAR,
    window: range = range(COMPLETE_YEAR - 2, COMPLETE_YEAR + 1),
) -> dict:
    """Participación fraccional de NL, trabajos con ≥1 institución NL o del hub Eindhoven."""
    cs = country_shares(s, (start, end)).filter(pl.col("country") == "NL")
    fw = _window(s, window)
    n = fw.group_by("domain", "frente").len("n")
    inst = s.institutions.select("institution_id", "display_name", "country", "hub")
    wi = s.authorships.select("work_id", "institution_id").drop_nulls().unique()
    nl = fw.join(wi, on="work_id").join(inst, on="institution_id").filter(pl.col("country") == "NL")
    out: dict = {}
    for (domain, frente), g in n.group_by("domain", "frente"):
        key = f"{domain}/{frente}"
        mine = nl.filter((pl.col("domain") == domain) & (pl.col("frente") == frente))
        share = {
            r["year"]: r["share"]
            for r in cs.filter(
                (pl.col("domain") == domain) & (pl.col("frente") == frente)
            ).iter_rows(named=True)
        }
        top = (
            mine.select("work_id", "display_name")
            .unique()
            .group_by("display_name")
            .len("works")
            .sort("works", descending=True)
        )
        out[key] = {
            "share_end": round(share.get(end, 0.0), 4),
            "change_pp": round((share.get(end, 0.0) - share.get(start, 0.0)) * 100, 2),
            "nl_works": mine["work_id"].n_unique(),
            "eindhoven_works": mine.filter(pl.col("hub") == "eindhoven")["work_id"].n_unique(),
            "n_works": g["n"].item(),
            "top_institution": top.row(0, named=True) if top.height else None,
        }
    return out


def build_preview(s: Staging) -> dict:
    series = share_series(s)
    return {
        "complete_year": COMPLETE_YEAR,
        "growth": growth_table(series),
        "countries": top_countries(s),
        "geography": hubs_and_institutions(s),
        "talent": talent(s),
        "top_works": top_recent_works(s),
        "netherlands": netherlands_lens(s),
        "totals_year": s.totals_year.select("year", "works").sort("year").to_dicts(),
        "run_ids": sorted(set(s.works["run_id"].to_list())),
        "n_works": s.works.height,
    }
