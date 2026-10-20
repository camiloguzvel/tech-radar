"""Cliente de EPO OPS v3.2 y constructor de consultas CQL por frente (ADR F0-a).

Verificado en vivo (2026-10-20):
- OAuth2 client credentials; token de ~20 min.
- `X-Throttling-Control`, p. ej. "busy (search=green:15, retrieval=green:100, ...)": el número
  es el límite de llamadas por minuto de ese servicio; puede bajar a 0 (esperar).
- `X-RegisteredQuotaPerWeek-Used`: bytes usados en la semana (cuota gratuita de 4 GB).
- JSON pesa menos de la mitad que XML (~9,5 frente a 21,7 KB por documento con biblio).
- Clasificación: se busca con `cl` (CPC ∪ IPC). Solo con `cpc` se pierde entre el 48% y el 79%
  de los documentos chinos, en una proporción que cambia de año a año.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

from radar import PROJECT_ROOT
from radar.domains.loader import Frente, KeywordSpec

AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
BASE_URL = "https://ops.epo.org/3.2/rest-services"
WEEKLY_QUOTA_STOP = int(3.5 * 1024**3)  # freno antes de los 4 GB gratuitos
MAX_RESULTS_PER_QUERY = 2000  # tope de OPS para paginar una consulta
MAX_WAIT_S = 120  # ninguna espera individual supera esto
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_THROTTLE = re.compile(r"(\w+)=(\w+):(\d+)")


class QuotaExceeded(RuntimeError):
    pass


class OpsError(RuntimeError):
    pass


@dataclass
class OpsClient:
    key: str
    secret: str
    log: list[dict] = field(default_factory=list)
    week_bytes_used: int = 0
    verbose: bool = False
    _token: str | None = None
    _token_expiry: float = 0.0
    _next_call: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> OpsClient:
        load_dotenv(PROJECT_ROOT / ".env")
        key, secret = os.environ.get("EPO_OPS_KEY"), os.environ.get("EPO_OPS_SECRET")
        if not key or not secret:
            raise SystemExit("Faltan EPO_OPS_KEY / EPO_OPS_SECRET en .env")
        return cls(key, secret)

    def _auth(self) -> str:
        if self._token is None or time.monotonic() > self._token_expiry:
            r = httpx.post(
                AUTH_URL,
                auth=(self.key, self.secret),
                data={"grant_type": "client_credentials"},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._token_expiry = time.monotonic() + int(body.get("expires_in", 1199)) - 60
        return self._token

    def _pace(self, service: str, headers: httpx.Headers) -> None:
        """Programa la próxima llamada a `service` según el límite por minuto anunciado."""
        for svc, _color, limit in _THROTTLE.findall(headers.get("x-throttling-control", "")):
            per_min = int(limit)
            gap = 60.0 if per_min == 0 else 60.0 / per_min + 0.25
            self._next_call[svc] = time.monotonic() + gap

    def get(self, path: str, service: str, params: dict, range_: str | None = None) -> dict:
        if self.week_bytes_used >= WEEKLY_QUOTA_STOP:
            raise QuotaExceeded(f"cuota semanal: {self.week_bytes_used} bytes usados")
        headers = {"Accept": "application/json"}
        if range_:
            headers["Range"] = range_
        for attempt, backoff in enumerate((0, 10, 30, 90)):
            wait = max(backoff, self._next_call.get(service, 0) - time.monotonic(), 0)
            time.sleep(min(wait, MAX_WAIT_S))
            headers["Authorization"] = f"Bearer {self._auth()}"
            started = time.monotonic()
            r = httpx.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=HTTP_TIMEOUT)
            if self.verbose:
                print(
                    f"  [{service}] {r.status_code} {len(r.content)}B "
                    f"{time.monotonic() - started:.1f}s espera={wait:.0f}s "
                    f"{(r.headers.get('x-throttling-control') or '')[:60]}",
                    flush=True,
                )
            self._pace(service, r.headers)
            used = r.headers.get("x-registeredquotaperweek-used")
            if used:
                self.week_bytes_used = int(used)
            self.log.append(
                {
                    "path": path,
                    "params": params,
                    "status": r.status_code,
                    "bytes": len(r.content),
                    "throttling": r.headers.get("x-throttling-control"),
                    "attempt": attempt,
                }
            )
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:  # OPS responde 404 cuando no hay resultados
                return {}
            # 500 SERVER.DomainAccess ("try again later") aparece con consultas pesadas
            if r.status_code in (403, 429, 500, 503) and attempt < 3:
                retry_after = r.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    if int(retry_after) > MAX_WAIT_S:  # nunca bloquear horas: fallar y registrar
                        raise OpsError(f"{r.status_code} con Retry-After={retry_after}s: {path}")
                    time.sleep(int(retry_after))
                continue
            raise OpsError(f"{r.status_code} {path} {params}: {r.text[:300]}")
        raise OpsError(f"reintentos agotados: {path} {params}")

    def count(self, cql: str) -> int:
        body = self.get("/published-data/search", "search", {"q": cql}, range_="1-1")
        if not body:
            return 0
        return int(body["ops:world-patent-data"]["ops:biblio-search"]["@total-result-count"])

    def search_biblio(self, cql: str, start: int = 1, end: int = 100) -> dict:
        return self.get("/published-data/search/biblio", "search", {"q": cql}, f"{start}-{end}")


# ---------------------------------------------------------------- CQL


def _cl(code: str) -> str:
    return f"cl=/low {code}"


def _or(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


def _ta(word: str) -> str:
    if '"' in word:
        raise ValueError(f"keyword con comillas no soportada: {word!r}")
    return f'ta="{word}"' if (" " in word or "-" in word) else f"ta={word}"


def keyword_cql(spec: KeywordSpec) -> str:
    if spec.keywords_any:
        return _or([_ta(w) for w in spec.keywords_any])
    return " and ".join(_or([_ta(w) for w in group]) for group in spec.keyword_groups)


def classification_cql(frente: Frente) -> str:
    parts = [_cl(c) for c in frente.cpc_any]
    for q in frente.cpc_qualified:
        parts.append(f"({_or([_cl(c) for c in q.codes])} and {_or([_cl(c) for c in q.with_any])})")
    return _or(parts)


def frente_cql(frente: Frente, pd_from: str, pd_to: str) -> str:
    """Consulta de un frente para publicaciones entre dos fechas AAAAMMDD (inclusive).

    En CQL `and`/`or` tienen la MISMA precedencia (izquierda a derecha): cada subexpresión
    va entre paréntesis explícitos.
    """
    cls = classification_cql(frente)
    if frente.rule == "cpc":
        body = cls
    elif frente.rule == "cpc+keyword":
        body = f"{cls} and ({keyword_cql(frente)})"
    else:
        body = f"({cls} or ({keyword_cql(frente)}))"
    return f'{body} and pd within "{pd_from} {pd_to}"'
