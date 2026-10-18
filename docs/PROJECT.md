# STI Surveillance — Diseño, decisiones y estado

Documento único de referencia. Reemplaza los specs y planes de octubre de 2026 (siguen en el historial de git). Para el uso del proyecto, ver `README.md` / `README_es.md`; para los pasos manuales de Power BI Desktop (Windows), `docs/powerbi_windows_runbook.md`.

## 1. Qué es y en qué estado está

Pipeline gratuito de vigilancia de ITS en EE. UU.: CDC NNDSS (semanal, nacional) + Oregon (mensual, con condado/sexo/edad/raza) + Census (población) → Postgres (Neon) → dbt → modelo compuesto de Power BI con RLS/OLS → informe de 7 páginas (ES/EN) → MCP de solo lectura. Encima, una demo pública gratuita (sitio estático + MCP remoto).

| Área | Estado |
|---|---|
| Ingesta, dbt, CI semanal, MCP local (`mcp_reader`) | Hecho y verificado (`dbt build` 70/70, MCP probado desde Claude Code) |
| Modelo Power BI, medidas, agregación, RLS/OLS (Desktop) | Hecho y verificado con anclas y *View as* |
| Rediseño del informe (navegación, grilla, color por enfermedad) | Generado y validado contra el esquema; **falta abrirlo en Desktop** |
| Demo pública (`site/`, `worker/`, workflows) | Código probado en local; **falta desplegar** (pasos manuales, sección 7) |
| Prueba de RLS/OLS en el servicio de Power BI | Pendiente: no hay tenant de Microsoft 365 |

## 2. Fuentes (probadas en vivo el 2026-10-14; gratis y sin API key)

| Fuente | Endpoint | Volumen / cobertura | Clave natural |
|---|---|---|---|
| CDC NNDSS Weekly | `data.cdc.gov/resource/x9gk-5huc` | 69.720 filas ETS, 2022–2026-W40 | `(year, week, label, states)` |
| Oregon Monthly Reportable Disease | `data.oregon.gov/resource/rk77-sqhz` | 25.125 filas cargadas, 2021–2026-M09 | `(mmwr_year, month, disease_name, demographic, demographic_level, confirmation_status)` |
| Census PEP Vintage 2025 | `NST-EST2025-ALLDATA.csv` | población por estado 2020–2025 | `NAME` |

Descartadas: California CHHS (termina en 2021), Illinois IDPH (≤2016), NYC HIV (anual, ≤2022), AtlasPlus (sin API), Census API (exige key; se usa el CSV).
Enfermedades: NNDSS = clamidia, gonorrea, sífilis primaria y secundaria, sífilis congénita. Oregon añade sífilis temprana y **VIH** (único origen de VIH). Cada fila de Oregon es un marginal: una sola dimensión demográfica, sin cruces.

## 3. Arquitectura

```
CDC · Oregon · Census → scripts/ingest.py → Neon raw.* → dbt → analytics_marts.* ─┬─► Power BI (compuesto, RLS/OLS)
         (GitHub Actions, jueves 06:00 UTC)        └─ snapshot m1 → mart_revisions ├─► MCP local (mcp_reader, laboratorio)
                                                                                    └─► scripts/export_public.py → site/data/*.json
                                                                                          ├─► GitHub Pages (sitio estático)
                                                                                          └─► Cloudflare Worker (MCP remoto)
```

