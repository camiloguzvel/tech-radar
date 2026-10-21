# ADR F0-a — Volumen en EPO OPS, cuota y forma de la ingesta

- **Fecha:** 2026-10-20
- **Estado:** aceptada
- **Script:** `spikes/f0a_ops.py volume` · resultado en `data/spikes/f0a/volume-20261020-091141.json`
- **Código:** `src/radar/connectors/epo_ops.py` (`OpsClient`, `frente_cql`)

## Preguntas
1. ¿Cuántos documentos tiene cada frente y su campo padre, y cuánto pesa el backfill 2014→hoy?
2. ¿Cabe en la cuota gratuita (4 GB/semana; freno propio en 3,5 GB)?
3. ¿Qué hay que saber de OPS para construir el conector?

## Hallazgos de comportamiento de OPS (medidos)
- **Clasificación: hay que usar `cl` (CPC ∪ IPC).** Muchos documentos CN/JP solo tienen IPC.
  Con `cpc` se ve apenas el 21%–52% de los documentos CN en `C02F` (21% en 2015, 52% en 2018,
  32% en 2022) y el 34%–42% de los JP. Como la proporción **cambia de año a año**, contar solo con
  CPC crearía tendencias falsas.
  - Consecuencia: los códigos **exclusivos de CPC** (subgrupos con título entre llaves, índices de la
    serie 2000 como `C12N2310/20`, `C12R2001`, `A01B79/005`) no coinciden con documentos que solo
    tienen IPC. Esto baja el recall en CN y JP en los frentes que dependen de ellos
    (`agricultura_precision`, el `cpc_qualified` de CRISPR, `rnai_spray`). Se mide en F1.
- **Precedencia en CQL:** `and` y `or` tienen la misma prioridad (de izquierda a derecha). El
  constructor pone paréntesis explícitos y hay un test que lo cubre.
- **Formato:** JSON pesa **9,5 KB por documento** con biblio, frente a 21,7 KB en XML. Se usa JSON.
- **Cuota:** `X-RegisteredQuotaPerWeek-Used` da los bytes exactos usados en la semana. Contar
  (`Range: 1-1`) cuesta ~1 KB por consulta.
- **Límite de ritmo:** con OPS en "overloaded" se permiten 5 búsquedas por minuto (12 s cada una);
  en "busy", 15. El límite anunciado puede llegar a **0**: el cliente espera, con un tope de 120 s.
- **Errores:** `500 SERVER.DomainAccess` ("try again later") con consultas pesadas; se resolvió
  reintentando. Sin resultados, OPS responde `404`, que el cliente toma como 0.
- **Incidente:** la primera corrida se colgó 2 h sin dejar rastro: esperas sin tope y salida en
  búfer. Se corrigió con tope a cada espera, timeouts HTTP explícitos, registro por llamada
  (`verbose`) y captura de errores por frente, que deja el error registrado en vez de un número.

## Volumen medido (documentos publicados por mes, `cl`)

| Objetivo | 2015-06 | 2020-06 | 2025-06 | Backfill 2014→2026 (estim.) |
|---|---|---|---|---|
| edicion_genica_vegetal | 4 | 25 | 46 | 0,04 GB |
| biopesticidas | 313 | 469 | 530 | 0,62 GB |
| bioestimulantes_fijacion_n | 5 | 11 | 25 | 0,02 GB |
| rnai_spray | 6 | 3 | 20 | 0,01 GB |
| agricultura_precision | 114 | 338 | 302 | 0,36 GB |
| pfas_remocion | 0 | 2 | 20 | 0,01 GB |
| desalinizacion_membranas | 377 | 741 | 680 | 0,85 GB |
| agua_atmosferica | 18 | 57 | 45 | 0,06 GB |
| reutilizacion_avanzada | 318 | 726 | 655 | 0,80 GB |
| redes_inteligentes | 217 | 619 | 540 | 0,65 GB |
| ion_sodio (control) | 23 | 47 | 196 | 0,13 GB |
| **Subtotal frentes** | | | | **≈ 3,6 GB** |
| Padre agua (`C02F`) | 2.918 | 8.075 | 4.500 | 7,3 GB |
| Padre agrobiotech | 1.387 | 1.901 | 2.076 | 2,5 GB |
| Padre control (`H01M`) | 3.523 | 7.273 | **12.010** | 10,7 GB |

