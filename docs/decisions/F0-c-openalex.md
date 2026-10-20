# ADR F0-c — Topics de OpenAlex por frente, límites de la API y costos

- **Fecha:** 2026-10-19
- **Estado:** aceptada
- **Script:** `spikes/f0c_openalex.py` (`discover`, `limits`, `series`) · resultados en `data/spikes/f0c/`
- **Código derivado:** bloque `science` en `domains/*.yaml` (`ScienceDef` en `src/radar/domains/loader.py`)
  y `src/radar/connectors/openalex.py` (`works_filter`).

## Preguntas
1. ¿Qué topics de OpenAlex corresponden a cada frente?
2. ¿Cuántos valores OR acepta un filtro?
3. ¿Qué cuesta y cómo se comporta el límite de uso con una API key gratuita?

## Hallazgos

### 1. Los topics son demasiado gruesos para la mayoría de los frentes
OpenAlex tiene 4.516 topics. Solo **2 de 11 frentes** quedan bien con topic solo, y eso tras revisar
una muestra de 8 títulos por frente:

| Situación | Frentes |
|---|---|
| Sin topic propio: hace falta búsqueda por keywords | `agua_atmosferica`, `rnai_spray` |
| Topic más amplio que el frente (topic + keywords) | `pfas_remocion` (incluye toxicología), `desalinizacion_membranas` (alimentos, bioprocesos), `reutilizacion_avanzada` (saneamiento rural), `redes_inteligentes` (hidroeléctricas, acuicultura), `edicion_genica_vegetal` (edición humana), `biopesticidas` (taxonomía de hongos), `bioestimulantes_fijacion_n`, `agricultura_precision` (ganadería), `ion_sodio` |

**Decisión:** cada frente tiene un bloque `science` con regla propia: `topic`, `topic+keyword` o
`keyword`. Las keywords se buscan en `title_and_abstract.search`, con OR dentro de cada grupo y AND
entre grupos. Hoy todos los frentes usan `topic+keyword` o `keyword`.

Efecto en volumen: PFAS pasa de 24.338 a 6.700 trabajos y CRISPR de 49.702 a 4.969. En la muestra de
8 títulos quedan entre 6 y 8 relevantes por frente. **Es una revisión informal**: la precisión real
se mide en F1 con los sets etiquetados (meta ≥ 0,85).

Brecha conocida: no hay topic para el biocontrol de patógenos vegetales. `biopesticidas` hoy solo
cubre los entomopatógenos.

### 2. Límites de la API (medidos)
- **Máximo 100 valores OR por filtro.** Con 101 o más devuelve HTTP 400 ("Maximum number of values
  exceeded"). `ScienceDef` limita `topics` a 100.
- **429 en ráfaga para filtros grandes.** Tres llamadas seguidas con 100 valores OR: la 2.ª y la 3.ª
  reciben 429. Cinco llamadas seguidas con 2 valores no lo reciben. Con 3 s de espacio, todo responde 200.
  El conector debe espaciar las llamadas (≥ 1 s) y reintentar el 429 con backoff (5 s, 15 s, 45 s).
- **La sintaxis booleana funciona:** `title_and_abstract.search:(a OR "frase dos") AND (b OR c)`.
- **Ruido en los datos:**
  - aparecen trabajos de tipo revisión por pares ("decision letters");
  - hay fechas imposibles (2027, 2028, 2045).

  Decisión: filtrar siempre `type:article|review|preprint` y `to_publication_date:<hoy>`.

### 3. Costos y cabeceras
- Por llamada: lista o `group_by` US$0,0001; con `search` US$0,001; búsqueda de topics US$0,001.
- Las cabeceras traen el presupuesto: `x-ratelimit-remaining-usd`, `x-ratelimit-limit-usd`
  (US$1/día) y `x-ratelimit-reset` (segundos hasta medianoche UTC). El conector las registra en `runs`
  y frena en US$0,80.
- **El spike completo costó unos US$0,08 de US$1/día.** Una serie anual de los 11 frentes con muestra
  de títulos cuesta unos US$0,02 (22 llamadas).

### 4. Hace falta normalizar por el total de OpenAlex
El total de trabajos (artículos, revisiones y preprints) es estable en 6,1–7,0 M por año entre 2014 y
2024, pero **salta a 8,04 M en 2025 (+16%)** y ya va en 7,76 M en 2026 parcial (19 de octubre). Es un
efecto de cobertura, no de ciencia. Las series crudas sobreestiman el crecimiento reciente.
**Decisión:** las métricas científicas usan participación (frente / total del año), no conteos
crudos. El año en curso siempre es `provisional`.

Crecimiento de la participación 2020→2025 (tasa anual compuesta). Es descriptivo, **no es una señal**:

| Frente | Crudo 2019→2025 | Participación 2019→2025 | TCAC participación 2020–25 |
|---|---|---|---|
| agua_atmosferica | ×8,90 | ×7,28 | +35,8% |
| agricultura_precision | ×5,61 | ×4,59 | +30,9% |
| pfas_remocion | ×5,26 | ×4,30 | +26,8% |
| ion_sodio (control) | ×2,31 | ×1,89 | +13,7% |
| rnai_spray | ×2,10 | ×1,72 | +12,4% |
| bioestimulantes_fijacion_n | ×2,52 | ×2,07 | +11,4% |
| redes_inteligentes | ×2,08 | ×1,70 | +9,0% |
| reutilizacion_avanzada | ×2,05 | ×1,68 | +8,5% |
| edicion_genica_vegetal | ×1,55 | ×1,27 | +4,1% |
| desalinizacion_membranas | ×1,64 | ×1,34 | +4,1% |
| biopesticidas | ×1,73 | ×1,42 | +2,8% |

Los tres frentes de mayor crecimiento coinciden con dos eventos pre-registrados del backtest (PFAS y
agua atmosférica). Esto **no valida** el sistema: el backtest formal se hace en F2 con datos
publicados hasta cada fecha t, y la definición de los frentes se ajustó viendo estas series. Por
eso, cambios futuros a estos `science` deben justificarse con los sets etiquetados, no con las series.

## Pendiente
- Medir la precisión con los sets etiquetados en F1 (≥ 60 papers por dominio).
- Decidir si conviene una consulta extra para el biocontrol de patógenos vegetales.
- `group_by` por país, institución y autor (hubs y talento) en F1.
