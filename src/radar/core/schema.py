"""Contratos de datos del radar, en tres capas: dato, señal e interpretación.

Las tablas de entidades (dato) son tipadas y anchas. Las métricas (señal) van en formato
largo en `Observation`. La interpretación (`Signal`) siempre se apoya en filas de `Evidence`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IP5_OFFICES = frozenset({"US", "EP", "CN", "JP", "KR"})

Layer = Literal["science", "patent", "capital", "market"]
Lens = Literal["all", "international"]
GeoType = Literal["global", "bloc", "country", "hub"]
HubMethod = Literal["radius", "country", "manual"]


def stable_id(*parts: object) -> str:
    """Hash determinista (16 hex) de una clave compuesta; mismo input => mismo id."""
    payload = json.dumps([str(p) for p in parts], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(_Record):
    """Trazabilidad mínima de cualquier registro extraído de una fuente."""

    source: str
    url: str
    extracted_at: datetime
    run_id: str


# ---------------------------------------------------------------- CAPA DATO


class PatentDoc(_Record):
    """Staging: una fila por publicación (documento DOCDB)."""

    doc_id: str  # p. ej. "EP.3456789.A1"
    family_id: str  # DOCDB simple family
    office: str  # código de país de la oficina (US, EP, CN, JP, KR, WO, ...)
    kind: str  # A1, B1, U, ...
    is_utility_model: bool
    pub_date: date
    appl_date: date | None = None
    earliest_priority_date: date
    cpc: list[str] = Field(default_factory=list)
    ipc: list[str] = Field(default_factory=list)
    applicants_raw: list[str] = Field(default_factory=list)
    applicant_countries: list[str] = Field(default_factory=list)  # sufijo [CC] de OPS
    title_en: str | None = None
    abstract_en: str | None = None
    abstract_orig_lang: str | None = None
    provenance: Provenance
    raw_ref: str  # ruta del archivo crudo en data/raw


class Family(_Record):
    """Core: una fila por familia. Es la unidad de conteo de patentes."""

    family_id: str
    earliest_priority_date: date
    first_pub_date: date
    offices: frozenset[str]
    has_pct: bool
    only_utility_models: bool
    cpc_union: list[str] = Field(default_factory=list)
    applicant_ids: list[str] = Field(default_factory=list)
    applicant_country_weights: dict[str, float] = Field(default_factory=dict)
    text_en: str | None = None
    text_source: Literal["original_en", "docdb_en", "llm_translation"] | None = None

    @property
    def n_ip5_offices(self) -> int:
        return len(self.offices & IP5_OFFICES)

    @property
    def is_international(self) -> bool:
        """Lente "international": ≥2 oficinas IP5 o solicitud PCT."""
        return self.n_ip5_offices >= 2 or self.has_pct

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Family:
        if self.applicant_country_weights:
            total = sum(self.applicant_country_weights.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"applicant_country_weights suman {total}, deben sumar 1")
        return self


class Applicant(_Record):
    """Core: diccionario de normalización de solicitantes."""

    applicant_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    country: str | None = None
    type: Literal["company", "university", "individual", "gov", "unknown"] = "unknown"
    hub: str | None = None
    hub_method: HubMethod | None = None
    first_seen_by_frente: dict[str, date] = Field(default_factory=dict)


class Work(_Record):
    """Staging: una publicación científica de OpenAlex."""

    work_id: str
    doi: str | None = None
    pub_date: date
    type: str
    primary_topic_id: str | None = None
    topic_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    institution_ids: list[str] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    abstract: str | None = None  # reconstruido desde abstract_inverted_index
    cited_by_count: int = 0
    fwci: float | None = None
    provenance: Provenance


class Institution(_Record):
    """Core: institución de OpenAlex con su hub asignado."""

    institution_id: str
    ror: str | None = None
    type: str
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    hub: str | None = None
    hub_method: HubMethod | None = None


class Membership(_Record):
    """Core: una entidad pertenece a un frente, y por qué regla."""

    entity_id: str
    entity_type: Literal["family", "work"]
    domain: str
    frente: str
    rule: Literal["cpc", "topic", "keyword", "cpc+keyword", "llm"]
    llm_label_id: str | None = None
    confidence: float = Field(ge=0, le=1)


# ---------------------------------------------------------------- CAPA SEÑAL


class Observation(_Record):
    """Marts: una métrica para un frente × geo × lente × periodo (formato largo)."""

    observation_id: str
    period_start: date
    period_end: date
    granularity: Literal["M", "Q", "Y"]
    layer: Layer
    domain: str
    frente: str | None = None
    geo_type: GeoType
    geo: str
    lens: Lens
    variable: str
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    n_basis: int = Field(ge=0)
    provisional: bool
    completeness: float | None = Field(default=None, ge=0, le=1)
    source: str
    method_version: str
    run_id: str
    computed_at: datetime

    @model_validator(mode="after")
    def _period_order(self) -> Observation:
        if self.period_end < self.period_start:
            raise ValueError("period_end anterior a period_start")
        return self


# ---------------------------------------------------------------- CAPA INTERPRETACIÓN


class Evidence(_Record):
    """Respaldo de una señal. Toda señal tiene al menos una."""

    signal_id: str
    kind: Literal["observation", "family", "work", "url"]
    ref: str
    url: str
    extracted_at: datetime
    note: str = ""


class Signal(_Record):
    signal_id: str
    run_id: str
    domain: str
    frente: str
    geo: str
    type: Literal[
        "inflection_up",
        "inflection_down",
        "leadership_shift",
        "entrant_wave",
        "science_ahead",
        "convergence",
        "concentration",
    ]
    direction: Literal["up", "down"]
    magnitude: float
    score: float = Field(ge=0, le=1)
    confidence: Literal["alta", "media", "baja"]
    confidence_reasons: list[str] = Field(default_factory=list)
    action: Literal["investigar", "vigilar", "descartar"]
    why_now: str | None = None  # borrador LLM, editado por humano
    bear_case: str | None = None
    interpretation_status: Literal["auto", "draft", "reviewed"] = "auto"
    first_seen_run: str
    persistence: int = Field(default=1, ge=1)


class RunLog(_Record):
    """Bitácora de cada llamada o lote a una fuente; los fallos quedan registrados."""

    run_id: str
    started_at: datetime
    source: str
    query: str
    status: Literal["ok", "partial", "error"]
    n_records: int = 0
    bytes: int = 0
    cost_usd: float | None = None
    error: str | None = None
