# Plan — Radar Tecnológico Global (MVP: Agua + Agrobiotech)

> Documento de planificación. Fuentes verificadas en vivo el 2026-10-19. Lo marcado **[NV]** = no verificado (con motivo).
> Decisiones ya tomadas por Camilo: pilotos **Agua + Agrobiotech**; **memo mensual + digest semanal**; ejecución **local en Windows**; LLM vía **Claude Code (plan Max)**, sin API de pago.

---

## Decisiones tras la aprobación (2026-10-19)

Respuestas a las preguntas abiertas de §12:

| # | Pregunta | Decisión | Efecto en el plan |
|---|---|---|---|
| 1 | Dedicación | **4–5 h/semana** | El MVP pasa a ~16–20 semanas. El clustering (F2b) sale del MVP y pasa a F3 |
| 2 | Histórico | **2014 → hoy** | Backfill más corto. El evento CRISPR (2015–19) queda con poca línea base y se toma como caso débil |
| 3 | Hubs en patentes | **Lente país/bloque** en el MVP | Sin cambios: hubs solo en ciencia; tabla curada de solicitantes en F3 |
| 4 | Interpretación | **Borrador que Camilo edita** | Sin cambios (`interpretation_status: draft` → `reviewed`) |
| 5 | Backtest | Validados: PFAS, CRISPR, agua atmosférica, bioestimulantes. RNAi en spray sigue *propuesto* | `domains/backtest_events.yaml` |
| 6 | Frente de control | **Sí**, ion-sodio, solo para calibrar | `domains/control.yaml` con `role: calibration`; no aparece en el memo |
| 7 | Repositorio | **GitHub privado** (código; datos locales) | git local ahora; el remoto se crea cuando Camilo indique el nombre |

ADR F0-d (`docs/decisions/F0-d-claude-cli.md`): el backend LLM usa `--tools ""`, no `--disallowedTools "*"`.

ADR F0-c (`docs/decisions/F0-c-openalex.md`): los topics de OpenAlex son demasiado gruesos. Cada
frente tiene un bloque `science` (`topic`, `topic+keyword` o `keyword`) que reemplaza a
`openalex_topics` del §5. Las métricas científicas se normalizan por el total anual de OpenAlex.

---

## Context

Camilo quiere un sistema personal, de costo ~0, que detecte qué tecnologías cruzan un punto de inflexión (dónde, quién, por qué ahora) con evidencia trazable, para decidir dónde invertir atención, aprendizaje y capital. La carpeta del proyecto está vacía: esto es un greenfield. El plan prioriza un MVP pequeño y confiable (2 dominios, 2 fuentes, 2 salidas) sobre un sistema amplio.

---

## 1. Reformulación del problema y supuestos

**Problema reformulado.** No es un "monitor de patentes", es un *detector de cambios de pendiente* sobre series normalizadas, en tres capas que avanzan con desfase (ciencia → patente → mercado/capital). Un **frente** (subdominio estrecho, p. ej. "remoción de PFAS") es la unidad de detección; el **dominio** (Agua) es la unidad de tesis. Las inflexiones casi nunca son visibles a nivel dominio agregado: "Agua" crece lento siempre; "PFAS" no.

**Críticas al brief (y alternativa propuesta)**

| # | Del brief | Problema | Propuesta |
|---|---|---|---|
| 1 | 11 dominios × IP5 × 11 hubs × 4 capas × 6 salidas | Inmantenible para una persona; nunca llega a calibrarse | MVP = 2 dominios, OpenAlex + EPO OPS, memo + ficha. Dominios se agregan de 2 en 2 solo tras pasar el gate de evaluación |
| 2 | Dominio como unidad | Agregados diluyen la señal | Dominio = tesis; **frente** = unidad de señal (3–6 frentes por dominio en YAML) |
| 3 | Hubs para patentes | EPO OPS no trae direcciones (solo `[CC]` del solicitante) | Patentes: lente **país/bloque**. Hubs: solo ciencia (geo de instituciones OpenAlex) + tabla curada top-solicitantes→hub (sesgo sede central, documentado) |
| 4 | Contrato único en formato largo para todo | Pierde tipado, caro de validar, mezcla dato y métrica | Tablas de entidades tipadas (dato) + `observations` largo solo para métricas (señal) + `signals`/`evidence` (interpretación) |
| 5 | "Agricultura regenerativa" | Es una práctica, casi no se patenta | Renombrar: **Agrobiotech y bioinsumos** (edición génica vegetal, biológicos, RNAi, microbios fijadores N) + frente "agricultura de precisión" |
| 6 | "IA y semiconductores", "Materiales avanzados", "Salud digital", "Construcción sostenible" | Demasiado amplios/difusos | Partir/estrechar en F3 (ver §5) |
| 7 | "AI governance" como dominio | No es tecnología; patentes irrelevantes | Capa transversal de *market pull* (regulación/estándares) que afecta a todos los dominios |
| 8 | Capital global | No existe fuente gratuita (Crunchbase/Dealroom = enterprise) | Proxies honestos: subvenciones (CORDIS, NWO, RVO, NSF/NIH), SEC Form D (solo EE.UU.). Ausencia de dato ≠ ausencia de capital |
| 9 | Volumen de patentes chinas | Modelos de utilidad (kind U) y solicitudes domésticas inflan conteos | Doble lente: **todas las familias** vs **familias internacionales** (≥2 oficinas o PCT). Liderazgo y calidad se miden en la segunda |
| 10 | Detección de inflexión en series anuales | ~10 puntos, rezago 18 m → estadística frágil | Series trimestrales por fecha de prioridad + nowcasting; exigir confirmación multi-capa para "Investigar"; curvas S solo descriptivas |
| 11 | Claude para traducir todo CN/JP/KR | Innecesario: DOCDB trae títulos/resúmenes en inglés para la mayoría | Reglas primero; LLM solo para residuales, nombres de clusters, borradores de memo |
| 12 | Memo semanal | Patentes no cambian semana a semana | Memo mensual + digest semanal de capas rápidas (decidido) |

