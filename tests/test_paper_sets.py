import zipfile

import polars as pl

from radar.domains.loader import load_domains
from radar.evals import paper_sets as ps


def test_title_keyword_detection():
    assert ps._title_has_keyword("Removal of PFAS by sorption", ["PFAS"])
    assert not ps._title_has_keyword("Adsorption on biochar", ["PFAS", "PFOA"])
    assert not ps._title_has_keyword(None, ["PFAS"])


def test_write_set_hides_stratum_and_keeps_key(tmp_path):
    domain = load_domains()["agua"]
    f = domain.frentes[0]
    rows = [
        ps._row(domain, f, s, f"W{i}", 2020, f"t{i}", "abs", "https://openalex.org/W1")
        for i, s in enumerate(["nucleo", "frontera", "adyacente"])
    ]
    xlsx, key = ps.write_set(domain, rows, out_dir=tmp_path)
    k = pl.read_csv(key)
    assert sorted(k["estrato"].to_list()) == ["adyacente", "frontera", "nucleo"]
    with zipfile.ZipFile(xlsx) as z:
        text = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
    assert "frontera" not in text and "adyacente" not in text and "nucleo" not in text
