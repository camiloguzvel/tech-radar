# Decisiones (ADRs) — spikes de F0

Cada spike deja un ADR corto: pregunta, método, números obtenidos y decisión.

| Spike | Pregunta | Requiere | Estado |
|---|---|---|---|
| F0-a | Volumen OPS por frente y mes, y semanas de cuota (4 GB/semana) para el backfill | Credenciales EPO OPS | **Hecho** → [F0-a-volumen-ops.md](F0-a-volumen-ops.md) |
| F0-b | ¿Está fresca la tabla de Google Patents en BigQuery? (`MAX(publication_date)`) | Cuenta Google (sandbox) | **Descartado**: no hace falta (ver F0-a) |
| F0-c | IDs de Topics de OpenAlex por frente y máximo de valores OR por filtro | API key OpenAlex | **Hecho** → [F0-c-openalex.md](F0-c-openalex.md) |
| F0-d | `claude -p --safe-mode --json-schema` en Windows con un lote de prueba | Login Max (listo) | **Hecho** → [F0-d-claude-cli.md](F0-d-claude-cli.md) |
| F0-e | Cobertura de resúmenes en inglés para CN/JP/KR (muestra de 200 documentos OPS) | Credenciales EPO OPS | **Hecho** → [F0-e-ingles-cjk.md](F0-e-ingles-cjk.md) |
| F0-f | Denominador de patentes (estadística WIPO IP Statistics u otra) | — | **Hecho** → [F0-f-denominador-patentes.md](F0-f-denominador-patentes.md) (campo padre por conteos, ver F0-a) |
| F0-g | Validar los símbolos CPC de los YAML contra el esquema CPC 2026.08 | Descarga oficial CPC | **Hecho** → [F0-g-cpc.md](F0-g-cpc.md) |