**Supuestos que debes validar**
- A1. ~8–10 h/semana de dedicación (calibra el cronograma) → pregunta abierta.
- A2. Ventana histórica 2010–hoy es suficiente para calibrar (afecta cuota OPS).
- A3. Lente país para patentes es aceptable en el MVP.
- A4. Uso de `claude -p` con tu login Max a volúmenes modestos encaja en "uso individual ordinario" (la política no define el umbral; ver §10).
- A5. El sistema produce borradores de interpretación (why now / bear case) que tú revisas; nada se publica sin tu edición.
- A6. Las inflexiones históricas de los pilotos (§7) son conocidas *antes* de mirar los datos (evita sesgo retrospectivo).

---

## 2. Inventario de fuentes verificadas

### Núcleo MVP

| Fuente | Acceso / auth | Costo | Límites clave | Licencia | Cobertura / latencia | Riesgos |
|---|---|---|---|---|---|---|
| **EPO OPS v3.2** | Registro gratis, OAuth2 client credentials (token ~20 min) | Gratis ≤ **4 GB/semana**; luego €2.800/año | Búsqueda CQL: **100/página, 2.000 resultados máx. por consulta**; throttling dinámico (`X-Throttling-Control`, semáforo); ~450 MB/h | Uso en productos derivados permitido; **no redistribuir crudo** | DOCDB: >100 países incl. IP5 + WO; semanal (mar/jue). Índices `cpc`, `pd`, `pa`, `famn`; familia simple (`/equivalents`) e INPADOC (`/family`) | Sin direcciones; país solo vía sufijo `[CC]`; hay que partir consultas (CPC × semana). Cobertura de resúmenes EN para CN/JP/KR en 2026 **[NV]**; traducción automática vía OPS **[NV]** (no documentada) |
| **OpenAlex** | API key gratuita (de facto obligatoria; sin key no pagina) | Gratis **US$1/día**; list/filter y `group_by` = US$0,10 por 1.000 llamadas; `search=` 10× más caro | 30 req/s con key; `group_by` ≤200 grupos/página; 1 dimensión por llamada; `per_page` 100 | **CC0** | ~Todo; API continua; snapshot S3 trimestral gratis (CC0). *Concepts* deprecados → usar **Topics** (4.516) + keywords. Instituciones con `geo` lat/long + ROR | Precios cambiaron 2 veces en 2026; huecos de afiliación; geo de empresas = sede; **no indexa patentes**; máx. valores OR por filtro **[NV]** |

### Complementos (fases posteriores)

| Fuente | Estado verificado | Uso propuesto |
|---|---|---|
| Google Patents en BigQuery (sandbox) | 1 TiB consultas/mes gratis; tabla no particionada (~900 GB en 2018); repo archivado abr-2026; **frescura 2025–26 [NV]** | Spike F0: `MAX(publication_date)`. Si fresca → backfill histórico barato; si no → descartar |
| EPO DOCDB bulk | Listado como **gratis** en la lista de precios; ~200 GB zip + frontfiles semanales | Ruta de escalado si OPS se queda corto (F3+) |
| PATSTAT | Fuentes EPO contradictorias (gratis vs compra) **[NV]** | No usar en MVP |
| USPTO ODP / PatentsView | ODP exige cuenta USPTO + ID.me desde jun-2026; **API PatentsView pausada desde 20-mar-2026**; bulk Q4-2025 disponible | Opcional F3: ubicaciones de inventores EE.UU. (lat/long **[NV]** en 2026) |
| Lens.org | API solo con suscripción institucional (términos jun-2026); trial 14 días no comercial | **Descartar** |
| WIPO PATENTSCOPE | Sin API gratuita (SOAP CHF 600–2.000/año) | **Descartar** (PCT ya está en DOCDB/OPS) |
| Semantic Scholar | Key gratis, 1 req/s; datasets ODC-BY; SPECTER2 por API | Opcional (embeddings); malo para hubs |
| arXiv | CC0 metadata, 1 req/3 s, casi sin afiliaciones | Irrelevante para agua/agro; útil luego para cuántica/IA |
| Reliance on Science v66 (sep-2026) | Citas patente→paper, **solo USPTO**, CC BY-NC | F2–F3: validar brecha ciencia→patente |
| ROR dump v2.14 / GeoNames | CC0 / CC BY | Probablemente innecesarios (OpenAlex ya trae geo) |
| CPC 2026.08 + concordancia CPC↔IPC | Descarga oficial | F0: validar códigos de los YAML |
| Capital/regulación (F4) | CORDIS (mensual, abierto), NWOpen-API (diario), RVO CSV (incompleto), SEC Form D (trimestral), ISO Open Data (ODC-By, diario), openFDA (CC0), Federal Register (riesgo bot-check) | Ver F4 |
| **No viable gratis** | Rondas VC globales, CVC/M&A estructurado, empleo agregado (Adzuna prohíbe agregar sin permiso), datos IEEE/ETSI | Declarar como hueco |

**Prioridad MVP: EPO OPS + OpenAlex → confirmada.** Justificación: son las únicas fuentes gratis, oficiales y vivas con (a) familias y CPC multi-oficina, y (b) instituciones geolocalizadas + autores estables + agregados baratos. Corrección: añadir un **spike de BigQuery** para el backfill histórico, porque la cuota semanal de OPS hace lento un backfill de 15 años en dominios voluminosos como C02F.

---

## 3. Arquitectura propuesta

