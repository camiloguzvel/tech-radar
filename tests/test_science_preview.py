import polars as pl
import pytest

from radar.metrics import science_preview as sp


def staging() -> sp.Staging:
    # Frente f: 1 trabajo en 2019, 2 en 2022, 4 en 2025; el total de OpenAlex se duplica
    # en 2025, así que la participación solo crece ×2 entre 2022 y 2025.
    years = {"W1": 2019, "W2": 2022, "W3": 2022, "W4": 2025, "W5": 2025, "W6": 2025, "W7": 2025}
    works = pl.DataFrame(
        {
            "work_id": list(years),
            "publication_year": list(years.values()),
            "title": [f"t{w}" for w in years],
            "url": [f"https://openalex.org/{w}" for w in years],
            "doi": [None] * len(years),
            "cited_by_count": [1, 2, 3, 40, 5, 6, 7],
            "run_id": ["r"] * len(years),
        }
    )
    members = pl.DataFrame(
        {"work_id": list(years), "domain": ["d"] * len(years), "frente": ["f"] * len(years)}
    )
    authorships = pl.DataFrame(
        {
            "work_id": ["W4", "W4", "W5", "W6", "W7", "W7"],
            "author_id": ["A1", "A2", "A1", "A3", "A1", None],
            "institution_id": ["I1", "I2", "I1", None, "I3", None],
            "institution_country": ["NL", "US", "NL", None, "CN", None],
            "institution_type": ["education", "company", "education", None, "education", None],
            "author_countries": [["NL"], ["US"], ["NL"], ["CN"], ["CN"], []],
        }
    )
    institutions = pl.DataFrame(
        {
            "institution_id": ["I1", "I2", "I3"],
            "display_name": ["TU/e", "Acme", "CAS"],
            "country": ["NL", "US", "CN"],
            "city": ["Eindhoven", "Boston", "Beijing"],
            "hub": ["eindhoven", None, None],
            "type": ["education", "company", "government"],
        }
    )
    totals = pl.DataFrame(
        {"year": [2019, 2020, 2022, 2025], "works": [1_000_000, 1_000_000, 1_000_000, 2_000_000]}
    )
    return sp.Staging(works, members, authorships, institutions, totals)


def test_growth_uses_share_not_raw_counts():
    g = sp.growth_table(sp.share_series(staging()), end=2025)[0]
    assert g["works_end"] == 4
    # participación por millón: 2022 = 2, 2025 = 2 (4 de 2M) => crecimiento reciente 0
    assert g["cagr_recent_3y"] == pytest.approx(0.0)
    assert g["cagr_previous_3y"] == pytest.approx(2 ** (1 / 3) - 1)
    assert g["acceleration_pp"] < 0


def test_country_fractional_counting_sums_to_one_per_work():
    wc = sp.work_countries(staging())
    per_work = wc.group_by("work_id").agg(pl.col("weight").sum())
    assert per_work["weight"].to_list() == pytest.approx([1.0] * per_work.height)
    w4 = wc.filter(pl.col("work_id") == "W4").sort("country")
    assert w4["country"].to_list() == ["NL", "US"] and w4["weight"].to_list() == [0.5, 0.5]


def test_hubs_institutions_and_talent():
    s = staging()
    geo = sp.hubs_and_institutions(s, years=range(2025, 2026))["d/f"]
    assert geo["n_works"] == 4
    assert geo["hubs"] == [{"hub": "eindhoven", "works": 2, "share": 0.5}]
    assert geo["institutions"][0]["name"] == "TU/e"
    assert geo["cities"][0] == {"city": "Eindhoven", "country": "NL", "works": 2, "share": 0.5}
    t = sp.talent(s, years=range(2025, 2026))["d/f"]
    assert t["repeat_authors"] == 1  # A1 aparece en 3 trabajos
    assert t["company_share"] == pytest.approx(0.25)  # solo W4 tiene empresa


def test_top_recent_works_ranked_by_citations():
    top = sp.top_recent_works(staging(), years=(2025,), k=2)["d/f"]
    assert [w["title"] for w in top] == ["tW4", "tW7"]


def test_netherlands_lens():
    nl = sp.netherlands_lens(staging(), start=2019, end=2025, window=range(2025, 2026))["d/f"]
    assert nl["nl_works"] == 2 and nl["eindhoven_works"] == 2 and nl["n_works"] == 4
    assert nl["top_institution"] == {"display_name": "TU/e", "works": 2}
    # W4 = NL+US (0,5 c/u), W5 = NL (1) => NL suma 1,5 de 4 trabajos en 2025
    assert nl["share_end"] == pytest.approx(0.375)
