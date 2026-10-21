# Guía de etiquetado (F1)

Para qué sirve: medir si las definiciones de los frentes son precisas (meta ≥ 0,85) y cuánto
dejan fuera (recall ≥ 0,70) **antes** de que el radar emita señales. Sin esto, una "señal"
podría ser ruido de clasificación.

## Qué etiquetar ahora

| Archivo | Filas | Tiempo estimado |
|---|---|---|
| `evals/papers_agua.xlsx` | 65 publicaciones | 1,5–2 h |
| `evals/papers_agrobiotech.xlsx` | 65 publicaciones | 1,5–2 h |
| `evals/patents_*.xlsx` | se generan cuando avance la carga de EPO | — |

## Cómo

1. Abre el Excel. La hoja **Guía** tiene los criterios de cada frente (qué entra y qué no).
2. En la hoja **Etiquetar**, para cada fila lee el título y el resumen y responde:
   - **pertenece**: `si`, `no` o `dudoso` (lista desplegable). La pregunta es si el trabajo
     pertenece al frente de la columna `frente_a_evaluar`.
   - **frente_correcto**: solo si respondiste `no` y el trabajo encaja en otro frente del dominio,
     o en "Otro dominio" o "Ninguno".
   - **nota**: opcional; lo que te haga dudar.
3. No hace falta abrir el enlace salvo que el resumen falte o sea ambiguo.
4. Guarda el archivo con el mismo nombre y avísame. Yo calculo precisión, recall y qué
   definiciones conviene ajustar.

Etiqueta a ciegas: el Excel no dice por qué se eligió cada fila (muestra aleatoria, caso
dudoso o trabajo que el filtro excluyó). Esa clave está en `evals/papers_*.key.csv`; mejor no
abrirla antes de terminar.

## Reglas generales

- Juzga con el título y el resumen. Si no hay resumen y el título no alcanza, marca `dudoso`.
- `si` = el trabajo trata sobre la tecnología del frente; no basta con mencionarla.
- Si no pertenece pero encaja en otro frente del mismo dominio, elígelo en `frente_correcto`.
- No busques información fuera de la fila: se mide lo que el sistema ve.

Los criterios por frente están en `src/radar/evals/criteria.py` (y en la hoja Guía).