```
radar-tecnologico/
├── CLAUDE.md
├── pyproject.toml / uv.lock
├── src/radar/
│   ├── core/          schema.py (contratos), quality.py (pandera), ids.py, config.py
│   ├── connectors/    openalex.py, epo_ops.py (+ bigquery_backfill.py si pasa el spike)
│   ├── resolve/       families.py, applicants.py (normalización), geo.py (país, hubs)
│   ├── domains/       loader.py (YAML→pydantic), membership.py
│   ├── metrics/       series.py, nowcast.py, metrics.py
│   ├── signals/       inflection.py, scoring.py, rules.py
│   ├── llm/           backend.py (interfaz), claude_code.py (`claude -p`), queue.py, cache
│   ├── reports/       memo.py, ficha.py, digest.py (+ templates Jinja2)
│   └── cli.py         Typer: `radar ingest|build|signals|report|run`
├── domains/           agua.yaml, agrobiotech.yaml, hubs.yaml, backtest_events.yaml
├── evals/             patents_agua.csv, papers_agua.csv, … (etiquetados a mano)
├── data/              (gitignored) raw/ staging/ core/ marts/ runs/
├── reports/           memos y fichas generadas (Markdown + HTML)
├── docs/decisions/    ADRs cortos de los spikes
├── .claude/skills/    clasificar-cola, redactar-memo (Claude Code)
└── tests/
```

| Decisión | Justificación |
|---|---|
| Python 3.12 + **uv**, **Polars**, **DuckDB + Parquet** | Rápido en un portátil, sin servidor, columnar; DuckDB consulta Parquet directo |
| Capas `raw → staging → core → marts` | `raw` = respuestas tal cual (gz) + manifiesto (URL, fecha, hash) = trazabilidad y re-procesamiento sin re-descargar; `core` = entidades resueltas; `marts` = métricas y señales |
| Snapshots/vintages mensuales de `marts` | Necesarios para medir error del nowcasting y estabilidad de señales |
| Tabla `runs` + `errors` | "Nunca inventar datos": cada fallo queda registrado; un hueco se ve como hueco |
| httpx + tenacity; lxml para XML de OPS | Reintentos con backoff respetando el semáforo de OPS |
| pydantic (configs/YAML) + **pandera** (dataframes) + pytest + ruff | Validación en las fronteras de capas |
| `ruptures`, `scipy`, `statsmodels` | Change-point, ajuste logístico, Theil–Sen |
| sentence-transformers multilingüe local + HDBSCAN (F2b/F3) | Embeddings gratis en CPU; sin API |
| **LLM vía `claude -p`** detrás de una interfaz `LLMBackend` | Cumple tu decisión (Max); cambiar a API = otro backend, sin tocar el pipeline |
| Programador de tareas de Windows | `uv run radar run --weekly` (domingo) y `--monthly` (día 5); mismo usuario de Windows (credenciales en `%USERPROFILE%\.claude`) |
| Salidas: Markdown → HTML estático (Jinja2 + Plotly) | Sin servidor; evoluciona directo a la estética "Liquid Glass". Streamlit solo como explorador local opcional en F4 |

**Detalles de `claude -p` verificados:** autentica con el login Max **siempre que no exista `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`** en el entorno (si existe, factura por API). Usar `--safe-mode` (no `--bare`, que desactiva el login de suscripción), `--output-format json --json-schema <schema>` (salida en `structured_output`), `--model haiku`, `--tools ""` (ADR F0-d: `--disallowedTools "*"` bloquea StructuredOutput), `--no-session-persistence`, `encoding="utf-8"`. Lotes de 10–20 registros por llamada, validación pydantic + reintento. Verificar con `claude auth status` → `authMethod: claude.ai`.

---

## 4. Contrato de datos (`core/schema.py`, pseudocódigo)

```python
# ---------- CAPA DATO (entidades tipadas) ----------
class PatentDoc:            # staging: 1 fila por publicación
    doc_id: str             # "EP.3456789.A1" (docdb)
    family_id: str          # DOCDB simple family (atributo family-id)
    office: Literal["US","EP","CN","JP","KR","WO",...]
    kind: str               # A1, B1, U (modelo de utilidad), ...
    is_utility_model: bool
    pub_date: date; appl_date: date | None; earliest_priority_date: date
    cpc: list[str]; ipc: list[str]
    applicants_raw: list[str]; applicant_countries: list[str]  # de sufijo [CC]
    title_en: str | None; abstract_en: str | None; abstract_orig_lang: str | None
    source: str; url: str; extracted_at: datetime; run_id: str; raw_ref: str

class Family:               # core: 1 fila por familia (unidad de conteo)
    family_id: str; earliest_priority_date: date; first_pub_date: date
    offices: set[str]; n_ip5_offices: int; has_pct: bool
    is_international: bool  # n_ip5_offices>=2 or has_pct
    only_utility_models: bool
    cpc_union: list[str]
    applicant_ids: list[str]           # normalizados
    applicant_country_weights: dict[str, float]  # conteo fraccional, suma 1
    text_en: str | None; text_source: Literal["original_en","docdb_en","llm_translation", None]

class Applicant:            # core: diccionario de normalización
    applicant_id: str; canonical_name: str; aliases: list[str]
    country: str | None; type: Literal["company","university","individual","gov","unknown"]
    hub: str | None         # curado (top-N), con hub_method
    first_seen_by_frente: dict[str, date]

class Work:                 # OpenAlex
    work_id: str; doi: str | None; pub_date: date; type: str
    primary_topic_id: str; topic_ids: list[str]; keywords: list[str]
    institution_ids: list[str]; author_ids: list[str]; countries: list[str]
    abstract: str | None    # reconstruido del inverted index
    cited_by_count: int; fwci: float | None
    source="openalex"; url: str; extracted_at: datetime; run_id: str

class Institution:          # OpenAlex + asignación de hub
    institution_id: str; ror: str | None; type: str
    country: str; lat: float | None; lon: float | None
    hub: str | None; hub_method: Literal["radius","country","manual"]

class Membership:           # core: entidad ∈ frente
    entity_id: str; entity_type: Literal["family","work"]
    domain: str; frente: str
    rule: Literal["cpc","topic","keyword","cpc+keyword","llm"]
    llm_label_id: str | None; confidence: float

# ---------- CAPA SEÑAL (formato largo, solo métricas) ----------
class Observation:
    observation_id: str          # hash determinista de la clave
    period_start: date; period_end: date; granularity: Literal["Q","Y","M"]
    layer: Literal["science","patent","capital","market"]
    domain: str; frente: str | None
    geo_type: Literal["global","bloc","country","hub"]; geo: str
    lens: Literal["all","international"]
    variable: str                # "families","share","velocity","hhi","new_entrants",...
    value: float; ci_low: float | None; ci_high: float | None
    n_basis: int                 # tamaño muestral detrás del valor
    provisional: bool; completeness: float | None   # nowcast
    source: str; method_version: str; run_id: str; computed_at: datetime

# ---------- CAPA INTERPRETACIÓN ----------
class Signal:
    signal_id: str; run_id: str; domain: str; frente: str; geo: str
    type: Literal["inflection_up","inflection_down","leadership_shift",
                  "entrant_wave","science_ahead","convergence","concentration"]
    direction: Literal["up","down"]; magnitude: float; score: float
    confidence: Literal["alta","media","baja"]; confidence_reasons: list[str]
    action: Literal["investigar","vigilar","descartar"]
    why_now: str | None; bear_case: str | None   # borrador LLM → editado por humano
    interpretation_status: Literal["auto","draft","reviewed"]
    first_seen_run: str; persistence: int        # nº corridas consecutivas

class Evidence:             # N:1 con Signal — toda señal tiene ≥1
    signal_id: str; kind: Literal["observation","family","work","url"]
    ref: str; url: str; extracted_at: datetime; note: str

class RunLog:  run_id; started_at; source; query; status; n_records; bytes; cost_usd; error
```

