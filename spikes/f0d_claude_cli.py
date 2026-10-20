"""Spike F0-d: clasificación + traducción por lotes con `claude -p` (login Max) en Windows.

Lote SINTÉTICO (resúmenes escritos para la prueba, no son patentes reales) con
etiquetas esperadas, en EN/ZH/JA/KO. Mide: autenticación, conformidad con el esquema,
latencia, estabilidad entre repeticiones y exactitud sobre los casos no ambiguos.

Uso:  uv run python spikes/f0d_claude_cli.py [--repeats 3] [--model haiku]
Salida: data/spikes/f0d/<timestamp>/ (respuestas crudas + resumen.json)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from radar import PROJECT_ROOT
from radar.domains.loader import load_domains

RECORDS = [
    # id, texto, dominio esperado, frente esperado, ambiguo
    (
        "s01",
        "Electrochemical oxidation reactor with boron-doped diamond anodes that mineralizes "
        "PFOA and PFOS in contaminated groundwater to fluoride ions.",
        "agua",
        "pfas_remocion",
        False,
    ),
    (
        "s02",
        "Thin-film composite reverse osmosis membrane with a polyamide layer for seawater "
        "desalination at reduced energy consumption.",
        "agua",
        "desalinizacion_membranas",
        False,
    ),
    (
        "s03",
        "Passive device using a metal-organic framework sorbent to harvest drinking water "
        "from desert air at 20% relative humidity.",
        "agua",
        "agua_atmosferica",
        False,
    ),
    (
        "s04",
        "Base editing of the rice ALS gene with a Cas12 variant to confer herbicide "
        "tolerance without transgene integration.",
        "agrobiotech",
        "edicion_genica_vegetal",
        False,
    ),
    (
        "s05",
        "Sprayable double-stranded RNA formulation that silences an essential gene in the "
        "Colorado potato beetle on potato crops.",
        "agrobiotech",
        "rnai_spray",
        False,
    ),
    (
        "s06",
        "Wettable powder formulation of Bacillus thuringiensis spores for biological control "
        "of lepidopteran pests in maize.",
        "agrobiotech",
        "biopesticidas",
        False,
    ),
    (
        "s07",
        "Nickel-rich layered cathode material for lithium-ion batteries with improved cycle life.",
        "none",
        "none",
        False,
    ),
    (
        "s08",
        "Low-cost electrochemical sensor for detecting PFAS at ppt levels in municipal "
        "drinking water distribution networks.",
        "agua",
        "redes_inteligentes",
        True,
    ),
    (
        "s09",
        "一种用于去除饮用水中全氟和多氟烷基物质（PFAS）的电化学氧化装置，采用掺硼金刚石电极。",
        "agua",
        "pfas_remocion",
        False,
    ),
    (
        "s10",
        "海水淡水化用の逆浸透膜であって、ポリアミド分離機能層を有し、低エネルギーで運転できるもの。",
        "agua",
        "desalinizacion_membranas",
        False,
    ),
    (
        "s11",
        "질소 고정 근권 세균을 포함하여 질소 비료 사용량을 줄이는 바이오 비료 조성물.",
        "agrobiotech",
        "bioestimulantes_fijacion_n",
        False,
    ),
    (
        "s12",
        "基于物联网压力传感器和机器学习的城市供水管网漏损检测系统。",
        "agua",
        "redes_inteligentes",
        False,
    ),
    (
        "s13",
        "半導体ウェハの洗浄装置において、超純水の使用量を削減する洗浄ノズル。",
        "none",
        "none",
        True,
    ),
]


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_lang: str
    text_en: str | None
    domain: Literal["agua", "agrobiotech", "none"]
    frente: str
    confidence: float
    rationale: str


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Item]


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "source_lang",
                    "text_en",
                    "domain",
                    "frente",
                    "confidence",
                    "rationale",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "source_lang": {"type": "string", "description": "ISO 639-1"},
                    "text_en": {
                        "type": ["string", "null"],
                        "description": "English translation; null if already English",
                    },
                    "domain": {"type": "string", "enum": ["agua", "agrobiotech", "none"]},
                    "frente": {"type": "string", "description": "frente id or 'none'"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string", "description": "one short sentence"},
                },
            },
        }
    },
}


def build_instruction() -> str:
    lines = [
        "Classify each technology abstract (JSON on stdin) into exactly one frente.",
        "If the abstract is not in English, translate it faithfully into text_en.",
        "Use domain 'none' and frente 'none' when no frente fits. Do not guess.",
        "Frentes:",
    ]
    for domain in load_domains().values():
        for frente in domain.frentes:
            lines.append(f"- domain={domain.domain} frente={frente.id}: {frente.name}")
    lines.append("Return one item per input id, in the same order.")
    return "\n".join(lines)


def run_batch(model: str, tools_mode: str, timeout: int) -> dict:
    exe = shutil.which("claude")
    if exe is None:
        raise SystemExit("claude no está en el PATH")
    cmd = [
        exe,
        "-p",
        build_instruction(),
        "--safe-mode",
        "--model",
        model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
        "--no-session-persistence",
    ]
    if tools_mode == "none":
        # Bloquea también la herramienta interna StructuredOutput: no hay structured_output.
        cmd += ["--disallowedTools", "*"]
    elif tools_mode == "empty":
        cmd += ["--tools", ""]
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }
    payload = json.dumps([{"id": r[0], "text": r[1]} for r in RECORDS], ensure_ascii=False)
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=timeout,
        cwd=PROJECT_ROOT,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "seconds": round(time.perf_counter() - started, 1),
    }


def evaluate(raw: dict) -> dict:
    result: dict = {"returncode": raw["returncode"], "seconds": raw["seconds"]}
    try:
        envelope = json.loads(raw["stdout"])
    except json.JSONDecodeError as exc:
        return result | {"ok": False, "error": f"stdout no es JSON: {exc}"}
    result["envelope_keys"] = sorted(envelope)
    for key in ("total_cost_usd", "num_turns", "is_error", "subtype", "usage"):
        if key in envelope:
            result[key] = envelope[key]
    structured = envelope.get("structured_output")
    if structured is None:
        return result | {"ok": False, "error": "sin structured_output"}
    try:
        batch = Batch.model_validate(structured)
    except ValidationError as exc:
        return result | {"ok": False, "error": f"esquema pydantic: {exc}"}
    expected = {r[0]: (r[2], r[3], r[4]) for r in RECORDS}
    got = {i.id: i for i in batch.items}
    clear = [k for k, v in expected.items() if not v[2]]
    correct = [k for k in clear if k in got and (got[k].domain, got[k].frente) == expected[k][:2]]
    return result | {
        "ok": True,
        "ids_complete": set(got) == set(expected),
        "accuracy_clear": f"{len(correct)}/{len(clear)}",
        "wrong": {
            k: [got[k].domain, got[k].frente] for k in clear if k in got and k not in correct
        },
        "ambiguous": {
            k: [got[k].domain, got[k].frente, got[k].confidence]
            for k, v in expected.items()
            if v[2] and k in got
        },
        "labels": {k: got[k].frente for k in got},
        "translations": {k: got[k].text_en for k in got if got[k].text_en},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--tools", choices=["empty", "none", "default"], default="empty")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    out = PROJECT_ROOT / "data" / "spikes" / "f0d" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for i in range(args.repeats):
        try:
            raw = run_batch(args.model, args.tools, args.timeout)
        except subprocess.TimeoutExpired:
            runs.append({"ok": False, "error": f"timeout {args.timeout}s"})
            continue
        (out / f"run{i}.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        runs.append(evaluate(raw))

    labels = [r["labels"] for r in runs if r.get("ok")]
    stable = all(lbl == labels[0] for lbl in labels) if labels else None
    summary = {
        "model": args.model,
        "tools": args.tools,
        "n_records": len(RECORDS),
        "runs": runs,
        "labels_identical_across_runs": stable,
    }
    (out / "resumen.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nGuardado en {out}")


if __name__ == "__main__":
    main()
