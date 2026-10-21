"""Genera la vista previa científica como una página HTML autocontenida.

Uso:  uv run python -m radar.reports.science_preview_html
Salida: data/reports/vista-previa-ciencia.html (no versionada; se publica como Artifact).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar import PROJECT_ROOT
from radar.domains.loader import load_domains, load_hubs
from radar.metrics.science_preview import Staging, build_preview

OUT = PROJECT_ROOT / "data" / "reports" / "vista-previa-ciencia.html"
TEMPLATE = Path(__file__).with_name("science_preview_template.html")


def frente_meta() -> dict:
    meta = {}
    for d in load_domains().values():
        if d.role != "thesis":
            continue
        for f in d.frentes:
            sci = f.science
            meta[f"{d.domain}/{f.id}"] = {
                "name": f.name,
                "domain": d.domain,
                "domain_name": d.name,
                "rule": sci.rule,
                "topics": [{"id": t.id, "name": t.name} for t in sci.topics],
                "keywords": sci.keywords_any,
                "keyword_groups": sci.keyword_groups,
            }
    return meta


def render() -> Path:
    data = build_preview(Staging.load())
    meta = frente_meta()
    data["growth"] = [g for g in data["growth"] if f"{g['domain']}/{g['frente']}" in meta]
    data |= {
        "frentes": meta,
        "hubs": {h.id: h.name for h in load_hubs().hubs},
        "generated_at": date.today().isoformat(),
    }
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(render())
