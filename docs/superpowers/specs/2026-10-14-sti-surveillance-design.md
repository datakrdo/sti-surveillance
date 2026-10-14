# STI Surveillance Platform — Design

Plan de implementación: `docs/superpowers/plans/2026-10-14-sti-surveillance.md`. Estado y operación: `README.md`. Origen: `powerbi_consolidado.md` (secciones 3–8, adaptadas al modelo NNDSS + Oregon).

## Decisiones
- Fuentes: CDC NNDSS Weekly (nacional, semanal, 4 enfermedades), Oregon Monthly Reportable Disease (condado/sexo/edad/raza) y Census PEP (población por estado).
- VIH: solo desde Oregon. NNDSS no lo publica; AtlasPlus no tiene API, queda fuera.
- Carga completa con upsert por clave natural, no incremental: ~95.000 filas, ~1 minuto. Solo el snapshot de NNDSS acumula historia.
- Frecuencia: semanal (jueves 06:00 UTC). Frescura de dbt: `warn` 8 días, `error` 15.
- Oregon trae marginales (una dimensión demográfica por fila): toda medida fuerza un `demographic_type`.
- Celdas Oregon con menos de 6 casos: `cases NULL` + `is_masked`, nunca imputadas.
- `fact_id` es `md5` en texto, no BIGINT.
- Seguridad (diseño, pendiente de implementar en Power BI): RLS por estado (NNDSS) y condado (Oregon); OLS sobre `race_*`, `age_group` y `mart_revisions`; RLS+OLS combinadas en un solo rol.
- Sin Publish to web; la RLS se prueba en un workspace con trial de Fabric o developer tenant de M365.
- MCP: rol Postgres read-only con permisos reaplicados por un hook de dbt, vista `mcp_oregon_county_monthly` (solo condados, un corte) para que las sumas sean aditivas y regex como defensa en profundidad.
- Versiones fijadas: `dbt-core` 1.12.6, `dbt-postgres` 1.11.0, `mcp` 2.3.*.
