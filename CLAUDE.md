# Radar Tecnológico — reglas del proyecto

## Propósito
Detectar frentes tecnológicos que cruzan un punto de inflexión (dónde, quién, por qué ahora) con evidencia trazable.
No medir "cuánta tecnología hay". Plan completo y decisiones: `docs/plan.md`; ADRs de spikes: `docs/decisions/`.

## Conceptos
- **Dominio** = unidad de tesis (`domains/<id>.yaml`). **Frente** = subdominio estrecho, unidad de detección de señales.
- Capas: **dato** (`data/staging`, `data/core`) · **señal** (`data/marts`, determinista) · **interpretación** (borradores revisados por humano).
- Pilotos MVP: `agua`, `agrobiotech`. Fuentes MVP: EPO OPS (patentes) + OpenAlex (ciencia).

## Reglas de datos (no negociables)
- Nunca inventar, imputar ni "rellenar" datos. Si una fuente falla: registrar en `runs`/`errors` y dejar el hueco visible.
- Unidad de conteo de patentes = familia DOCDB. Nunca contar documentos.
- Toda observación lleva `source`, `url`, `extracted_at`, `run_id`, `method_version` y `provisional`.
- Toda señal tiene ≥1 fila en `evidence`. Sin evidencia no hay señal.
- Periodos con completitud < 0.9 se marcan provisional; < 0.5 no disparan señales.
- Reportar siempre las dos lentes (`all` / `international`) cuando haya patentes CN.
- Patentes: geografía a nivel país/bloque. Hubs solo para ciencia (geo de instituciones) o tabla curada (`hub_method="manual"`).

## Reglas de código
- Python ≥3.12 con uv. Polars (no pandas en código nuevo), DuckDB, Parquet. ruff + pytest. Validación pandera en cada frontera de capa.
- Contratos en `src/radar/core/schema.py`; definiciones de dominio validadas por `src/radar/domains/loader.py`.
- Conectores idempotentes, con caché raw, reintentos con backoff y respeto de cuotas
  (OPS: semáforo `X-Throttling-Control` + freno 3,5 GB/semana; OpenAlex: freno US$0,80/día vía `meta.cost_usd`).
- Cambios en definiciones de dominio o en umbrales ⇒ subir `version`/`method_version` y re-ejecutar evals.
- No commitear `data/`, `.env` ni datos crudos de OPS (licencia: no redistribuir).
- Windows: abrir archivos con `encoding="utf-8"` explícito.
- OpenAlex (ADR F0-c): filtros con `radar.connectors.openalex.works_filter` (≤100 valores OR,
  `type:article|review|preprint`, `to_publication_date` = hoy); espaciar ≥1 s y reintentar el 429 con
  backoff; métricas científicas sobre participación (frente / total anual), nunca conteos crudos.
- Cambios a un bloque `science` se justifican con los sets etiquetados, no mirando series (evita sobreajuste).
- CPC (ADR F0-g): leer el título oficial antes de añadir un código; cada código incluye sus subgrupos por
  jerarquía (`CpcScheme.expand`), nunca por prefijo de texto; los códigos amplios van en `cpc_qualified`
  con un contexto. `radar validate` verifica la existencia si `data/ref/cpc-202608/` está descargado.
- EPO OPS (ADR F0-a): usar `radar.connectors.epo_ops` (`OpsClient`, `frente_cql`). Buscar con `cl` (CPC ∪ IPC),
  nunca solo `cpc`; JSON, no XML; respetar `X-Throttling-Control` (puede ser 0) y no esperar nunca más de 120 s;
  en CQL `and`/`or` tienen igual precedencia: paréntesis explícitos. Frentes: descarga completa; campos padre:
  solo conteos. Correr scripts largos con `python -u` y registro por llamada.
- Texto en inglés (ADR F0-e): DOCDB primero (CN/KR 100%, JP 52%); traducir con Claude solo lo que falte.

## Reglas para LLM
- Usar LLM solo para: casos frontera de clasificación, traducción residual, nombres de clusters, borradores de memo.
- Backend por defecto (ADR F0-d): `claude -p --safe-mode --model haiku --output-format json --json-schema ... --tools ""
  --no-session-persistence`, lote por stdin, leer `structured_output`. Quitar `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN`
  del entorno del subproceso y exigir `authMethod == "claude.ai"`. No usar `--bare` (desactiva el login de suscripción)
  ni `--disallowedTools "*"` (bloquea la herramienta interna StructuredOutput).
- Siempre salida JSON validada con esquema; cachear por hash(entrada + versión de prompt).
- Al redactar why_now/bear_case: citar evidence_ids; si no hay evidencia, escribir "sin evidencia suficiente".
- Nunca presentar un borrador como conclusión revisada.

## Comandos
- `uv sync` — instalar dependencias
- `uv run radar validate [--strict]` — validar dominios y hubs
- `uv run pytest` — tests
- `uv run ruff check . && uv run ruff format --check .` — lint

## Idioma
Código e identificadores en inglés; reportes, fichas y docs en español.
