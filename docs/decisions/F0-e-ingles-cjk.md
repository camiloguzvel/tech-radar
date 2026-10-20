# ADR F0-e — Título y resumen en inglés en documentos CN/JP/KR (EPO OPS)

- **Fecha:** 2026-10-20
- **Estado:** aceptada
- **Script:** `spikes/f0a_ops.py english` · resultado en `data/spikes/f0a/english-20261020-090032.json`
- **Muestra:** publicaciones de 2025-06 en `C02F`, `A01N`, `C12N` y `H01M` (con `cl`): 100 de CN,
  50 de JP y 50 de KR, vía `published-data/search/biblio` en JSON (3 llamadas, 1,5 MB).

## Pregunta
¿Cuánto hay que traducir con Claude para tener texto en inglés de las patentes asiáticas?

## Resultado

| Oficina | n | Título en inglés | Resumen en inglés | Algún resumen |
|---|---|---|---|---|
| CN | 100 | **100%** | **100%** | 100% |
| KR | 50 | **100%** | **100%** | 100% |
| JP | 50 | 52% | **52%** | 62% |

- DOCDB entrega, junto al inglés, el resumen en idioma original (`@lang="ol"`).
- En esta muestra cada documento era de una familia distinta (n familias = n documentos).
- Japón es la excepción: el 38% de los documentos no trae resumen y el 48% no tiene inglés.

## Decisión
1. `text_en` de la familia se toma, en este orden:
   1. el título y resumen en inglés de DOCDB de cualquier miembro de la familia (`docdb_en`);
   2. si no hay, se traduce con Claude el resumen original, o el título si no hay resumen
      (`llm_translation`, backend del ADR F0-d);
   3. si no hay nada, `text_en = null` y se marca. **Nunca se inventa un resumen.**
2. Carga de traducción esperada: solo una parte de los documentos JP, decenas por mes en los
   frentes piloto. Cabe sin problema en el plan Max. La traducción masiva que preveía el brief no
   hace falta.
3. Las keywords de patentes (`ta=` en OPS) funcionan sobre el texto en inglés. En los documentos JP
   sin inglés, la regla de keywords **no puede coincidir**, así que los frentes `cpc+keyword` tienen
   menor recall en Japón. Se reporta como limitación por oficina y se mide en los sets de F1.

## Limitaciones
- La muestra es de un solo mes reciente. La cobertura de inglés en años antiguos (2014–2018) **no
  está medida**: se revisa en F1 con una muestra por año.
- La calidad de los resúmenes en inglés de CN y KR (de origen o traducción automática) no se evaluó.
