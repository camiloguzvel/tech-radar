"""Carga y validación de definiciones de dominio, hubs y eventos de backtest (YAML)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from radar import DOMAINS_DIR
from radar.core.config import HISTORY_START

NON_DOMAIN_FILES = {"hubs.yaml", "backtest_events.yaml"}

# Símbolo CPC/IPC a nivel subclase, grupo principal o subgrupo:
# "C02F", "B01J20", "C02F1/28", "C02F2103/08", "C12R2001".
CPC_PATTERN = re.compile(r"^[A-HY]\d{2}[A-Z](\d{1,4}(/\d{2,6})?)?$")
SLUG_PATTERN = r"^[a-z][a-z0-9_]*$"


def _check_cpc(code: str) -> str:
    if not CPC_PATTERN.match(code):
        raise ValueError(f"símbolo CPC con formato inválido: {code!r}")
    return code


CpcCode = Annotated[str, AfterValidator(_check_cpc)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TopicRef(_Model):
    """Topic de OpenAlex. `id` queda en None hasta resolverlo (spike F0-c)."""

    name: str
    id: str | None = Field(default=None, pattern=r"^T\d+$")


class Frente(_Model):
    """Unidad de detección de señales.

    Regla de pertenencia:
    - `cpc`: alguna clase de `cpc_any`.
    - `cpc+keyword`: alguna clase de `cpc_any` Y coincidencia de keywords.
    - `cpc|keyword`: alguna clase de `cpc_any` O coincidencia de keywords.
    Keywords: alguna de `keywords_any`, o bien cada grupo de `keyword_groups`
    con al menos una coincidencia (AND entre grupos, OR dentro de cada grupo).
    """

    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    rule: Literal["cpc", "cpc+keyword", "cpc|keyword"]
    cpc_any: list[CpcCode] = Field(default_factory=list)
    cpc_combined_with: list[CpcCode] = Field(default_factory=list)
    keywords_any: list[str] = Field(default_factory=list)
    keyword_groups: list[list[str]] = Field(default_factory=list)
    openalex_topics: list[TopicRef] = Field(default_factory=list)

    @property
    def has_keywords(self) -> bool:
        return bool(self.keywords_any or self.keyword_groups)

    @model_validator(mode="after")
    def _rule_has_inputs(self) -> Frente:
        if not self.cpc_any:
            raise ValueError(f"frente {self.id}: la regla {self.rule!r} requiere cpc_any")
        if self.rule != "cpc" and not self.has_keywords:
            raise ValueError(f"frente {self.id}: la regla {self.rule!r} requiere keywords")
        if any(not group for group in self.keyword_groups):
            raise ValueError(f"frente {self.id}: keyword_groups no admite grupos vacíos")
        return self


class Exclusions(_Model):
    cpc_only_if_alone: list[CpcCode] = Field(default_factory=list)
    keywords_any: list[str] = Field(default_factory=list)


class Domain(_Model):
    domain: str = Field(pattern=SLUG_PATTERN)
    name: str
    role: Literal["thesis", "calibration"] = "thesis"  # calibration: fuera del memo
    version: str
    thesis: str
    frentes: list[Frente] = Field(min_length=1)
    exclude: Exclusions = Field(default_factory=Exclusions)
    lenses: list[Literal["all", "international"]] = Field(default=["all", "international"])
    min_families_per_period: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _unique_frentes(self) -> Domain:
        ids = [f.id for f in self.frentes]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"dominio {self.domain}: frentes duplicados {sorted(dupes)}")
        return self

    def unresolved_topics(self) -> list[tuple[str, str]]:
        return [(f.id, t.name) for f in self.frentes for t in f.openalex_topics if t.id is None]


class HubCenter(_Model):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0)


class Hub(_Model):
    """Hub geográfico: radios alrededor de centros, restringidos a ciertos países.

    Si `whole_country` es True, toda institución de esos países pertenece al hub.
    """

    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    countries: list[str] = Field(min_length=1)
    centers: list[HubCenter] = Field(default_factory=list)
    whole_country: bool = False

    @model_validator(mode="after")
    def _has_geometry(self) -> Hub:
        if not self.whole_country and not self.centers:
            raise ValueError(f"hub {self.id}: requiere centers o whole_country")
        return self


class HubsConfig(_Model):
    version: str
    hubs: list[Hub] = Field(min_length=1)


class BacktestEvent(_Model):
    """Evento histórico pre-registrado para el backtest (§7 del plan)."""

    id: str = Field(pattern=SLUG_PATTERN)
    domain: str
    frente: str
    description: str
    expected_window: tuple[int, int]
    mainstream_date: str | None = None  # AAAA o AAAA-MM; lo valida Camilo
    source: str | None = None  # referencia citable; nunca inventada
    status: Literal["propuesto", "validado", "descartado"] = "propuesto"
    note: str | None = None

    @model_validator(mode="after")
    def _window_within_history(self) -> BacktestEvent:
        start, end = self.expected_window
        if end < start:
            raise ValueError(f"evento {self.id}: expected_window invertida")
        if start < HISTORY_START.year:
            raise ValueError(
                f"evento {self.id}: la ventana empieza antes del histórico ({HISTORY_START.year})"
            )
        return self


class BacktestConfig(_Model):
    version: str
    events: list[BacktestEvent]


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_domain(path: Path) -> Domain:
    return Domain.model_validate(_read_yaml(path))


def load_domains(directory: Path = DOMAINS_DIR) -> dict[str, Domain]:
    domains: dict[str, Domain] = {}
    for path in sorted(directory.glob("*.yaml")):
        if path.name in NON_DOMAIN_FILES:
            continue
        domain = load_domain(path)
        if domain.domain != path.stem:
            raise ValueError(f"{path.name}: el campo domain debe ser {path.stem!r}")
        domains[domain.domain] = domain
    return domains


def load_hubs(path: Path = DOMAINS_DIR / "hubs.yaml") -> HubsConfig:
    return HubsConfig.model_validate(_read_yaml(path))


def load_backtest(
    domains: dict[str, Domain], path: Path = DOMAINS_DIR / "backtest_events.yaml"
) -> BacktestConfig:
    config = BacktestConfig.model_validate(_read_yaml(path))
    for event in config.events:
        domain = domains.get(event.domain)
        if domain is None:
            raise ValueError(f"evento {event.id}: dominio desconocido {event.domain!r}")
        if event.frente not in {f.id for f in domain.frentes}:
            raise ValueError(f"evento {event.id}: frente desconocido {event.frente!r}")
    return config
