# Decisiones (ADRs) — spikes de F0

Cada spike deja un ADR corto: pregunta, método, números obtenidos y decisión.

| Spike | Pregunta | Requiere | Estado |
|---|---|---|---|
| F0-a | Volumen OPS por frente y mes, y semanas de cuota (4 GB/semana) para el backfill | Credenciales EPO OPS | Pendiente |
| F0-b | ¿Está fresca la tabla de Google Patents en BigQuery? (`MAX(publication_date)`) | Cuenta Google (sandbox) | Pendiente |
| F0-c | IDs de Topics de OpenAlex por frente y máximo de valores OR por filtro | API key OpenAlex | Pendiente |
| F0-d | `claude -p --safe-mode --json-schema` en Windows con un lote de prueba | Login Max (listo) | **Hecho** → [F0-d-claude-cli.md](F0-d-claude-cli.md) |
| F0-e | Cobertura de resúmenes en inglés para CN/JP/KR (muestra de 200 documentos OPS) | Credenciales EPO OPS | Pendiente |
| F0-f | Denominador de patentes (estadística WIPO IP Statistics u otra) | — | Pendiente |
| F0-g | Validar los símbolos CPC de los YAML contra el esquema CPC 2026.08 | Descarga oficial CPC | Pendiente |