---

## 5. Definición operativa de dominios

Los códigos CPC se validan contra el esquema CPC 2026.08 en F0. Los IDs de Topics de OpenAlex se resuelven en F0 vía `/topics?search=` (los nombres de abajo son candidatos **[NV]**).

```yaml
# domains/agua.yaml
domain: agua
name: Tecnologías del agua
thesis: >
  Regulación de contaminantes emergentes (PFAS), escasez hídrica y reutilización
  industrial (semiconductores, data centers) empujan tratamiento avanzado y
  fuentes no convencionales.
frentes:
  - id: pfas_remocion
    name: Remoción/destrucción de PFAS
    cpc_any: ["C02F1/28", "C02F1/44", "C02F1/461", "C02F1/72", "B01J20", "A62D3"]
    keywords_all_any: [["PFAS", "perfluoro", "polyfluoro", "PFOA", "PFOS"]]
    openalex_topics: ["Per- and polyfluoroalkyl substances research"]
    rule: cpc+keyword          # CPC solo es demasiado amplio
  - id: desalinizacion_membranas
    name: Desalinización y membranas
    cpc_any: ["C02F1/441", "C02F1/442", "C02F1/444", "C02F1/445", "C02F1/469", "B01D61/02", "B01D61/025", "B01D61/027", "B01D61/14", "B01D61/36", "B01D69", "B01D71"]
    cpc_any_combined_with: ["C02F103/08"]   # agua de mar (opcional, sube precisión)
    openalex_topics: ["Membrane Separation Technologies", "Membrane-based Ion Separation Techniques"]
    rule: cpc
  - id: agua_atmosferica
    name: Captación de agua atmosférica
    cpc_any: ["E03B3/28", "B01D5/0039", "B01D53/26"]
    keywords_any: ["atmospheric water", "water harvesting", "metal-organic framework"]
    openalex_topics: ["Atmospheric water harvesting / sorbents"]   # [NV] resolver
    rule: cpc OR keyword
  - id: reutilizacion_avanzada
    name: Reutilización y oxidación avanzada
    cpc_any: ["C02F1/72", "C02F1/78", "C02F1/32", "C02F2101/30", "C02F2103/34"]
    openalex_topics: ["Advanced oxidation water treatment"]
    rule: cpc
  - id: redes_inteligentes
    name: Monitoreo y redes inteligentes de agua
    cpc_any: ["E03B7/07", "E03B7/071", "G01M3/28", "G01N33/18"]
    keywords_any: ["leak detection", "water network", "smart water"]
    rule: cpc
exclude:
  cpc_only_if_alone: ["C02F2201", "C02F2209"]   # tags auxiliares
  keywords_any: ["ballast water"]                # ejemplo de ruido conocido
lenses: [all, international]
min_families_per_period: 30
version: 0.1
```

```yaml
# domains/agrobiotech.yaml
domain: agrobiotech
name: Agrobiotech y bioinsumos   # reemplaza "agricultura regenerativa"
thesis: >
  Edición génica sin transgénesis (marcos regulatorios NGT), presión sobre
  agroquímicos y fertilizantes nitrogenados, y caída de costos de secuenciación
  habilitan biológicos y cultivos editados.
frentes:
  - id: edicion_genica_vegetal
    name: Edición génica en plantas
    cpc_any: ["C12N15/82", "C12N15/8201", "C12N15/8213", "A01H1/00", "A01H1/06", "A01H6"]
    keywords_any: ["CRISPR", "Cas9", "Cas12", "base editing", "prime editing", "genome editing"]
    rule: cpc+keyword
    openalex_topics: ["CRISPR and Genetic Engineering", "Plant genetic and mutation studies"]
  - id: biopesticidas
    name: Biocontrol y biopesticidas
    cpc_any: ["A01N63", "A01P"]
    rule: cpc
    openalex_topics: ["Biological control of plant pathogens", "Insect-pest control with Bt / entomopathogens"]
  - id: bioestimulantes_fijacion_n
    name: Bioestimulantes y fijación biológica de N
    cpc_any: ["C05F11/08", "C05G3/60", "C12N1/20", "C12R2001"]
    keywords_any: ["biostimulant", "nitrogen-fixing", "plant growth-promoting", "PGPR", "rhizobacteria"]
    rule: cpc+keyword
  - id: rnai_spray
    name: RNAi tópico (dsRNA)
    cpc_any: ["C12N15/113", "A01N57/16"]
    keywords_all_any: [["dsRNA", "RNAi", "double-stranded RNA"], ["plant", "crop", "pest", "spray"]]
    rule: cpc+keyword
  - id: agricultura_precision
    name: Agricultura de precisión y suelo   # puente con lo "regenerativo"
    cpc_any: ["A01B79/005", "A01C21/007", "A01G25/16", "G01N33/24", "G06Q50/02"]
    rule: cpc
lenses: [all, international]
version: 0.1
```