- **Marts:** `dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, `dim_date`; hechos `fct_nndss_weekly` (semana × estado × enfermedad) y `fct_oregon_monthly` (mes × corte × enfermedad); `agg_weekly_national`, `mart_revisions`, `mart_data_quality`, vista `mcp_oregon_county_monthly`. `fact_id` es `md5` en texto.
- **Modelo Power BI:** 2 hechos en DirectQuery, 5 dimensiones Dual, `dim_geography` en Import (el editor rechaza RLS sobre una tabla Dual que referencia la Import `dim_access`), agregación `agg_weekly_national` en Import, 13 relaciones. Medidas en `_Measures` por carpetas (NNDSS 15, Oregon 7, Quality 4, QA 4).
- **Seguridad:** roles RLS (`State_Analyst`, `County_Analyst`, `Admin`) y OLS (`Restricted_Epidemiologist`, `Restricted_State_Analyst`) sobre `race_group`, `age_group`, `demographic_level` y `mart_revisions`. Un usuario = un rol: combinar uno con filtros y otro solo con OLS une los filtros de fila (93 vs 38 geografías), por eso RLS+OLS van juntas en `Restricted_State_Analyst`.
- **Roles de base:** `mcp_reader` y `pbi_reader` solo lectura, con permisos reaplicados por el hook `on-run-end` de dbt (`mcp_reader` sin `SELECT` en `dim_demographic`, `fct_oregon_monthly` ni `mart_revisions`).
- **Informe:** lienzo 1920×1080, grilla de 8 px, navegación superior, segmentadores sincronizados, color fijo por enfermedad (medida `Disease Color`); generado por `scripts/build_report_layout.py` para ES y EN. Tema `theme/dark_accessible.json` con tests de contraste.

## 4. Decisiones de diseño (y por qué)

- **Dos fuentes:** ninguna API gratuita reciente tiene ITS con demografía; NNDSS es nacional sin demografía ni VIH, Oregon tiene ambos.
- **Carga completa con upsert, no incremental:** ~95.000 filas en ~1 minuto; solo `snap_nndss_weekly` acumula historia. Frecuencia semanal; frescura de dbt: aviso 8 días, error 15.
- **Celdas de Oregon con menos de 6 casos:** `cases NULL` + `is_masked`, nunca imputadas; las tasas usan solo celdas visibles.
- **Cero ≠ no disponible:** en NNDSS `-` = sin casos (se carga como 0); solo `U` queda `NULL` (213 filas, Maryland y Ohio).
- **Tasas en persona-años:** población anual y períodos de Oregon de 28/35 días ⇒ tasa = casos × 100.000 / (Σ población semanal / (365,25/7)), con filas de población > 0 y casos conocidos.
- **El MCP ve un solo corte:** la vista `mcp_oregon_county_monthly` (solo condados) hace aditiva cualquier `SUM`. El filtro regex del MCP (`[OLS-HIPAA]`) es solo una guarda de demostración; la barrera real es el rol de base.
- **Nueva York City se suma a NY** (Census solo tiene el estado).
- **Total estatal de Oregon:** corte propio `Statewide`; `Geography` contiene solo condados (si no, 82.066 vs 80.587 en clamidia).
- **Versiones fijadas:** sin fijar `dbt-core`, pip resolvió una beta sin soporte de postgres y falló el primer CI. `dbt-core` 1.12.6, `dbt-postgres` 1.11.0, `mcp` 2.3.*.
- **Sin *Publish to web*:** expone los datos y no admite RLS (tampoco DirectQuery); la demo pública es un HTML estático propio.

## 5. Trampas de datos que el diseño ya cubre

1. Sumar Oregon sin filtrar el tipo demográfico cuenta cada caso ≈5 veces (clamidia: 500.312 en todos los cortes vs 80.587 por condados).
2. `demographic_level` repite los valores de `age_group`/`race_group`: ocultar solo estas dos deja los datos visibles; por eso también está restringida.
3. 70,7 % de las filas de Oregon están enmascaradas; las sumas por condado subestiman el total estatal (HIV: 376 de 1.291 visibles).
4. Nombres sucios (`"Multnomah  County"` con doble espacio): se normalizan; 36 condados + `Unknown County`.
5. Sífilis primaria/secundaria (NNDSS) ≠ sífilis temprana (Oregon): `comparable_across_sources = false`.
6. NNDSS es provisional y se revisa tras publicarse; el snapshot registra cada cambio.
7. `SAMEPERIODLASTYEAR` sobre una sola semana queda vacío; el informe usa la comparación alineada por semana MMWR (difieren justo en los 2.833 casos de 2025-W1).
8. Posible reporte parcial de CA gonorrea en 2026-W40 (hipótesis).

## 6. Anclas de verificación (carga del 2026-10-14; `sql/qa_anchors.sql` las regenera)

Los valores que dependen de datos nuevos (`fct_*`, semana de referencia, estados en brote de la semana en curso) cambian con cada ingesta: antes de dar algo por fallido, regenerar con el SQL. Los históricos solo cambian si el CDC revisa.

| Id | Ancla | Valor |
|---|---|---|
| A1 | Filas dim_disease / dim_geography / dim_mmwr_week / dim_epi_month / dim_demographic / dim_date / fct_nndss / fct_oregon / agg / mart_revisions / mart_data_quality / dim_access | 6 / 93 / 303 / 69 / 39 / 2.191 / 55.776 / 25.125 / 996 / 55.776 / 3 / 4 |
| A2 | Casos NNDSS por enfermedad | CHL 3.189.987 · GON 1.060.446 · SYP_PS 20.953 · SYP_CONG 24 |
| A3 | CA, GON, 2024-W52 | 499 |
| A4 | Tasa anualizada: CA CHL 2024 · nacional GON 2025 | 259,434 · 62,036 |
| A5 | GON nacional 2026 sem. 1–40: casos · LY MMWR · YoY · LY SAMEPERIODLASTYEAR | 163.363 · 167.261 · −2,33 % · 164.428 |
| A6 | Corredor CA GON sem. 40: P25 · P50 · P75 · casos 2026-W40 | 657,75 · 810 · 885,75 · 1 |
| A7 | Estados en brote GON: 2026-W40 · 2026-W38 | 11 · 15 |
| A8 | Semana de referencia · última semana | 202638 · 202640 |
| A9 | Oregon CHL por corte: Age · Geography · Race (alone) · Race (primary) · Sex · Statewide | 81.886 · 80.587 · 92.237 · 81.803 · 81.733 · 82.066 |
| A10 | Multnomah CHL: 2026-M01 · 2025 · total · tasa 2025 | 294 · 3.376 · 23.787 · 414,658 |
| A11 | % celdas suprimidas: Geography · Statewide · Sex · Age · Race (alone) · Race (primary) | 79,2 · 0,0 · 60,7 · 68,8 · 58,3 · 65,9 |
| A12 | Cobertura de condados sobre el total estatal | HIV 29,1 % · CHL 98,2 % |
| A13 | GON 2025: OR · CA · nacional | 4.073 · 31.479 · 217.373 |
| A14 | Oregon CHL por edad (solo sin OLS) | 20–29: 41.900 · 10–19: 16.587 · 30–39: 15.456 · 40–49: 5.457 · 50–59: 1.991 · 60–69: 485 · <5: 10 |
| A15 | Vista del MCP | 12.395 filas · CHL 80.587 |

## 7. Demo pública (diseño)

**Intención:** que un recruiter vea cómo luce el informe y pueda preguntarle a los datos, sin cuentas ni pagos.

- **Metas:** sitio estático en GitHub Pages con 3 vistas (Resumen, Mapa, Corredor), ES/EN, filtros de enfermedad/año/estado, 5 preguntas de ejemplo calculadas en el navegador, bloque "Conecta tu propio Claude", modo recorrido `?tour=1`; MCP remoto de solo lectura en Cloudflare Workers; repo listo para hacerse público.
- **No metas:** no embeber Power BI (exige licencia y no admite DirectQuery/RLS); no chat libre dentro de la página (requeriría un LLM de pago); no consultas en vivo a Postgres; no el dataset del Oregon Health Authority (condados y demografía) ni las revisiones en lo público; las filas del estado de Oregon de NNDSS sí se publican; no logos de terceros.
- **Portada:** `scripts/make_cover_gif.sh` regenera `docs/img/cover_en.gif` y `cover_es.gif` (Resumen → Mapa → Corredor) con capturas reales del sitio; `tests/test_readme_assets.py` impide imágenes rotas en los README.
- **Anti-metas:** filtrar credenciales o datos restringidos; cualquier cargo o tarjeta; SQL libre o escritura en el MCP público; que las cifras difieran de las anclas.
- **Datos:** solo NNDSS (CHL, GON, SYP_PS, SYP_CONG) por estado y semana. VIH no está porque solo existe en Oregon.
- **Flujo:** `scripts/export_public.py` → `site/data/nndss.json` (1,8 MB) y `anchors.json`. `site/js/metrics.js` concentra los cálculos y lo usan el sitio y el Worker, así coinciden. `pages.yml` exporta, corre `node --test` (compara con las anclas SQL) y publica; `weekly_ingest.yml` lo invoca cada semana. El Worker lee el JSON desde Pages (caché 10 min): no hace falta redesplegarlo ni un token de Cloudflare en GitHub.
- **MCP remoto (6 herramientas, parámetros validados con zod):** `list_dimensions`, `get_cases`, `get_rate_per_100k`, `get_yoy`, `get_corridor`, `top_states`, más el recurso `sti://definitions`.
- **Claude:** los conectores personalizados con MCP remoto están en todos los planes (el gratuito permite uno; en Team solo los propietarios los añaden) y el servidor debe ser público. Datos de CDC: dominio público con atribución; son provisionales. Términos de Census: sin verificar (se asume dominio público federal).
- **Auditoría previa (2026-10-18):** historial con un solo autor (noreply de GitHub); sin contraseñas ni tokens; `.env` nunca versionado; `dbt/.user.yml` versionado (se debe dejar de versionar). **El host real de Neon (`ep-…neon.tech`, sin contraseña) sí aparece en 12 archivos TMDL de `data_model/` y en 1 commit**: no es una credencial, pero conviene decidir si se acepta, se parametriza o se reescribe el historial antes de hacer público el repo.

