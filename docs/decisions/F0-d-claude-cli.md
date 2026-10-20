# ADR F0-d — LLM por lotes con `claude -p` (login Max) en Windows

- **Fecha:** 2026-10-19
- **Estado:** aceptada
- **Script:** `spikes/f0d_claude_cli.py` · resultados crudos en `data/spikes/f0d/` (local, no versionado)

## Pregunta
¿Puede el pipeline clasificar y traducir resúmenes por lotes con `claude -p` usando la suscripción Max,
con salida JSON garantizada por esquema, desde Python en Windows?

## Método
- Entorno: Claude Code 2.1.304; `claude auth status` → `authMethod: claude.ai`, `subscriptionType: max`.
  Sin `ANTHROPIC_API_KEY` ni `ANTHROPIC_AUTH_TOKEN` (se eliminan además del entorno del subproceso).
- Lote **sintético** de 13 resúmenes escritos para la prueba (no son patentes reales): 8 en inglés,
  2 en chino, 2 en japonés, 1 en coreano. 11 casos claros con etiqueta esperada y 2 ambiguos
  (sensor de PFAS en redes; boquilla de limpieza de obleas con agua ultrapura).
- Tarea: asignar dominio y frente (lista generada desde `domains/*.yaml`) y traducir al inglés si
  hace falta. Esquema JSON por `--json-schema` y validación con pydantic.
- Modelo `haiku`, `--safe-mode`, `--output-format json`, `--no-session-persistence`,
  `subprocess.run(..., encoding="utf-8")` con el lote por stdin.

## Resultados

| Configuración de herramientas | `structured_output` | Turnos | Latencia | Tokens de entrada (caché) | Exactitud (claros) |
|---|---|---|---|---|---|
| `--disallowedTools "*"` | **No** (se deniega la herramienta interna `StructuredOutput`) | 3 | 27 s | ~22,9k | (las etiquetas que intentó devolver eran correctas, pero no llegan) |
| `--tools ""` | **Sí** | 2 | 10,6–12,4 s | ~5,1k | **11/11** en 4 corridas |

- **Estabilidad:** etiquetas idénticas en 3 repeticiones consecutivas.
- **Ambiguos:** el sensor de PFAS se asignó siempre a `redes_inteligentes`, con confianza de 0,6–0,7.
  La boquilla de obleas quedó en `none` (0,85–0,93). La confianza baja en el caso ambiguo es útil
  como criterio de revisión.
- **Traducción:** las 5 traducciones ZH/JA/KO son fieles (revisión manual).
- **Costo:** `total_cost_usd` ≈ US$0,0013–0,0015 por lote de 13. Es una **estimación equivalente
  a la API**: con `authMethod: claude.ai` no se factura, solo consume del límite de uso de Max.
- **UTF-8:** sin problemas pasando el lote por stdin con `encoding="utf-8"`.

## Decisión
1. Backend LLM por defecto:
   `claude -p "<instrucción>" --safe-mode --model haiku --output-format json --json-schema <schema> --tools "" --no-session-persistence`,
   con el lote en JSON por stdin, leyendo `structured_output` y validando con pydantic.
2. **No usar `--disallowedTools "*"`**: bloquea `StructuredOutput` y rompe la salida estructurada.
3. **No usar `--bare`**: desactiva el login de suscripción (ver plan §3).
4. Antes de cada lote: comprobar `claude auth status` → `authMethod == "claude.ai"`. Si no, abortar
   (evita facturación por API inesperada).
5. Lotes de ~13–20 registros. Ítems con `confidence < 0.75` van a la cola de revisión humana.
6. Si `structured_output` falta o no valida: registrar en `errors` y reintentar una vez. Nunca
   reconstruir la respuesta parseando `result` (texto libre).

## Implicaciones
- Volumen previsto (< 2.000 registros/mes) ≈ 150 llamadas × ~12 s ≈ 30 min/mes, secuenciales.
  Consumo nocional ≈ US$0,25/mes equivalente API, lo que da margen frente al límite de Max.
- Esto **no** mide la precisión real: un lote sintético de 13 casos fáciles solo valida la mecánica.
  La precisión se mide en F1 con los sets etiquetados (≥ 60 patentes y ≥ 60 papers por dominio,
  precisión ≥ 0,85 y κ ≥ 0,7).

## Pendiente
- Ver qué devuelve `claude -p` cuando la salida no cumple el esquema (no ocurrió en 4 corridas).
- Ejecutarlo desde el Programador de tareas de Windows (mismo usuario, "Iniciar en" = carpeta del
  proyecto). Se valida en F1 con la primera corrida programada.
