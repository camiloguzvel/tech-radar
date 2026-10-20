# ADR F0-f — Denominador para normalizar los conteos de patentes

- **Fecha:** 2026-10-19
- **Estado:** aceptada (la parte de "campo padre" depende del spike F0-a)
- **Método:** investigación en fuentes oficiales, con consultas en vivo a WIPO IPSDC y OECD SDMX.

## Pregunta
¿Contra qué total se normalizan las familias de cada frente, de modo que el crecimiento sea relativo
y no un reflejo del aumento general de patentes, en especial el de China?

## Fuentes oficiales gratuitas evaluadas

| Fuente | Unidad | Último año útil | Acceso | Licencia / términos | Uso |
|---|---|---|---|---|---|
| **WIPO IPSDC, indicador 6a** (familias por origen) | Familias por primera presentación (PATSTAT), primer solicitante | **2023** (2024 vacío) | Web; backend JSON/CSV interno sin documentar (`api.ipstatsdc...`); ZIP masivo de abr-2024 | Gratis; **no republicar** las series; citar "WIPO Statistics Database" | Lente "todas" por país |
| WIPO IPSDC, indicadores 7 y 8 (familias con presencia extranjera, por oficina destino) | Familias | 2022 | Igual | Igual | Complemento por oficina |
| WIPO IPSDC, indicador 1 (solicitudes por oficina) | Documentos, por año de presentación | 2024 | Igual | Igual | Contexto por oficina |
| **OECD `DF_PATENTS`, `9P50_3` (familias IP5)** | Familias por año de **prioridad**, conteo fraccional por país del solicitante, con total mundial | 2022 (**truncado**: 252.898 frente a 283.331 en 2021) | API SDMX REST pública, sin clave | CC BY 4.0 según la OECD (para datos **[NV]**) | Lente "internacional" por país |
| IP5 Statistics Report 2024 (XLSX) | Familias por prioridad, por bloque | 2020 | Una planilla por edición | **[NV]** | Solo verificación cruzada (su "familia IP5" exige las 5 oficinas) |
| EPO Technology Dashboard | Solicitudes EP (documentos) | 2025 | XLSX | **[NV]** | No sirve: solo oficina EP, sin familias |

## Problemas de fondo
1. **Rezago:** el último año completo y confiable es 2021 (OECD) o 2022–2023 (WIPO). El radar necesita
   2024–2026 con nowcast. Extender estas series sería inventar datos: **prohibido**.
2. **Definiciones distintas:** nuestro numerador son familias simples DOCDB vía OPS. WIPO y OECD usan
   familias construidas sobre PATSTAT con reglas propias. OECD además cuenta en fracciones y WIPO
   atribuye el país al primer solicitante. Solo se pueden comparar **cocientes e índices**, nunca
   niveles absolutos.
3. **Revisiones:** cada edición de PATSTAT cambia los valores pasados.
4. **Fragilidad:** el backend de WIPO no está documentado y puede cambiar sin aviso.

## Decisión: dos denominadores con roles distintos

### A. Velocidad y aceleración → "campo padre" de la misma fuente
`g_base` del plan (§6) se calcula con el **campo tecnológico padre de cada dominio**, medido en OPS con
la misma definición de familia, la misma fecha de prioridad y el mismo nowcast que el numerador:

| Dominio | Campo padre (propuesto) |
|---|---|
| agua | `C02F` (todo el tratamiento de agua) |
| agrobiotech | `A01N63` ∪ `A01N65` ∪ `A01H` ∪ `C12N15/82` ∪ `C05F` |
| control | `H01M` (baterías y celdas) |

La pregunta de inversión que responde es: ¿el frente crece más rápido que su propio campo?
(por ejemplo, PFAS frente a todo el tratamiento de agua). Tiene el mismo rezago y la misma
corrección que el numerador, y no mezcla fuentes. **Depende de F0-a**: el volumen de `C02F` y `H01M`
tiene que caber en la cuota de OPS (4 GB/semana). Si no cabe, se usa la suma de frentes del dominio
como base y se marca como base reducida.

### B. Geografía y liderazgo → series oficiales, solo en años completos
Para saber si un país está **especializado** en un frente se usa la ventaja tecnológica revelada:

```
RTA(país, frente, año) = (familias_país,frente / familias_frente) / (familias_país,total / familias_mundo,total)
```

- **Lente "todas":** el denominador es WIPO 6a. Para el total mundial se suman los orígenes, porque
  no se encontró un código de mundo **[NV]**.
- **Lente "internacional":** el denominador es OECD `9P50_3` (familias IP5, prioridad, solicitante),
  con total mundial `W`.
- **Solo años con dato oficial completo:** hasta 2021 en OECD y hasta 2022 en WIPO, con el último año
  como provisional. Para años posteriores **no se calcula RTA**: el memo muestra participaciones crudas
  dentro del frente, marcadas "sin normalizar por país".
- Cada descarga se guarda como **vintage** (fecha y edición) en `data/ref/` y no se republica (términos
  de WIPO).

## Consecuencias para el plan
- §6: "Denominador para normalizar" se reemplaza por esta decisión. Se elimina la idea de usar
  WIPO como denominador de crecimiento reciente.
- El conector OPS (F1) consulta también los campos padre. F0-a mide si cabe en la cuota.
- Conector F1 de referencia: OECD SDMX, que es estable y sin clave. WIPO IPSDC por CSV, con descarga
  manual de respaldo si el backend cambia.

## Pendiente / no verificado
- Licencia de datos de la OECD (oecd.org respondió 403).
- Código de total mundial en WIPO IPSDC.
- Definición exacta de familia en WIPO 6a y en OECD (¿simple o extendida?).
- Contenido del ZIP masivo de WIPO (Last-Modified abr-2024, posiblemente desactualizado).