**Ajustes propuestos al resto (F3):** "IA y semiconductores" → *hardware para IA* (G06N3/063, G06F15/78, H10B/H10D) separado de *manufactura de semiconductores* (H01L21, G03F7); "Materiales avanzados" → *materiales descubiertos con IA* o frentes concretos (2D, metamateriales); "Salud digital" → *dispositivos médicos con IA* (G16H + lista FDA de dispositivos con IA); "Construcción sostenible" → *materiales de construcción bajos en carbono* (C04B bajo clínker, Y02W30/91, Y02B); "Sensores ambientales y OT" se mantiene, fusionando con el frente "redes inteligentes" de agua; "AI governance" → capa transversal de regulación/estándares (ISO JTC1/SC42, AI Act).

**Hubs** (`domains/hubs.yaml`): centro(s) + radio haversine — Bay Area (SF, San José; 50 km), Boston (Cambridge MA; 40), Shenzhen (40; HK como hub aparte), Tokio (60, incluye Tsukuba), Seúl (50), Múnich (40), **Eindhoven (25)**, Cambridge–Oxford (2 × 25), Tel Aviv (35, incluye Rehovot), Singapur (país), Zúrich (30). Instituciones `type=company` revisadas a mano (sesgo de sede). Para patentes: tabla curada de los ~200 solicitantes top por dominio → hub (Brainport: Philips, Signify, ASML, NXP, TU/e, TNO/Holst), con `hub_method="manual"`.

---

## 6. Métodos de detección de señales y scoring

**Series base.** Por frente × geo × lente × trimestre:
- Patentes: familias por **fecha de prioridad más temprana** (conteo de invención) con nowcasting; serie de control por fecha de primera publicación (sin rezago, mezcla cosechas).
- Ciencia: works por fecha de publicación (`group_by=publication_year` y por trimestre vía filtros de fecha).
- Denominador para normalizar: total de familias/works del año. Ciencia: `group_by` sobre todo OpenAlex (barato). Patentes: estadística anual de WIPO IP Statistics **[NV, spike F0]**; fallback = unión de todos los dominios rastreados + clase CPC padre.

**Nowcasting del rezago (~18 meses).** Para cada oficina o, se estima la curva de completitud c_o(k) = fracción de familias con prioridad en el trimestre q que ya están publicadas k meses después del fin de q. Se estima con cohortes de hace 4–6 años, que se asumen completas. Luego:
- n̂_q = n_obs,q / c(k_q), con IC binomial;
- `provisional = c(k) < 0.9`;
- los trimestres con c(k) < 0.5 no se usan para disparar señales; solo se muestran.

El método se valida comparando el nowcast de cada vintage con el valor observado 12 meses después (MAPE).

**Métricas** (*s* = participación, *g* = crecimiento):

| Métrica | Fórmula | Umbral inicial |
|---|---|---|
| Volumen | V = Σ familias (lente) | mínimo n ≥ 30 por periodo para señales |
| Velocidad | g = pendiente Theil–Sen de log(n̂) últimos 5 años completos → %/año; **g_rel = g_frente − g_base** | g_rel > +10 pp = rápido |
| Aceleración | a = g(últimos 3 a) − g(3 a previos); en trimestres: Δ de pendiente PELT | a > +10 pp |
| Globalidad | G = % familias internacionales (≥2 oficinas IP5 o PCT); + nº oficinas IP5 con ≥10 familias | G sube ≥ 5 pp en 3 a |
| Concentración geo | HHI = Σ s_c² (conteo fraccional por país del solicitante; lente internacional) | <0,15 diverso · 0,15–0,25 moderado · >0,25 concentrado |
| Cambio de liderazgo | Δs del bloque líder vs 2º en 3 a; evento *flip* si el ranking cambia y persiste ≥2 periodos | flip o Δs ≥ 10 pp |
| Nuevos entrantes | E_t = solicitantes con ≥1 familia en t y 0 en el frente en [t−3, t−1]; e = familias de entrantes / total | e > percentil 80 histórico del frente |
| Brecha ciencia→patente | GAP = g_ciencia − g_patente (normalizados); lag = argmax correlación cruzada de Δlog (0–6 a); validar con Reliance on Science (EE.UU.) | GAP > +15 pp = "ciencia adelantada" (ventana temprana); GAP < −15 pp y ciencia plana = incremental/hype |
| Madurez | Reglas (abajo) | — |
| Convergencia | C_AB = \|F_A ∩ F_B\| / min(\|F_A\|,\|F_B\|) por co-clasificación CPC; índice del frente = % de familias que caen en otro dominio; señal si C crece ≥ 2× en 3 a | — |
| Densidad de talento | autores con ≥2 works en el frente en 3 a (`group_by=authorships.author.id`) por hub; movilidad academia→empresa = autores con afiliación universitaria previa y luego `type=company` | crecimiento ≥ percentil 80 |
| Confianza | ver abajo | — |

**Madurez (reglas, por frente):**
- **emergente:** V bajo (< percentil 25 entre frentes) y g_rel > 0, ciencia ≥ patentes, e alto.
- **acelerando:** a > umbral y g_rel > 0.
- **escalando:** g_rel > 0, a ≤ 0, G sube y e baja.
- **madura:** |g_rel| ≤ 5 pp.
- **declinando:** g_rel < −5 pp durante 2 periodos.

