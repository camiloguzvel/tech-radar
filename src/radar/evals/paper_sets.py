"""Sets de publicaciones para etiquetar a mano (plan §7).

Por frente se toman 13 trabajos, en tres estratos:
  nucleo (8)     muestra aleatoria de lo asignado al frente, 4 de 2014–2019 y 4 de 2020–2025
                 → estima la precisión de la definición
  frontera (2)   asignados, pero sin ninguna keyword en el título (solo en el resumen)
                 → casos dudosos para ajustar la definición
  adyacente (3)  mismo tema que el frente pero excluidos por el filtro (API, muestra con semilla)
                 → estima el recall
El orden se baraja y el estrato no aparece en el Excel (etiquetado a ciegas); la clave va aparte.
"""

from __future__ import annotations

import random
from pathlib import Path

import polars as pl

from radar import PROJECT_ROOT
from radar.connectors.openalex import WORK_TYPES, OpenAlexClient
from radar.domains.loader import Domain, Frente
from radar.evals.criteria import CRITERIA, GENERAL
from radar.staging.openalex import STAGING, reconstruct_abstract, short_id

EVALS = PROJECT_ROOT / "evals"
SEED = 20261021
N_CORE_OLD, N_CORE_NEW, N_BORDER, N_ADJ = 4, 4, 2, 3

# Consultas "adyacentes" para frentes sin topic: más amplias que la definición.
ADJACENT_SEARCH = {
    "agua_atmosferica": '("water harvesting" OR "atmospheric water" OR "fog collection" '
    'OR "moisture harvesting")',
    "rnai_spray": '(dsRNA OR "RNA interference" OR RNAi) AND (crop OR plant OR pest)',
}


def _terms(frente: Frente) -> list[str]:
    sci = frente.science
    return sci.keywords_any or [w for g in sci.keyword_groups for w in g]


def _title_has_keyword(title: str | None, terms: list[str]) -> bool:
    t = (title or "").lower()
    return any(w.lower() in t for w in terms)


def _sample(df: pl.DataFrame, n: int, seed: int) -> pl.DataFrame:
    return df.sample(n=min(n, df.height), seed=seed, shuffle=True) if df.height else df


