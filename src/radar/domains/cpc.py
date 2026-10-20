"""Símbolos CPC: validación contra la lista oficial y expansión jerárquica (ADR F0-g).

Fuente: CPCTitleList<version>.zip de cooperativepatentclassification.org, guardado en
`data/ref/cpc-<version>/` (no versionado). Cada línea: `símbolo<TAB>nivel<TAB>título`,
en orden del esquema. Nivel vacío = sección/clase/subclase; "0" = grupo principal;
"1", "2"... = subgrupos (los puntos del esquema).

Un código de los YAML incluye todos sus descendientes. La jerarquía de subgrupos NO es
un prefijo de texto (C02F1/44 no contiene a C02F1/42), por eso se expande con los niveles.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from radar import PROJECT_ROOT
from radar.domains.loader import Domain, Frente

DEFAULT_TITLE_LIST = PROJECT_ROOT / "data" / "ref" / "cpc-202608" / "CPCTitleList202608.zip"


@dataclass(frozen=True)
class CpcEntry:
    symbol: str
    level: str
    title: str


class CpcScheme:
    def __init__(self, entries: list[CpcEntry]) -> None:
        self.entries = entries
        self.index = {e.symbol: i for i, e in enumerate(entries)}

    @classmethod
    def from_title_list(cls, path: Path = DEFAULT_TITLE_LIST) -> CpcScheme:
        entries: list[CpcEntry] = []
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                for line in zf.read(name).decode("utf-8").splitlines():
                    symbol, level, title = (line.split("\t") + ["", ""])[:3]
                    if symbol:
                        entries.append(CpcEntry(symbol, level, title))
        return cls(entries)

    def get(self, code: str) -> CpcEntry | None:
        i = self.index.get(canonical(code))
        return self.entries[i] if i is not None else None

    def expand(self, code: str) -> frozenset[str]:
        """El código y todos sus descendientes. KeyError si no existe."""
        symbol = canonical(code)
        start = self.index[symbol]
        entry = self.entries[start]
        if entry.level == "":  # sección, clase o subclase: por prefijo
            return frozenset(e.symbol for e in self.entries if e.symbol.startswith(symbol))
        out = {symbol}
        depth = int(entry.level)
        main_group = symbol.split("/")[0] + "/"
        for e in self.entries[start + 1 :]:
            if e.level == "" or not e.symbol.startswith(main_group) or int(e.level) <= depth:
                break
            out.add(e.symbol)
        return frozenset(out)


def canonical(code: str) -> str:
    """Los YAML admiten grupo principal sin '/00' (p. ej. "B01J20" == "B01J20/00")."""
    if len(code) > 4 and "/" not in code:
        return f"{code}/00"
    return code


def domain_codes(domain: Domain) -> list[tuple[str, str]]:
    """(dónde, código) de todas las referencias CPC de un dominio."""
    refs: list[tuple[str, str]] = []
    for frente in domain.frentes:
        where = f"{domain.domain}/{frente.id}"
        refs += [(where, c) for c in frente.cpc_any]
        for q in frente.cpc_qualified:
            refs += [(where, c) for c in (*q.codes, *q.with_any)]
    refs += [(f"{domain.domain}/exclude", c) for c in domain.exclude.cpc_only_if_alone]
    return refs


def invalid_codes(domains: dict[str, Domain], scheme: CpcScheme) -> list[str]:
    return [
        f"{where}: {code}"
        for domain in domains.values()
        for where, code in domain_codes(domain)
        if scheme.get(code) is None
    ]


class FrenteCpcMatcher:
    """Parte CPC de la regla de un frente, con los códigos ya expandidos."""

    def __init__(self, frente: Frente, scheme: CpcScheme) -> None:
        self.any = frozenset().union(*(scheme.expand(c) for c in frente.cpc_any))
        self.qualified = [
            (
                frozenset().union(*(scheme.expand(c) for c in q.codes)),
                frozenset().union(*(scheme.expand(c) for c in q.with_any)),
            )
            for q in frente.cpc_qualified
        ]

    def matches(self, family_cpcs: set[str]) -> bool:
        if family_cpcs & self.any:
            return True
        return any(family_cpcs & codes and family_cpcs & ctx for codes, ctx in self.qualified)