**Métodos de inflexión: cuándo usar cada uno**

| Método | Uso | Cuándo |
|---|---|---|
| z-score robusto: z = (x_t − mediana)/(1,4826·MAD) sobre el crecimiento de la participación | Anomalía reciente vs historia del propio frente | Siempre; disparador principal (z ≥ 2) |
| EWMA (λ = 0,3; L = 2,7) | Control de series mensuales rápidas (OpenAlex) | Digest semanal |
| Change-point PELT (`ruptures`, penalización BIC) sobre log(n̂) trimestral | Cambio estructural de pendiente | Solo con ≥24 trimestres y n ≥ 30/trimestre |
| Curva logística / S (scipy) sobre acumulado | Ubicar etapa (antes/después de t0), **nunca como disparador**: antes de la inflexión t0 es inestable | ≥10 años de historia y ajuste con IC estrecho |

**Regla de señal (determinista, versionada):**

```
inflexión_up ⇐ (z ≥ 2  ∨  PELT detecta ↑ pendiente) ∧ g_rel > 0 ∧ n ≥ 30 ∧ no_provisional_en_disparo
score = 0.30·norm(a) + 0.20·norm(g_rel) + 0.15·norm(e) + 0.15·norm(ΔG) + 0.10·acuerdo_capas + 0.10·norm(GAP)
Penalizaciones: top-1 solicitante aporta > 40 % del crecimiento (−0.3); solo modelos de utilidad (descartar);
                solo una capa (máx. "vigilar")
Acción:  investigar ⇐ score ≥ 0.6 ∧ confianza ≥ media ∧ ≥2 capas coinciden
         vigilar    ⇐ score ≥ 0.4  ∨  1 capa  ∨  provisional
         descartar  ⇐ concentrada en un actor ∨ solo U ∨ n insuficiente
Confianza: alta = n ≥ 100, completitud ≥ 0.9, 2+ capas, persistencia ≥ 2 corridas, sin errores de fuente;
           media = cumple 3 de 5; baja = resto. Se listan los motivos.
```

Los pesos y umbrales son iniciales. Se calibran en el backtest (§7) y quedan congelados por versión (`method_version`).

**Clustering temático (F2b).** Se hacen embeddings locales multilingües de título + resumen (EN) por dominio, se agrupa con HDBSCAN cada trimestre y se siguen el crecimiento y la novedad de cada cluster (% de miembros sin CPC del frente). Claude nombra los clusters. Un cluster que crece y no está cubierto por CPC se marca como **candidato a nuevo frente**, nunca como señal directa.

**Separación de capas.** El dato vive en `staging`/`core`. La señal (métricas y reglas) es 100 % determinista y reproducible desde `raw`. La interpretación (why now, bear case) son borradores LLM con `interpretation_status`; el memo solo publica lo que está `reviewed`, o lo marca explícitamente como borrador.

---

## 7. Estrategia de evaluación

| Set | Tamaño | Muestreo | Etiqueta | Métrica / meta |
|---|---|---|---|---|
| Patentes por dominio | ≥ 60 (agua) + ≥ 60 (agro) | estratificado: 40 % núcleo (CPC+kw), 20 % solo-keyword, 20 % CPC adyacente, 20 % aleatorio del CPC padre | ¿pertenece? ¿a qué frente? | Precisión de la definición ≥ 0,85; recall estimado (sobre adyacentes) ≥ 0,70 |
| Publicaciones por dominio | ≥ 60 + ≥ 60 | ídem con topics/keywords | ídem | ídem |
| Clasificación LLM (casos frontera) | los mismos sets | — | humano vs Claude | Precisión ≥ 0,85 y κ de Cohen ≥ 0,7; si no, el LLM no decide (solo sugiere) |
| Traducción CN/JP/KR | 20 | aleatorio de residuales | adecuación 1–5 | media ≥ 4 |
| Normalización de solicitantes | top-200 por dominio | — | fusión correcta | precisión ≥ 0,95 (un falso merge crea "líderes" ficticios) |
| Nowcast | todas las vintages | — | — | MAPE a 12 meses ≤ 15 % |

Etiquetado: lo haces tú (≈ 2–3 h por set) en un CSV con columnas fijas. Claude puede proponer una etiqueta, pero la que vale es la humana.

**Criterio de "señal útil"**
1. **Backtest pre-registrado.** Antes de mirar datos, `backtest_events.yaml` lista eventos con año aproximado y fuente. Candidatos, que validas tú:
   - PFAS: regulación EPA / UE y auge del tratamiento, ~2019–2024;
   - edición CRISPR en cultivos, ~2015–2019;
   - captación atmosférica con MOFs, ~2017–2021;
   - bioestimulantes (reglamento UE de fertilizantes 2019/1009);
   - RNAi en spray, ~2020+.

   Meta: detectar ≥ 60 % de los eventos con un adelanto de ≥ 12 meses frente a la fecha "mainstream" de referencia, ejecutando el sistema como si fuera la fecha t (vintages simulados con datos publicados hasta t).
2. **Placebo.** Sobre frentes aleatorios (CPC al azar) o series barajadas, la tasa de "investigar" debe ser ≤ 10 %.
3. **Estabilidad.** El flip-rate de una acción entre corridas consecutivas debe ser < 20 %.
4. **Prospectivo.** Calificas cada señal del memo como útil o no útil. Meta tras 3 memos: ≥ 50 % útiles entre las "investigar" y ≤ 1 "investigar" absurda por memo.

---

## 8. Plan por fases

Dedicación confirmada: 4–5 h/semana. Las duraciones de abajo se calcularon con 8–10 h/semana; a tu ritmo, cuenta aproximadamente el doble (ver §9).

