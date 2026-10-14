# STI Surveillance Platform — Design

Fuente de verdad del diseño: `docs/superpowers/plans/2026-10-14-sti-surveillance.md` (sección Context y tasks 1–9) más `powerbi_consolidado.md` (secciones 3–8, adaptadas al modelo NNDSS + Oregon).

## Decisiones
- Fuentes: CDC NNDSS Weekly (nacional, semanal, 4 enfermedades), Oregon Monthly Reportable Disease (condado/sexo/edad/raza), Census PEP (población por estado).
- HIV: solo desde Oregon. NNDSS no lo publica; AtlasPlus no tiene API, queda fuera.
- Oregon trae marginales (una dimensión demográfica por fila): toda medida fuerza un `demographic_type`.
- Celdas Oregon con menos de 6 casos: `cases NULL` + `is_masked`, nunca imputadas.
- Seguridad: RLS por estado (NNDSS) y condado (Oregon); OLS sobre `race_*`, `age_group` y `mart_revisions`; RLS+OLS combinadas en un solo rol.
- Sin Publish to web; RLS probada en workspace con trial de Fabric o developer tenant de M365.
- MCP: rol Postgres read-only + regex como defensa en profundidad.