**Pasos manuales (nadie más puede):**
1. `git rm --cached dbt/.user.yml`; commits y push.
2. Repo público; Settings → Pages → Source: **GitHub Actions**; lanzar `pages.yml` a mano.
3. `cd worker && npx wrangler login && npx wrangler deploy`; poner la URL del Worker en `site/js/config.js` y en los README; commit y push.
4. Probar el MCP público desde Claude (conector personalizado).

## 8. Pendientes y riesgos

- **Windows (Desktop):** abrir ambos `.pbip` sin errores; relación 13; los 7 botones de navegación; segmentadores sincronizados; barras con el color de la enfermedad; tarjetas sin cambios (A3, A4, A9, A10); revisión manual de accesibilidad (teclado, daltonismo, 11 pt, texto alternativo); capturas `page_1…7` del informe, que se usarán en una sección «Informe en Power BI» de los README para que se vea cómo luce (no para documentar el proceso). Si Desktop rechaza el botón de navegación generado: insertar uno a mano y el generador lo clona.
- **Servicio de Power BI (7.E):** cuando haya tenant, cambiar el dominio de `dbt/seeds/dim_access.csv` y `dbt seed`.
- **Limitaciones conocidas:** la paleta de colores no pasa el validador (banda de luminosidad y ΔE 14,9 entre CC79A7 y EF7B3A); se compensa con etiquetas porque la enfermedad se elige de una en una. La línea del informe no se puede colorear por medida. Neon suspende el cómputo a los 5 minutos: la primera consulta tras una pausa tarda unos segundos.
- **Mejoras posibles:** el exportador usa el rol del pipeline; un rol de solo lectura (`pbi_reader`) reduciría privilegios. Migrar a `uv`/`pyproject.toml`.

## 9. Convenciones de trabajo

- El agente nunca hace `git commit`/`push` ni crea repos: entrega el mensaje de commit, sin líneas de atribución.
- Nunca se versiona un `.pbix` (contiene datos) ni credenciales; secretos solo en `.env` (local) y GitHub Secrets. Power BI usa `pbi_reader`, no el dueño de la base.
- Los `.pbip`/TMDL los commitea quien trabaja en Windows. Cerrar Desktop antes de `git pull`.
- Cada cambio de un README se replica en el otro idioma.

## 10. Verificación

```bash
.venv/bin/pytest -q                                   # 45 tests (ingesta, tema, layout, exportador, README)
node --test "site/js/*.test.mjs"                      # 17 (cálculos contra anclas SQL + sitio)
(cd worker && npm test)                               # 11 (herramientas del MCP remoto)
cd dbt && ../.venv/bin/dbt build --profiles-dir .     # 70/70
```