**F0 — Diseño y spikes (1–2 semanas)**
- Entregables:
  - repo con `uv`, ruff, pytest, estructura §3;
  - `CLAUDE.md`;
  - `schema.py`, `agua.yaml`, `agrobiotech.yaml`, `hubs.yaml` y `backtest_events.yaml`, validados con pydantic;
  - credenciales OPS y OpenAlex en `.env` (gitignored).
- Spikes, cada uno con su ADR en `docs/decisions/`:
  - (a) volumen OPS por frente y mes (conteos) y cuota necesaria para el backfill 2010→;
  - (b) frescura de BigQuery (`MAX(publication_date)`);
  - (c) resolver los IDs de Topics de OpenAlex y el límite de valores OR por filtro;
  - (d) `claude -p --safe-mode --json-schema` en Windows con un lote de prueba;
  - (e) cobertura de resúmenes EN para CN/JP/KR en una muestra de 200 documentos OPS;
  - (f) fuente del denominador de patentes.
- Éxito: todos los spikes respondidos con números, y los YAML validados contra CPC 2026.08.

**F1 — Ingesta de los 2 pilotos (3–4 semanas)**
- Entregables:
  - conector OpenAlex: agregados con `group_by` y registros completos con `select`, incremental por `from_updated_date`, registrando `meta.cost_usd` con freno a US$0,80/día;
  - conector OPS: búsqueda biblio con división automática de consultas (CPC × semana hasta < 2.000), cliente que respeta el semáforo y la cuota semanal (freno en 3,5 GB), caché raw;
  - backfill por OPS o BigQuery, según el spike;
  - staging → core: dedup por familia, lentes, normalización de solicitantes v1 (reglas + revisión del top-200), país fraccional, hubs de instituciones;
  - `membership`;
  - pandera en cada frontera; tabla `runs`/`errors`;
  - sets de evaluación etiquetados.
- Éxito:
  - `radar run --monthly` reproducible de punta a punta;
  - precisión de las definiciones ≥ 0,85;
  - cero fallos silenciosos (test que inyecta un error de fuente y verifica que se registra);
  - re-procesar desde `raw` da resultados idénticos.

**F2 — Métricas, señales y memo (3–4 semanas)**
- Entregables:
  - `series` + `nowcast` + `metrics` → `observations`;
  - `inflection` + `scoring` + `rules` → `signals` + `evidence`;
  - skill de Claude Code `redactar-memo`, que llena why now / bear case como borrador;
  - **memo mensual** (top 5: why now, evidencia con URLs, bear case, confianza, acción);
  - **ficha de dominio viva**;
  - **digest semanal** (OpenAlex: works nuevos por frente, alertas EWMA, top works nuevos);
  - backtest + placebo;
  - opcional: frente de control "baterías de ion-sodio" (H01M10/054), solo para calibrar umbrales con una inflexión conocida y de alto volumen.
  - ~~F2b: clustering temático~~ → movido a F3 por la dedicación de 4–5 h/semana.
- Éxito:
  - metas de backtest y placebo de §7;
  - el memo se produce con ≤ 30 min de tu tiempo;
  - el 100 % de las señales tiene evidencia trazable.

**F3 — Escalar (6–8 semanas, en tandas de 2 dominios)**
- Entregables:
  - dominios restantes redefinidos (§5), cada uno con su YAML y sus sets de evaluación;
  - convergencia entre dominios;
  - hubs de patentes vía tabla curada; opcional, ubicaciones de inventores de PatentsView bulk (EE.UU.);
  - Reliance on Science para la brecha ciencia→patente;
  - evaluar DOCDB bulk si OPS no da abasto.
- Éxito: cada dominio pasa el gate de evaluación antes de entrar al memo, y el tiempo de corrida mensual es menor de 2 h.

**F4 — Visualización + capital/regulación (4–6 semanas)**
- Entregables:
  - HTML estático (Plotly + estética Liquid Glass): mapa mundial de hubs (volumen × aceleración), carrera de liderazgo, matriz de madurez, pipeline ciencia→patente→capital;
  - capa de capital: CORDIS, NWOpen, RVO (foco Eindhoven) y SEC Form D;
  - capa de mercado: ISO Open Data (comités relevantes) y regulación de los pilotos (PFAS: EPA/UE; NGT: UE; bioestimulantes: Reglamento 2019/1009);
  - capa regulatoria siempre curada a mano + Federal Register cuando funcione.
- Éxito: las 6 salidas del brief existen, y la capa de capital está marcada como parcial (sin VC global).

---

## 9. Costos y tiempo