La estimación es el promedio de los 3 meses × 12 × 13 años × 9,5 KB. Es gruesa: un solo mes es
ruidoso (por ejemplo, `C02F` 2020-06 frente a 2025-06), porque las oficinas publican por lotes.

## Decisiones
1. **Frentes: descarga completa** (biblio en JSON) desde 2014. Son ~3,6 GB: **1–2 semanas de cuota**.
   Ningún frente supera 2.000 documentos al mes, así que las ventanas mensuales sirven. El conector
   igual divide automáticamente cualquier ventana con más de 2.000 resultados.
2. **Campos padre: solo conteos**, no descarga. Son 3 padres × ~154 meses ≈ 460 consultas de ~1 KB
   (≈ 0,5 MB, ~1,5 h al ritmo de OPS). Esto cierra la dependencia del ADR F0-f.
   - Unidad del denominador: **documentos publicados por mes** en el campo padre. Para comparar en
     la misma unidad, la velocidad relativa usa también los **documentos** del frente
     (`share_docs = docs_frente / docs_padre`). El resto de las métricas (entrantes, globalidad,
     HHI, liderazgo) se calcula sobre **familias** del frente.
   - Esta excepción a "nunca contar documentos" se limita a la normalización. En F2 se verifica
     que el crecimiento de `share_docs` y el de las familias del frente apunten en la misma dirección.
3. **Umbral de volumen:** `pfas_remocion`, `rnai_spray` y `bioestimulantes_fijacion_n` tienen ~20
   documentos al mes en 2025 y casi nada antes de 2020. Con `min_families_per_period: 30` solo
   alcanzan para señales **anuales** recientes, no trimestrales. Es esperable en frentes emergentes y
   se marca en la ficha de cada frente.
4. **BigQuery (F0-b): no hace falta.** El backfill de frentes cabe en 1–2 semanas de OPS y los
   padres se resuelven con conteos.

## Pendiente
- Medir en F1, con los sets etiquetados, la pérdida de recall en CN/JP por los códigos
  exclusivos de CPC y decidir si se agregan equivalentes IPC (con la concordancia CPC↔IPC oficial).
- Medir el tamaño real de las familias (documentos por familia) en el backfill.

## Addendum 2026-10-21 — cuota por hora y `Retry-After` en milisegundos

Durante la carga completa, OPS rechazó búsquedas con `403` y `Retry-After: 900000`. Era la
**cuota por hora** (`X-IndividualQuotaPerHour-Used` ≈ 392 MB de ~450 MB), y el valor está en
**milisegundos**: 900000 = 15 minutos, y bajaba ~61000 por cada minuto transcurrido. El cliente lo
leía como segundos (10 días), marcaba el trimestre como error y pasaba al siguiente (15 errores
seguidos). Después, un corte de conexión SSL (`UNEXPECTED_EOF_WHILE_READING`) tumbó el proceso,
porque los errores de red no se reintentaban. Ningún trimestre con error quedó marcado como
completo, así que se volvieron a bajar en la corrida siguiente.

Correcciones en `OpsClient` (con tests en `tests/test_epo_client.py`):
- `Retry-After` se interpreta en milisegundos; ante un 403 de cuota horaria se espera lo pedido,
  con un tope acumulado de 30 min y registro en el log. Un rechazo de cuota semanal frena la
  corrida (`QuotaExceeded`).
- Pausa preventiva de 5 min cuando el contador horario supera 380 MB.
- Los errores de red (`httpx.TransportError`) se reintentan con backoff.
