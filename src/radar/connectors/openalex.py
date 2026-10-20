"""Construcción de filtros de OpenAlex a partir de las definiciones de frente (ADR F0-c).

Límites verificados (2026-10-19):
- máximo 100 valores OR por filtro (más devuelve HTTP 400);
- `title_and_abstract.search` acepta OR/AND, comillas y paréntesis, y cuesta 10x
  una consulta de lista (US$0,001 frente a US$0,0001 por llamada);
- consultas con muchos valores OR seguidas reciben 429: espaciar y reintentar con backoff.
"""

from __future__ import annotations

from datetime import date

from radar.domains.loader import KeywordSpec, ScienceDef

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