| Rubro | Estimación |
|---|---|
| EPO OPS | US$0 (≤ 4 GB/semana; backfill repartido en semanas si hace falta) |
| OpenAlex | US$0 (agregados: ~1.100 llamadas ≈ US$0,11 por corrida; registros: ~US$0,10 por 100k works; tope US$1/día) |
| BigQuery sandbox | US$0 (1 TiB/mes; consultas con dry-run, solo columnas biblio) |
| Claude | US$0 marginal con Max (`claude -p`). Volumen esperado: < 2.000 registros frontera/traducciones al mes + 1 memo + 4 digests. Referencia si algún día pasas a la API: Haiku 5.5 Batch (US$0,05/0,25 por MTok) ≈ US$1–2/mes para 10k resúmenes; memo con Opus 5.5 ≈ US$0,30 |
| Almacenamiento | Local, < 10 GB en Parquet para 2 dominios × 15 años (sin DOCDB bulk) |
| Tiempo (4–5 h/sem, confirmado) | F0 2–3 sem · F1 6–8 · F2 6–8 · **MVP útil en ~16–20 semanas** · F3 +12–16 (incluye clustering) · F4 +8–12 |
| Operación | ~1 h/mes (revisar el memo, etiquetar lo dudoso) + ~15 min/semana (digest) |

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Cuota OPS de 4 GB/semana y tope de 2.000 resultados por consulta | División automática de consultas; freno en 3,5 GB; backfill por BigQuery si es fresca; DOCDB bulk como ruta de escalado |
| Definiciones de agua/agro con poca precisión | Frentes con regla `cpc+keyword`; sets de evaluación; gate ≥ 0,85 antes de emitir señales |
| Inflación por CN y modelos de utilidad | Lente internacional para liderazgo y calidad; flag `only_utility_models` |
| Falsos "líderes" por mala normalización de solicitantes | Revisión manual del top-200; preferir no fusionar ante la duda |
| Sesgo de sede en hubs | Lente país para patentes; revisión de las instituciones `company`; documentado en cada ficha |
| Cambios de precio/acceso (OpenAlex cambió 2× en 2026; Lens y PatentsView se cerraron) | Conectores aislados; `cost_usd` registrado; revisión trimestral de términos; `raw` local para no depender de re-descargas |
| Política de uso de Max ("uso individual ordinario"; Anthropic puede limitar sin aviso) | Uso de LLM mínimo por diseño (reglas primero), caché por hash, lotes pequeños, sin Agent SDK; interfaz lista para cambiar a la API (~US$2/mes) |
| `ANTHROPIC_API_KEY` presente → facturación inesperada | El pipeline elimina esas variables del entorno del subproceso y verifica `claude auth status` antes de cada lote |
| Sobreajuste del backtest (umbrales tuneados a eventos conocidos) | Eventos pre-registrados; placebo; umbrales congelados por versión; evaluación prospectiva |
| "Why now" alucinado | Borrador obligatorio con citas a `evidence`; estado `draft` hasta tu revisión; regla en CLAUDE.md |
| Abandono por complejidad | MVP de 2 dominios; gate antes de escalar; operación ≤ 1 h/mes |
| Federal Register bloquea bots; Adzuna prohíbe agregar | Regulación curada a mano; empleo fuera de alcance |

---

## 11. Propuesta de `CLAUDE.md`

```markdown
# Radar Tecnológico — reglas del proyecto
## Propósito
Detectar frentes tecnológicos que cruzan un punto de inflexión, con evidencia trazable. No medir "cuánta tecnología hay".
## Reglas de datos (no negociables)
- Nunca inventar, imputar ni "rellenar" datos. Si una fuente falla: registrar en `runs/errors` y dejar el hueco visible.
- Unidad de conteo de patentes = familia DOCDB. Nunca contar documentos.
- Toda observación lleva source, url, extracted_at, run_id, method_version y provisional.
- Toda señal tiene ≥1 fila en `evidence`. Sin evidencia, no hay señal.
- Capas separadas: dato (staging/core) · señal (marts, determinista) · interpretación (borradores revisados por humano).
- Periodos con completitud < 0.9 se marcan provisional; < 0.5 no disparan señales.
- Reportar siempre las dos lentes (all / international) cuando haya patentes CN.
## Reglas de código
- Python 3.12, uv, Polars (no pandas en código nuevo), DuckDB, Parquet. ruff + pytest. Validación pandera en cada frontera de capa.
- Conectores idempotentes, con caché raw, reintentos con backoff y respeto de cuotas (OPS: semáforo + freno 3,5 GB/semana; OpenAlex: freno US$0,80/día).
- Cambios en definiciones de dominio o en umbrales ⇒ subir `version`/`method_version` y re-ejecutar evals.
- No commitear `data/`, `.env` ni datos crudos de OPS (licencia: no redistribuir).
## Reglas para LLM
- Usar LLM solo para: casos frontera de clasificación, traducción residual, nombres de clusters, borradores de memo.
- Siempre salida JSON validada con esquema; cachear por hash(entrada + versión de prompt).
- Al redactar why_now/bear_case: citar evidence_ids; si no hay evidencia, escribir "sin evidencia suficiente".
- Nunca presentar un borrador como conclusión revisada.
## Idioma
Código e identificadores en inglés; reportes y fichas en español.
```

---

## 12. Preguntas abiertas (priorizadas, máximo 7)

1. **Dedicación real (h/semana)** y si hay una fecha objetivo para el primer memo. Esto ajusta el cronograma.
2. **Ventana histórica:** ¿2010→hoy, o basta 2014→hoy? Si el spike de BigQuery falla, esto define cuántas semanas de cuota OPS consume el backfill.
3. **Eventos de backtest:** ¿validas, quitas o añades eventos de la lista de §7? Tienen que quedar cerrados antes de ver los datos.
4. **Hubs de patentes:** ¿aceptas la lente país en el MVP, con hubs solo en ciencia más una tabla curada de top-solicitantes?
5. **Interpretación:** ¿quieres que el why now y el bear case salgan siempre como borrador para editar (recomendado), o aceptas publicación automática marcada como "no revisada"?
6. **Frente de control** (ion-sodio, fuera de tus pilotos): ¿lo incluimos solo para calibrar umbrales?
7. **Repositorio:** ¿GitHub privado solo para el código (los datos quedan locales)? ¿Algún nombre o organización en particular?

---

## Verificación (cómo se prueba el sistema construido)

- `uv run pytest`: tests unitarios de nowcast (series sintéticas con rezago conocido), métricas (HHI, Theil–Sen y entrantes con fixtures), reglas de señal (casos de borde) y validación pandera.
- Test de fallo de fuente: un mock de OPS que devuelve 403 o black-throttle debe dejar una fila en `errors` y ningún hueco relleno.
- Reproducibilidad: borrar `staging`/`core`/`marts`, re-procesar desde `raw` y comparar con hash de los marts.
- `uv run radar run --monthly --domains agua,agrobiotech` de punta a punta, revisando a mano 5 señales con sus URLs de evidencia.
- `uv run radar eval`: precisión y recall de las definiciones y κ del LLM contra los sets etiquetados.
- `uv run radar backtest`: tabla de eventos detectados con su adelanto, más el placebo.
- `claude auth status` → `authMethod: claude.ai` antes del primer lote LLM.
