"""Raw de OpenAlex → staging en Parquet (data/staging/openalex/), validado con Pandera.

Tablas:
  works.parquet           una fila por trabajo (deduplicado entre frentes)
  work_frente.parquet     pertenencia trabajo ∈ frente (Membership del contrato)
  authorships.parquet     trabajo × autor × institución (una fila sin institución si no hay)
  institutions.parquet    institución con geo y hub asignado
  totals_year.parquet     denominador: trabajos por año
  totals_country_year.parquet  denominador: trabajos por país × año
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandera.polars as pa
import polars as pl

from radar import PROJECT_ROOT
from radar.connectors.openalex import WORK_TYPES
from radar.core.config import HISTORY_START
from radar.domains.loader import Domain, Hub
from radar.ingest.openalex_works import RAW_ROOT, SUCCESS, latest_complete, read_json_gz
from radar.resolve.geo import assign_hub

STAGING = PROJECT_ROOT / "data" / "staging" / "openalex"


def short_id(url: str | None) -> str | None:
    return url.rsplit("/", 1)[-1] if url else None


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str | None:
    if not inverted:
        return None
    positions = [(pos, word) for word, poss in inverted.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))


# ---------------------------------------------------------------- esquemas


class WorksSchema(pa.DataFrameModel):
    work_id: str = pa.Field(unique=True, str_matches=r"^W\d+$")
    publication_year: int = pa.Field(ge=HISTORY_START.year, le=date.today().year)
    type: str = pa.Field(isin=list(WORK_TYPES))
    cited_by_count: int = pa.Field(ge=0)
    source: str = pa.Field(isin=["openalex"])
    url: str = pa.Field(str_startswith="https://openalex.org/W")
    run_id: str


class MembershipSchema(pa.DataFrameModel):
    work_id: str = pa.Field(str_matches=r"^W\d+$")
    domain: str
    frente: str
    rule: str = pa.Field(str_startswith="openalex:")

    @pa.dataframe_check
    def unique_membership(cls, data) -> pl.LazyFrame:  # noqa: N805
        return data.lazyframe.select(~pl.struct("work_id", "domain", "frente").is_duplicated())


class AuthorshipsSchema(pa.DataFrameModel):
    work_id: str = pa.Field(str_matches=r"^W\d+$")
    author_position: str = pa.Field(nullable=True)


class InstitutionsSchema(pa.DataFrameModel):
    institution_id: str = pa.Field(unique=True, str_matches=r"^I\d+$")
    lat: float = pa.Field(nullable=True, ge=-90, le=90)
    lon: float = pa.Field(nullable=True, ge=-180, le=180)
    hub_method: str = pa.Field(nullable=True, isin=["radius", "country", "manual"])


class TotalsYearSchema(pa.DataFrameModel):
    year: int = pa.Field(unique=True)
    works: int = pa.Field(gt=0)


# ---------------------------------------------------------------- works


def _latest_work_partitions(domains: list[Domain]) -> list[tuple[Domain, str, Path]]:
    found = []
    for d in domains:
        for f in d.frentes:
            frente_root = RAW_ROOT / "works" / d.domain / f.id
            if not frente_root.exists():
                continue
            for year_dir in sorted(frente_root.iterdir()):
                run_dir = latest_complete(year_dir)
                if run_dir is not None:
                    found.append((d, f.id, run_dir))
    return found


def build_works(domains: list[Domain]) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    works, members, auths = [], [], []
    rules = {(d.domain, f.id): f"openalex:{f.science.rule}" for d in domains for f in d.frentes}
    for domain, frente_id, run_dir in _latest_work_partitions(domains):
        run_id = run_dir.name
        for page in sorted(run_dir.glob("page-*.json.gz")):
            payload = read_json_gz(page)
            fetched_at = payload["fetched_at"]
            for w in payload["results"]:
                wid = short_id(w["id"])
                works.append(
                    {
                        "work_id": wid,
                        "doi": w.get("doi"),
                        "title": w.get("title"),
                        "publication_date": w.get("publication_date"),
                        "publication_year": w.get("publication_year"),
                        "type": w.get("type"),
                        "primary_topic_id": short_id((w.get("primary_topic") or {}).get("id")),
                        "topic_ids": [short_id(t["id"]) for t in w.get("topics") or []],
                        "cited_by_count": w.get("cited_by_count") or 0,
                        "fwci": w.get("fwci"),
                        "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
                        "source": "openalex",
                        "url": w["id"],
                        "extracted_at": fetched_at,
                        "run_id": run_id,
                    }
                )
                members.append(
                    {
                        "work_id": wid,
                        "entity_type": "work",
                        "domain": domain.domain,
                        "frente": frente_id,
                        "rule": rules[(domain.domain, frente_id)],
                        "confidence": 1.0,
                        "run_id": run_id,
                    }
                )
                for a in w.get("authorships") or []:
                    base = {
                        "work_id": wid,
                        "author_id": short_id((a.get("author") or {}).get("id")),
                        "author_position": a.get("author_position"),
                        "is_corresponding": bool(a.get("is_corresponding")),
                        "author_countries": a.get("countries") or [],
                    }
                    insts = a.get("institutions") or []
                    if not insts:
                        auths.append(
                            base
                            | {
                                "institution_id": None,
                                "institution_country": None,
                                "institution_type": None,
                            }
                        )
                    for inst in insts:
                        auths.append(
                            base
                            | {
                                "institution_id": short_id(inst.get("id")),
                                "institution_country": inst.get("country_code"),
                                "institution_type": inst.get("type"),
                            }
                        )
    works_df = (
        pl.DataFrame(works, infer_schema_length=None)
        .with_columns(pl.col("publication_date").str.to_date(strict=False))
        .sort("extracted_at", descending=True)
        .unique("work_id", keep="first")
        .sort("work_id")
    )
    members_df = pl.DataFrame(members).unique(["work_id", "domain", "frente"], keep="last")
    auths_df = pl.DataFrame(auths, infer_schema_length=None).unique(
        ["work_id", "author_id", "institution_id"], keep="first"
    )
    return (
        WorksSchema.validate(works_df),
        MembershipSchema.validate(members_df),
        AuthorshipsSchema.validate(auths_df),
    )


# ---------------------------------------------------------------- referencias


def build_institutions(hubs: list[Hub]) -> pl.DataFrame:
    rows = []
    root = RAW_ROOT / "institutions"
    for run_dir in sorted(root.iterdir()) if root.exists() else []:
        if not (run_dir / SUCCESS).exists():
            continue
        for batch in sorted(run_dir.glob("batch-*.json.gz")):
            for r in read_json_gz(batch)["results"]:
                geo = r.get("geo") or {}
                lat, lon, cc = geo.get("latitude"), geo.get("longitude"), r.get("country_code")
                hub = assign_hub(lat, lon, cc, hubs)
                rows.append(
                    {
                        "institution_id": short_id(r["id"]),
                        "ror": r.get("ror"),
                        "display_name": r.get("display_name"),
                        "type": r.get("type"),
                        "country": cc,
                        "city": geo.get("city"),
                        "lat": lat,
                        "lon": lon,
                        "hub": hub[0] if hub else None,
                        "hub_method": hub[1] if hub else None,
                        "run_id": run_dir.name,
                    }
                )
    schema = {"lat": pl.Float64, "lon": pl.Float64, "hub": pl.Utf8, "hub_method": pl.Utf8}
    df = pl.DataFrame(rows, schema_overrides=schema, infer_schema_length=None)
    if df.is_empty():
        return df
    return InstitutionsSchema.validate(df.unique("institution_id", keep="last"))


def build_totals() -> tuple[pl.DataFrame, pl.DataFrame]:
    run_dir = latest_complete(RAW_ROOT / "totals")
    if run_dir is None:
        raise FileNotFoundError("no hay totales de OpenAlex descargados")
    by_year = read_json_gz(run_dir / "by_year.json.gz")
    years = pl.DataFrame(
        [{"year": int(g["key"]), "works": g["count"]} for g in by_year["group_by"]]
    ).filter(pl.col("year") >= HISTORY_START.year)
    by_cy = read_json_gz(run_dir / "by_country_year.json.gz")["rows"]
    cy = (
        pl.DataFrame(by_cy)
        .rename({"key": "country", "count": "works"})
        .with_columns(pl.col("country").map_elements(short_id, return_dtype=pl.Utf8))
    )
    return (
        TotalsYearSchema.validate(years.with_columns(pl.lit(run_dir.name).alias("run_id"))),
        cy.with_columns(pl.lit(run_dir.name).alias("run_id")),
    )


def write(df: pl.DataFrame, name: str) -> Path:
    STAGING.mkdir(parents=True, exist_ok=True)
    path = STAGING / f"{name}.parquet"
    df.write_parquet(path)
    return path
