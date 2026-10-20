# ADR F0-g — Validación de los códigos CPC contra el esquema 2026.08

- **Fecha:** 2026-10-19
- **Estado:** aceptada
- **Fuente:** `CPCTitleList202608.zip` (4,46 MB, SHA-256 `CD3A6431…541F92`), descargado de
  cooperativepatentclassification.org (bulk 2026.08, modificado 2026-07-08). Se guarda en
  `data/ref/cpc-202608/` y no se versiona. Contiene 254.314 símbolos.
- **Script:** `spikes/f0g_cpc.py` · **Código:** `src/radar/domains/cpc.py` (`CpcScheme`, `FrenteCpcMatcher`)

## Pregunta
¿Existen los códigos CPC de los YAML y significan lo que pretendemos?

## Hallazgos

### 1. Existencia: todo válido
Las 52 referencias CPC de los YAML (incluidos los códigos de contexto y de exclusión) existen en
CPC 2026.08.

### 2. Significado: 7 códigos mal elegidos o demasiado amplios
Leer el título oficial cambió varias definiciones:

| Frente | Código | Título oficial (resumen) | Problema | Decisión |
|---|---|---|---|---|
| bioestimulantes | `C05G3/60` | Biocidas o conservantes en mezclas de fertilizantes | No son bioestimulantes | Quitado; se añaden `C05F11/10` (hormonas vegetales) y `A01N63` (reguladores de crecimiento con microorganismos), con keywords |
| biopesticidas | `A01P` | Actividad biocida de **compuestos químicos** | Incluye todos los pesticidas químicos | Quitado; se añade `A01N65` (algas y extractos vegetales) |
| rnai_spray | `A01N57/16` | Biocidas fosforados con radicales heterocíclicos | No es dsRNA | Reemplazado por `A01N63/60` (biocidas con ácidos nucleicos aislados) y `C12N2310/14` (ácidos nucleicos interferentes) |
| agua_atmosferica | `B01D53/26`, `B01D5/0039` | Secado de gases; recuperación de calor | Cualquier secado de gases o bomba de calor | Quitados; queda `E03B3/28` (agua desde aire húmedo) más keywords |
| reutilizacion_avanzada | `C02F2101/30`, `C02F2103/34` | Índices: contaminante orgánico; agua industrial | Cualquier tratamiento de esos efluentes | Quitados; queda oxidación `C02F1/72` (incluye ozono, peróxidos y catalítica) y UV `C02F1/32` |
| desalinizacion | `B01D69`, `B01D71`, `B01D61/*` | Membranas semipermeables en general | Incluye gases, alimentos y biofármacos | Solo cuentan con contexto de agua (`C02F`) |
| agricultura_precision | `G01N33/24`, `G06Q50/02` | Materiales terrestres; TI de agricultura **y minería** | Incluye minería y geología | Solo cuentan con contexto agrícola (`A01B`, `A01C`, `A01G`) |
| redes_inteligentes | `G01M3/28` | Fugas en tuberías, **cables**, válvulas | Incluye gas y cables | Solo con contexto `E03B` o `E03F`; la keyword "leak detection" pasa a "water leak" |

Códigos añadidos tras buscar en la lista oficial: `C12N9/222` (enzimas Cas) y `C12N2310/20`
(índice CRISPR), solo en contexto vegetal; `C02F1/722` y `C02F1/725` ya quedan cubiertos por
`C02F1/72`.

No existe un código CPC específico de bioestimulantes, fijación biológica de N ni reutilización
de agua. En esos frentes el trabajo lo hacen las keywords.

### 3. La jerarquía CPC no es un prefijo de texto
`C02F1/44` no contiene a `C02F1/42`, aunque el texto empiece igual. Y `H01M4/58` **sí** es descendiente
de `H01M4/36`, aunque el texto no lo sugiera. **Decisión:** cada código de los YAML incluye a sus
descendientes según los niveles del esquema (`CpcScheme.expand`), no por prefijo de texto.

## Decisión: nuevo campo `cpc_qualified`
Se reemplaza `cpc_combined_with`, que no tenía semántica definida, por `cpc_qualified`: una lista de
`{codes, with_any}`. Los `codes` solo cuentan si la familia también tiene algún código de
`with_any`. La "coincidencia CPC" de un frente queda así: algún código de `cpc_any` (con sus
descendientes) **o** algún `cpc_qualified` con su contexto. Después se aplica la regla del frente
(`cpc`, `cpc+keyword` o `cpc|keyword`).

## Limitaciones
- Amplitud de los códigos que bastan por sí solos: de 1 símbolo (agua atmosférica) a 255 (edición
  génica, por `A01H6`, que agrupa plantas por taxonomía). Las keywords obligatorias de ese frente
  contienen esa amplitud. La precisión real se mide en F1 con los sets etiquetados.
- El esquema cambia en cada versión CPC (trimestral). Al actualizar `CPCTitleList`, volver a
  correr `spikes/f0g_cpc.py`.