def staged_candidates(domain: Domain, works: pl.DataFrame, members: pl.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for i, f in enumerate(domain.frentes):
        mine = members.filter(
            (pl.col("domain") == domain.domain) & (pl.col("frente") == f.id)
        ).join(works, on="work_id")
        old = _sample(mine.filter(pl.col("publication_year") <= 2019), N_CORE_OLD, SEED + i)
        new = _sample(
            mine.filter(pl.col("publication_year").is_between(2020, 2025)),
            N_CORE_NEW,
            SEED + 100 + i,
        )
        core_ids = set(old["work_id"]) | set(new["work_id"])
        terms = _terms(f)
        border_pool = mine.filter(
            ~pl.col("work_id").is_in(list(core_ids))
            & pl.col("abstract").is_not_null()
            & ~pl.col("title").map_elements(
                lambda t, terms=terms: _title_has_keyword(t, terms), return_dtype=pl.Boolean
            )
        )
        border = _sample(border_pool, N_BORDER, SEED + 200 + i)
        for stratum, df in (("nucleo", old), ("nucleo", new), ("frontera", border)):
            for r in df.iter_rows(named=True):
                rows.append(
                    _row(
                        domain,
                        f,
                        stratum,
                        r["work_id"],
                        r["publication_year"],
                        r["title"],
                        r["abstract"],
                        r["doi"] or r["url"],
                    )
                )
    return rows


def _row(domain, frente, stratum, wid, year, title, abstract, url) -> dict:
    return {
        "work_id": wid,
        "domain": domain.domain,
        "frente": frente.id,
        "frente_nombre": frente.name,
        "estrato": stratum,
        "anio": year,
        "titulo": title or "",
        "resumen": (abstract or "")[:900],
        "enlace": url,
    }


def adjacent_candidates(
    client: OpenAlexClient, domain: Domain, members: pl.DataFrame
) -> list[dict]:
    rows: list[dict] = []
    assigned = set(members.filter(pl.col("domain") == domain.domain)["work_id"].to_list())
    types = "|".join(WORK_TYPES)
    for i, f in enumerate(domain.frentes):
        sci = f.science
        if sci.rule == "keyword":
            base = f"title_and_abstract.search:{ADJACENT_SEARCH[f.id]}"
        else:
            base = "primary_topic.id:" + "|".join(t.id for t in sci.topics)
        flt = f"{base},publication_year:2016-2025,type:{types}"
        body = client.get(
            "/works",
            {
                "filter": flt,
                "sample": 40,
                "seed": SEED + i,
                "per_page": 40,
                "select": "id,doi,title,publication_year,abstract_inverted_index",
            },
        )
        picked = 0
        for w in body.get("results") or []:
            wid = short_id(w["id"])
            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            if wid in assigned or not abstract:
                continue
            rows.append(
                _row(
                    domain,
                    f,
                    "adyacente",
                    wid,
                    w.get("publication_year"),
                    w.get("title"),
                    abstract,
                    w.get("doi") or w["id"],
                )
            )
            picked += 1
            if picked == N_ADJ:
                break
    return rows


def write_set(domain: Domain, rows: list[dict], out_dir: Path = EVALS) -> tuple[Path, Path]:
    """Excel para etiquetar (sin estrato) + clave CSV con el estrato."""
    random.Random(SEED).shuffle(rows)
    for n, r in enumerate(rows, start=1):
        r["n"] = n
    out_dir.mkdir(parents=True, exist_ok=True)
    key = pl.DataFrame(rows).select("n", "work_id", "domain", "frente", "estrato", "anio")
    key_path = out_dir / f"papers_{domain.domain}.key.csv"
    key.write_csv(key_path)

    import xlsxwriter

    xlsx_path = out_dir / f"papers_{domain.domain}.xlsx"
    frente_names = [f.name for f in domain.frentes] + ["Otro dominio", "Ninguno"]
    wb = xlsxwriter.Workbook(xlsx_path)
    head = wb.add_format(
        {"bold": True, "bg_color": "#E6EDF2", "border": 1, "text_wrap": True, "valign": "top"}
    )
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    todo = wb.add_format({"bg_color": "#FFF7D6", "border": 1, "valign": "top"})
    ws = wb.add_worksheet("Etiquetar")
    cols = [
        ("n", 5),
        ("frente_a_evaluar", 24),
        ("anio", 6),
        ("titulo", 45),
        ("resumen", 80),
        ("enlace", 18),
        ("pertenece", 11),
        ("frente_correcto", 24),
        ("nota", 30),
        ("id", 13),
    ]
    for c, (name, width) in enumerate(cols):
        ws.write(0, c, name, head)
        ws.set_column(c, c, width)
    for i, r in enumerate(rows, start=1):
        ws.write_number(i, 0, r["n"], wrap)
        ws.write(i, 1, r["frente_nombre"], wrap)
        ws.write(i, 2, r["anio"] or "", wrap)
        ws.write(i, 3, r["titulo"], wrap)
        ws.write(i, 4, r["resumen"] or "(sin resumen)", wrap)
        ws.write_url(i, 5, r["enlace"], string="abrir")
        ws.write_blank(i, 6, None, todo)
        ws.write_blank(i, 7, None, todo)
        ws.write_blank(i, 8, None, todo)
        ws.write(i, 9, r["work_id"])
        ws.set_row(i, 120)
    last = len(rows)
    ws.data_validation(1, 6, last, 6, {"validate": "list", "source": ["si", "no", "dudoso"]})
    ws.data_validation(1, 7, last, 7, {"validate": "list", "source": frente_names})
    ws.freeze_panes(1, 2)
    ws.autofilter(0, 0, last, len(cols) - 1)

    g = wb.add_worksheet("Guía")
    g.set_column(0, 0, 28)
    g.set_column(1, 2, 70)
    bold = wb.add_format({"bold": True, "valign": "top", "text_wrap": True})
    g.write(0, 0, "Reglas generales", bold)
    for i, rule in enumerate(GENERAL, start=1):
        g.write(i, 0, f"{i}.", wrap)
        g.write(i, 1, rule, wrap)
    row = len(GENERAL) + 2
    for c, name in enumerate(("Frente", "Incluye", "Excluye")):
        g.write(row, c, name, head)
    for f in domain.frentes:
        row += 1
        crit = CRITERIA[f.id]
        g.write(row, 0, f.name, bold)
        g.write(row, 1, crit["incluye"], wrap)
        g.write(row, 2, crit["excluye"], wrap)
        g.set_row(row, 75)
    wb.close()
    return xlsx_path, key_path


def build_sets(domains: list[Domain], client: OpenAlexClient) -> list[tuple[Path, Path]]:
    works = pl.read_parquet(STAGING / "works.parquet")
    members = pl.read_parquet(STAGING / "work_frente.parquet")
    out = []
    for d in domains:
        rows = staged_candidates(d, works, members) + adjacent_candidates(client, d, members)
        out.append(write_set(d, rows))
    return out


if __name__ == "__main__":
    from radar.domains.loader import load_domains

    ds = load_domains()
    for xlsx, key in build_sets([ds["agua"], ds["agrobiotech"]], OpenAlexClient.from_env()):
        print(xlsx, key)
