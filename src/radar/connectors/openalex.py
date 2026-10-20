"""Cliente de OpenAlex y construcción de filtros por frente (ADR F0-c).

Límites verificados (2026-10-19/20):
- máximo 100 valores OR por filtro (más devuelve HTTP 400);
- `title_and_abstract.search` acepta OR/AND, comillas y paréntesis, y cuesta 10x
  una consulta de lista (US$0,001 frente a US$0,0001 por llamada);
- consultas con muchos valores OR seguidas reciben 429: espaciar y reintentar con backoff;
- `per_page=200` funciona con cursor (cuesta lo mismo por página que 100);
- presupuesto en cabeceras: `x-ratelimit-limit-usd` y `x-ratelimit-remaining-usd` (diario, UTC).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date

import httpx
from dotenv import load_dotenv

from radar import PROJECT_ROOT
from radar.domains.loader import KeywordSpec, ScienceDef

BASE_URL = "https://api.openalex.org"
DAILY_BRAKE_USD = 0.80  # freno propio antes del US$1/día gratuito
MAX_OR_VALUES = 100
# Excluye peer-review ("decision letters"), paratext, erratas, etc. (ADR F0-c).
WORK_TYPES = ("article", "review", "preprint")


def _term(word: str) -> str:
    """Las frases (con espacio o guion) van entre comillas."""
    if '"' in word:
        raise ValueError(f"keyword con comillas no soportada: {word!r}")
    return f'"{word}"' if (" " in word or "-" in word) else word


def _or_group(words: list[str]) -> str:
    return "(" + " OR ".join(_term(w) for w in words) + ")"


def search_expression(spec: KeywordSpec) -> str:
    """Expresión booleana para `title_and_abstract.search`."""
    if spec.keywords_any:
        return _or_group(spec.keywords_any)
    return " AND ".join(_or_group(group) for group in spec.keyword_groups)


def works_filter(
    science: ScienceDef,
    since: date | None = None,
    until: date | None = None,
    types: tuple[str, ...] = WORK_TYPES,
) -> str:
    """Filtro `/works` de un frente; requiere topics resueltos si la regla los usa.

    `until` corta fechas de publicación futuras o erróneas (OpenAlex trae p. ej. 2045).
    """
    parts: list[str] = []
    if science.rule in ("topic", "topic+keyword"):
        ids = [t.id for t in science.topics]
        if any(i is None for i in ids):
            raise ValueError("hay topics sin resolver (id None)")
        if len(ids) > MAX_OR_VALUES:
            raise ValueError(f"más de {MAX_OR_VALUES} topics en un filtro")
        parts.append("primary_topic.id:" + "|".join(ids))
    if science.rule in ("topic+keyword", "keyword"):
        parts.append("title_and_abstract.search:" + search_expression(science))
    if since is not None:
        parts.append(f"from_publication_date:{since.isoformat()}")
    if until is not None:
        parts.append(f"to_publication_date:{until.isoformat()}")
    if types:
        parts.append("type:" + "|".join(types))
    return ",".join(parts)


# ---------------------------------------------------------------- cliente


class BudgetExhausted(RuntimeError):
    """Se alcanzó el freno diario; reanudar después de medianoche UTC."""


class OpenAlexError(RuntimeError):
    pass


@dataclass
class OpenAlexClient:
    api_key: str
    daily_brake_usd: float = DAILY_BRAKE_USD
    min_interval_s: float = 1.0
    transport: httpx.BaseTransport | None = None  # inyectable en tests
    sleep: Callable[[float], None] = time.sleep
    verbose: bool = False
    calls: list[dict] = field(default_factory=list)
    spent_today_usd: float = 0.0
    _last_call: float = 0.0

    def __post_init__(self) -> None:
        self._http = httpx.Client(
            base_url=BASE_URL,
            params={"api_key": self.api_key},
            timeout=httpx.Timeout(90.0, connect=15.0),
            transport=self.transport,
        )

    @classmethod
    def from_env(cls, **kwargs) -> OpenAlexClient:
        load_dotenv(PROJECT_ROOT / ".env")
        key = os.environ.get("OPENALEX_API_KEY")
        if not key:
            raise SystemExit("Falta OPENALEX_API_KEY en .env")
        return cls(key, **kwargs)

    def _update_budget(self, headers: httpx.Headers) -> None:
        limit, remaining = (
            headers.get("x-ratelimit-limit-usd"),
            headers.get("x-ratelimit-remaining-usd"),
        )
        if limit and remaining:
            self.spent_today_usd = round(float(limit) - float(remaining), 6)

    def get(self, path: str, params: dict) -> dict:
        if self.spent_today_usd >= self.daily_brake_usd:
            raise BudgetExhausted(f"gastado hoy US${self.spent_today_usd:.3f}")
        for attempt, backoff in enumerate((0, 5, 15, 45)):
            wait = max(backoff, self.min_interval_s - (time.monotonic() - self._last_call))
            if wait > 0:
                self.sleep(wait)
            self._last_call = time.monotonic()
            r = self._http.get(path, params=params)
            self._update_budget(r.headers)
            body = (
                r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            )
            self.calls.append(
                {
                    "path": path,
                    "params": params,
                    "status": r.status_code,
                    "bytes": len(r.content),
                    "cost_usd": (body.get("meta") or {}).get("cost_usd"),
                    "attempt": attempt,
                }
            )
            if self.verbose:
                print(
                    f"  [openalex] {r.status_code} {len(r.content)}B "
                    f"hoy=US${self.spent_today_usd:.3f}",
                    flush=True,
                )
            if r.status_code == 200:
                return body
            if r.status_code == 429 or r.status_code >= 500:
                continue
            raise OpenAlexError(
                f"{r.status_code} {path}: {(body or {}).get('message', r.text[:200])}"
            )
        raise OpenAlexError(f"reintentos agotados: {path} {params}")

    def paginate(self, path: str, params: dict) -> Iterator[dict]:
        """Recorre todas las páginas con cursor; devuelve cada respuesta completa."""
        cursor = "*"
        while cursor:
            body = self.get(path, {**params, "cursor": cursor})
            yield body
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not body.get("results") and not body.get("group_by"):
                break
