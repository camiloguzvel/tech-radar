"""Spike F0-g: validar los símbolos CPC de los YAML contra CPC 2026.08.

Uso:  uv run python spikes/f0g_cpc.py
Lista cada símbolo con su título oficial y cuántos símbolos abarca con sus subgrupos,
para revisar el ajuste semántico y la amplitud; al final, los inválidos.
"""

from __future__ import annotations

from radar.domains.cpc import CpcScheme, FrenteCpcMatcher, canonical
from radar.domains.loader import load_domains


def show(scheme: CpcScheme, code: str, label: str, invalid: list[str], where: str) -> None:
    entry = scheme.get(code)
    if entry is None:
        invalid.append(f"{where}: {code}")
        print(f"  !! {code:14s} NO EXISTE en CPC 2026.08 ({canonical(code)})")
        return
    n = len(scheme.expand(code))
    print(f"  ok {code:14s} {label:10s} símbolos={n:5d} {entry.title[:95]}")


def main() -> None:
    scheme = CpcScheme.from_title_list()
    print(f"símbolos en la lista oficial: {len(scheme.entries)}")
    invalid: list[str] = []
    for domain in load_domains().values():
        for frente in domain.frentes:
            where = f"{domain.domain}/{frente.id}"
            print(f"\n== {where} [{frente.rule}]")
            for code in frente.cpc_any:
                show(scheme, code, "any", invalid, where)
            for q in frente.cpc_qualified:
                for code in q.codes:
                    show(scheme, code, "qualified", invalid, where)
                for code in q.with_any:
                    show(scheme, code, "contexto", invalid, where)
            if not any(where in i for i in invalid):
                matcher = FrenteCpcMatcher(frente, scheme)
                print(f"  -> símbolos suficientes por sí solos: {len(matcher.any)}")
        for code in domain.exclude.cpc_only_if_alone:
            show(scheme, code, "exclude", invalid, f"{domain.domain}/exclude")
    print(f"\ninválidos: {len(invalid)}")
    for item in invalid:
        print("  -", item)


if __name__ == "__main__":
    main()
