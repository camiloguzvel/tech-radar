"""Backend LLM: `claude -p` con el login Max (ADR F0-d).

- Exige `authMethod == "claude.ai"` antes de cada lote (evita facturación por API).
- Quita ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN del entorno del subproceso.
- `--tools ""` (no `--disallowedTools "*"`, que bloquea StructuredOutput) y `--safe-mode`.
- Salida en `structured_output`; si falta, se reintenta una vez y luego se falla con error.
- Caché en data/cache/llm/ por hash(modelo + instrucción + esquema + entrada).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess

from radar import PROJECT_ROOT

CACHE = PROJECT_ROOT / "data" / "cache" / "llm"


class LLMError(RuntimeError):
    pass


def _env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }


def _exe() -> str:
    exe = shutil.which("claude")
    if exe is None:
        raise LLMError("claude no está en el PATH")
    return exe


def check_subscription_auth() -> None:
    r = subprocess.run(
        [_exe(), "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_env(),
        timeout=60,
    )
    try:
        method = json.loads(r.stdout).get("authMethod")
    except json.JSONDecodeError as exc:
        raise LLMError(f"no se pudo leer `claude auth status`: {r.stdout[:200]}") from exc
    if method != "claude.ai":
        raise LLMError(f"autenticación {method!r}: se exige el login de suscripción (claude.ai)")


def run_structured(
    instruction: str, payload: object, schema: dict, model: str = "opus", timeout: int = 600
) -> tuple[dict, dict]:
    """Devuelve (structured_output, metadatos). Usa caché si la misma llamada ya se hizo."""
    stdin = json.dumps(payload, ensure_ascii=False)
    key = hashlib.sha256(
        json.dumps([model, instruction, schema, stdin], ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cached = CACHE / f"{key}.json"
    if cached.exists():
        hit = json.loads(cached.read_text(encoding="utf-8"))
        return hit["structured_output"], hit["meta"] | {"cache": True}
    cmd = [
        _exe(),
        "-p",
        instruction,
        "--safe-mode",
        "--model",
        model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        "--tools",
        "",
        "--no-session-persistence",
    ]
    last_error = ""
    for _attempt in range(2):
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_env(),
            timeout=timeout,
            cwd=PROJECT_ROOT,
        )
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last_error = (
                f"stdout no es JSON (rc={proc.returncode}): {proc.stdout[:200]} {proc.stderr[:200]}"
            )
            continue
        out = envelope.get("structured_output")
        if out is None:
            last_error = f"sin structured_output: {str(envelope.get('result'))[:200]}"
            continue
        meta = {
            "model": model,
            "total_cost_usd_equiv": envelope.get("total_cost_usd"),
            "duration_ms": envelope.get("duration_ms"),
            "cache": False,
        }
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(
            json.dumps({"structured_output": out, "meta": meta}, ensure_ascii=False),
            encoding="utf-8",
        )
        return out, meta
    raise LLMError(last_error)
