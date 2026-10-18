# Contexto para Claude (sesión en Windows)

Leé esto primero. Sos el asistente de una persona que va a construir el modelo semántico y el informe de Power BI de este repo en Windows. Respondé en español, corto, sin halagos.

## Qué es el proyecto
Vigilancia de ETS en EE.UU. con datos públicos: **NNDSS** (CDC, semanal por estado), **Oregon** (mensual por condado/sexo/edad/raza, celdas <6 casos suprimidas) y **Census PEP** (población). Pipeline: ingesta Python semanal (GitHub Actions, jueves 06:00 UTC) → Postgres en Neon (`raw`) → dbt (`analytics_staging`, `analytics_marts`, `analytics_seeds`) → Power BI. Un servidor MCP (`mcp/mcp_server.py`) expone una vista read-only y lee el TMDL de `data_model/`.

## Estado (2026-10-15)
- Pipeline y dbt terminados y en verde (CI run `38731585509`, commit `31ae93e`); tests de dbt cubren ceros vs `U`, corte `Statewide`, `dim_date`, grano de la agregación.
- Rol de Postgres de solo lectura `pbi_reader` (credenciales: gestor de contraseñas de la persona; **nunca** en el chat ni en archivos).
- Tema accesible `theme/dark_accessible.json` con test de contraste (`tests/test_theme_contrast.py`, 10 tests verdes).
- **Falta todo lo de Power BI**: `data_model/` no existe, `docs/img/` está vacío. Este runbook es ese trabajo.

## Decisiones de diseño que no se discuten (ya validadas contra los datos)
- **Modelo compuesto:** 2 hechos en DirectQuery (`fct_nndss_weekly`, `fct_oregon_monthly`), 5 dimensiones en Dual (todas menos `dim_geography`) y en Import `dim_geography` (decisión 2026-10-17: RLS sobre Dual no puede referenciar `dim_access`, ver 7.A), `agg_weekly_national` (agregación), `mart_revisions`, `mart_data_quality`, `dim_access`.
- **Cero vs no disponible:** en NNDSS `-` = 0 casos; solo `U` es NULL (213 filas reales: Maryland y Ohio).
- **Oregon sin doble conteo:** el total estatal vive en el corte `Statewide`; `Geography` solo tiene condados. `Cases Oregon` fuerza un único `demographic_type` (por defecto `Geography`); sumar cortes distintos da 500.312 (incorrecto).
- **Tasas** anualizadas con **persona-años** (NNDSS: Σpoblación semanal / (365,25/7); Oregon: población × `period_days` / 365,25). Nunca dividir por una sola población anual.
- **Interanual en dos formas:** MMWR alineada (semana n vs semana n del año anterior) y `SAMEPERIODLASTYEAR` con `dim_date`; difieren a propósito (semana 2025-W1 empieza 2024-12-29) y en una semana suelta la segunda da vacío.
- **Seguridad:** RLS dinámica con `dim_access` (oculta y filtrada a la fila propia; UPN desconocido = sin datos) + OLS que también oculta `dim_demographic[demographic_level]` (repite los valores de `age_group`/`race_group`). RLS y OLS de un usuario van en un mismo rol.
- **Riesgos sin verificar** (registrá lo que observes): RLS sobre dimensión Dual en modelo compuesto; sintaxis TMDL de OLS (`metadataPermission`); si *View as* de Desktop aplica OLS; comportamiento al combinar roles; "Mark as date table" en tabla Dual.

## Qué podés hacer vos y qué no
- **Sí:** leer y revisar el TMDL/DAX en `data_model/` y `git diff`; comparar cada resultado con las anclas (tabla al final); diagnosticar discrepancias con `sql/qa_anchors.sql`; redactar mensajes de commit; sugerir correcciones de DAX.
- **No:** manejar la interfaz de Desktop, Tabular Editor o DAX Studio (lo hace la persona); `git commit`/`git push` (los corre la persona; entregá el mensaje en un bloque, **sin** líneas `Co-Authored-By` ni "Generated with Claude Code"); tocar la base: solo `SELECT` en el SQL Editor de Neon que corre la persona (los `REVOKE/GRANT` de la Prueba 3 de 6.G y el cambio de `dim_access.csv` de 7.E5 están descritos paso a paso abajo).
- Nunca subir `.pbix` ni `.pbit` (contienen datos); nunca *Publish to web*.
- Si un valor no coincide con el ancla: correr `sql/qa_anchors.sql`; si el SQL también cambió es dato nuevo de la ingesta semanal, no un bug. Los valores históricos solo cambian si el CDC revisa esa semana.

## Qué traer de vuelta a Linux (para la sesión que cierra el proyecto)
(1) hallazgo de 6.D1 (date table en Dual); (2) resultado de la combinación de roles en 7.D; (3) si *View as* aplicó OLS en Desktop; (4) valores que no coincidieron y qué devolvió el SQL; (5) `git push` hecho. Con eso se hace: verificar que el recurso MCP lee el TMDL, probar el MCP en Claude Code y escribir README/spec con resultados reales.

### Actualización 2026-10-18 (cierre de la sesión en Windows)
**Estado:** Task 6 y 7.A–7.D completas y subidas. 9.2 generada y revisada a mano por el usuario (7 páginas, ES y EN); falta el gate 9.2 (teclado, daltonismo, 11 pt, alt text) y las capturas. **7.E pendiente: no hay tenant.**

**Decisiones y hallazgos para README/Limitaciones**
1. `dim_geography` quedó en **Import** (no Dual): el editor de roles rechaza RLS sobre una tabla Dual que referencia `dim_access` (Import). Modelo vigente: 2 DirectQuery · 5 Dual · 5 Import. Con eso, GATES 6.C–6.G dieron los mismos valores. Costo: la consulta por `state_code` pasa de `JOIN` a `WHERE geo_key IN (…~5.664 claves…)` (~2,3 s); es la firma de una relación *limited* (Desktop no la dibuja, sin paréntesis).
2. Roles: `State_Analyst`, `County_Analyst`, `Admin`, `Restricted_Epidemiologist` (OLS) y `Restricted_State_Analyst` (RLS + OLS). Matriz 7.C: 10/10 filas coinciden.
3. **Combinar roles:** `State_Analyst` + `Restricted_Epidemiologist` → `QA Geo Rows` = 93 (el RLS se une: el rol sin filtro anula al de 38) y el OLS se mantiene ("This field was deleted from the model…"). No asignar a un usuario un rol con RLS y otro solo con OLS; usar `Restricted_State_Analyst`.
4. **Desktop *View as* sí aplicó el OLS** (los 4 objetos restringidos fallaron como se esperaba).
5. Al duplicar un rol en Tabular Editor 2 se hereda la anotación `PBI_Id`, que debe ser un GUID único; si no, no guarda ("PBI_Id annotation… in conflict"). Se arregló borrando la anotación; Desktop escribió un `annotation PBI_Id` vacío (bloque de triple comilla) y hubo que poner un GUID de 32 hex a mano.
6. "Mark as date table" **sí funciona** sobre `dim_date` en Dual.
7. Corredor P25/P50/P75: filtra años sin hechos (`NOT ISBLANK` en `hist`; 2021 existe en `dim_mmwr_week` sin datos). Con 2022–2024: GON semana 20 de 2025 → 4157/4663/4507 → P25 4332 · P50 4507 · P75 4585 (comprobado a mano).
8. CA GON 2026: semanas 202638 = 59 y 202640 = 1 casos (reporte parcial/tardío del CDC; hipótesis); `Reference Week` 202638 no es confiable para CA.
9. `fct_oregon_monthly[population]` es `numeric` en Postgres: debe ir como **Decimal** en el modelo (Whole number rompe los filtros `population > 0` en DirectQuery).
10. `Person-Years Oregon` se reescribió iterando `dim_epi_month` (evita `RELATED`/`NOT`/`ISBLANK` dentro de `FILTER` en DirectQuery). Limitación: ya no excluye del denominador las 34 filas no suprimidas con `cases` vacío; puede diferir levemente en otros cortes.
11. En DirectQuery no cambiar tipos con Power Query (error "can't be used for DirectQuery"): se cambian en el panel Data.
12. Agregación (6.G): Prueba 2 en DAX Studio confirma `RewriteAttempted` con match y `Scan` sobre `agg_weekly_national`, sin SQL; con `dim_geography` falla el rewrite y va a Postgres.
13. Informe: dos versiones sobre un solo modelo semántico: `STI_Surveillance_Model.pbip` (ES) y `STI_Surveillance_Model_EN.pbip` (EN, generado traduciendo títulos, alt text, notas y nombres de página). Las medidas conservan nombres en inglés en ambas. Los visuales se editaron como JSON PBIR con Desktop cerrado.
14. Tarjetas `Reference Week` / `Latest Week With Data`: formato `0000"-W"00` aplicado desde Tabular Editor 2 (el menú de Desktop no ofrece *Custom*) y *Display units* = None.
15. Filled map: el relleno por tasa se configura en *Fill colors → fx* (no hay *Color saturation*), con `nullColoringStrategy = noColor` para que los territorios sin población queden sin dato y no en 0.

**Pendiente en Windows:** gate 9.2 manual; capturas `rls_01`…`rls_10`, `ols_*`, `page_1`…`page_7`; borrar el `.pbit` sobrante de `data_model\`; decidir si se borra o se deja oculta `_AGG`; 7.E cuando haya tenant.

**Para la sesión en Linux:** (1) verificar que el recurso MCP lee el TMDL (incluye `roles\`); (2) probar el MCP en Claude Code; (3) escribir README/spec con los hallazgos de arriba; (4) revisar `git diff` de `_Measures.tmdl`, `Restricted_Epidemiologist.tmdl` y `Query 1.dax`, que cambiaron por guardados de Desktop.

---

# Runbook

> Cada bloque termina en un **GATE** con valores esperados; no se avanza sin el anterior en ✔. Pasos: modelo (Task 6), seguridad (Task 7), informe (Task 9.2). Antes de empezar, la persona necesita por canal seguro: `PGHOST`, `PGDATABASE`, `PBI_DB_USER` (=`pbi_reader`) y `PBI_DB_PASSWORD`, más acceso a la consola de Neon (SQL Editor).

## GATE P — Entorno Windows
- [x] **P1.** Windows 10/11 con Power BI Desktop actualizado, [Tabular Editor 2](https://github.com/TabularEditor/TabularEditor/releases) (2.x, gratis), [DAX Studio](https://daxstudio.org) y Git. Instalar TE2 y DAX Studio **antes** de abrir Desktop para que aparezcan en *External Tools*.
- [x] **P2.** `git clone` del repo privado (o `git pull` si ya existe). Confirmar `git log -1` = commit del tema (paso 0.2).
- [x] **P3.** Neon Console → SQL Editor → pegar `sql/qa_anchors.sql` → Run. Comparar con la tabla de anclas (al final).
- [x] **P4.** Desktop → *File → Options and settings → Options → Current File → Data Load* → **desmarcar** "Autodetect new relationships after data is loaded".
- [x] **P5.** *Options → Preview features*: activar "Power BI Project (.pbip) save option" y "Store semantic model using TMDL format" **solo si aparecen**; si no aparecen, ya vienen activos. Reiniciar Desktop si cambiaste algo.
- [ ] **P6. Parámetro `PgHost` (el host de Neon ya no está en el repo).** Al abrir el `.pbip` por primera vez: *Inicio → Transformar datos → Editar parámetros* → `PgHost` = el valor de `PGHOST` de tu `.env` (solo el host, sin contraseña) → Aceptar → *Cerrar y aplicar*. Las credenciales guardadas siguen valiendo porque el origen (host + `neondb`) es el mismo. **No commitees ese valor:** Desktop lo escribe en `definition/expressions.tmdl`; antes de `git add` ejecutá una sola vez `git update-index --skip-worktree data_model/STI_Surveillance_Model.SemanticModel/definition/expressions.tmdl`. `tests/test_no_real_host.py` falla si el host real llega al repo.

**Expected:** las 3 herramientas abren; P3 reproduce las anclas.

---

## Task 6.A — Cargar datos (dos pasadas)
Una tabla Import no puede pasar a DirectQuery, y solo una DirectQuery puede pasar a Dual: por eso dos pasadas.

- [x] **A1. Pasada DirectQuery.** *Home → Get data → PostgreSQL database*. Server = `PGHOST` (sin `https://`, sin puerto). Database = `PGDATABASE`. **Data Connectivity mode: DirectQuery**. OK → pestaña **Database** (no Windows) → `pbi_reader` + contraseña → Connect. Navigator → `analytics_marts` → marcar **exactamente 8**: `fct_nndss_weekly`, `fct_oregon_monthly`, `dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, `dim_date` → **Load**. (Si falla la conexión → Troubleshooting.)
- [x] **A2. Pasada Import.** *Get data → PostgreSQL database* (mismo server/base) en **Import**. Marcar `agg_weekly_national`, `mart_revisions`, `mart_data_quality` (`analytics_marts`) y `dim_access` (`analytics_seeds`) → Load. **No** marcar `mcp_oregon_county_monthly`.
- [x] **A3. Nombres.** *Home → Transform data* → en Queries, *Rename* cada una al nombre sin esquema (`analytics_marts fct_nndss_weekly` → `fct_nndss_weekly`). *Close & Apply*.
- [x] **A4. Tipos** (panel Data, seleccionar columna → *Column tools → Data type*):
  - *Whole number*: `epi_week_key`, `epi_month_key`, `mmwr_year`, `mmwr_week`, `month`, `month_number`, `year`, `quarter`, `period_days`, `cases`, `population` (**solo** `fct_nndss_weekly`, que es `bigint`). **Hallazgo (2026-10-15):** `fct_oregon_monthly[population]` es `numeric` en Postgres y debe quedar como *Decimal number*; como Whole number, los filtros `population > 0` fallan en DirectQuery con "Local evaluation of Table.Join… key equality comparers is not supported".
  - *Decimal number*: `cases_week` (en `fct_nndss_weekly` **y** `agg_weekly_national`, mismo tipo en ambas o la agregación falla), `max_prev_52w`, `cum_ytd`, `cum_ytd_prev`, `first_reported_m1`, `current_m1`, `n_revisions`, `delta`, `pct_masked`, `pct_flagged`.
  - *Date* (no Date/Time): `date`, `week_start_date`, `week_end_date`, `period_start`, `period_end`.
  - *True/False*: `is_masked`, `is_flagged`, `is_reference_week`, `comparable_across_sources`.
  - *Date/Time*: `last_ingested_at`. Resto: *Text*.
- [x] **A5. Guardar como proyecto:** *File → Save as* → tipo **Power BI Project (*.pbip)** → `<repo>\data_model\STI_Surveillance_Model.pbip` (crear la carpeta `data_model`). El nombre es exacto: el servidor MCP lee `data_model/STI_Surveillance_Model.SemanticModel/definition`.

**GATE 6.A** — *DAX query view* (icono de la barra izquierda) → pegar → *Run*:
```dax
EVALUATE
ROW (
    "dim_disease", COUNTROWS ( dim_disease ),
    "dim_geography", COUNTROWS ( dim_geography ),
    "dim_mmwr_week", COUNTROWS ( dim_mmwr_week ),
    "dim_epi_month", COUNTROWS ( dim_epi_month ),
    "dim_demographic", COUNTROWS ( dim_demographic ),
    "dim_date", COUNTROWS ( dim_date ),
    "fct_nndss_weekly", COUNTROWS ( fct_nndss_weekly ),
    "fct_oregon_monthly", COUNTROWS ( fct_oregon_monthly ),
    "agg_weekly_national", COUNTROWS ( agg_weekly_national ),
    "mart_revisions", COUNTROWS ( mart_revisions ),
    "mart_data_quality", COUNTROWS ( mart_data_quality ),
    "dim_access", COUNTROWS ( dim_access )
)
```
**Expected (A1):** 6 · 93 · 303 · 69 · 39 · 2.191 · 55.776 · 25.125 · 996 · 55.776 · 3 · 4.
- [x] 12 conteos = SQL · [x] 12 nombres exactos · [x] sin errores · [x] el `.pbip` existe en `data_model\`.

## Task 6.B — Modos de almacenamiento
- [x] **B1.** *Model view* → seleccionar cada dimensión (`dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, `dim_date`) → *Properties → Advanced → Storage mode = **Dual*** → aceptar aviso. (Se puede multiseleccionar con Ctrl.)
- [x] **B2.** No tocar el resto: hechos en DirectQuery; `agg_weekly_national`, `mart_revisions`, `mart_data_quality`, `dim_access` en Import.

**GATE 6.B:** tooltip del encabezado de cada tabla en Model view → **2 DirectQuery · 6 Dual · 4 Import** (modelo original; el vigente, tras 7.A, es **2 DirectQuery · 5 Dual · 5 Import**, con `dim_geography` en Import). Confirmación textual (si existe TMDL view): arrastrar una tabla a TMDL view y buscar `mode:` en `partition`.
- [x] 12/12 en el modo esperado.

## Task 6.C — Relaciones (13)
*Model view → Manage relationships → New*. Todas: **Many to one (*:1)**, **Single**, **activa**, *Assume referential integrity* **desmarcado**. Si Desktop creó alguna sola, borrarla.

| # | Desde (muchos) | Hacia (uno) |
|---|---|---|
| 1 | `fct_nndss_weekly[epi_week_key]` | `dim_mmwr_week[epi_week_key]` |
| 2 | `fct_nndss_weekly[disease_key]` | `dim_disease[disease_key]` |
| 3 | `fct_nndss_weekly[geo_key]` | `dim_geography[geo_key]` |
| 4 | `fct_nndss_weekly[week_start_date]` | `dim_date[date]` |
| 5 | `fct_oregon_monthly[epi_month_key]` | `dim_epi_month[epi_month_key]` |
| 6 | `fct_oregon_monthly[disease_key]` | `dim_disease[disease_key]` |
| 7 | `fct_oregon_monthly[geo_key]` | `dim_geography[geo_key]` |
| 8 | `fct_oregon_monthly[demographic_key]` | `dim_demographic[demographic_key]` |
| 9 | `agg_weekly_national[epi_week_key]` | `dim_mmwr_week[epi_week_key]` |
| 10 | `agg_weekly_national[disease_key]` | `dim_disease[disease_key]` |
| 11 | `mart_revisions[epi_week_key]` | `dim_mmwr_week[epi_week_key]` |
| 12 | `mart_revisions[geo_key]` | `dim_geography[geo_key]` |
| 13 | `mart_revisions[disease_key]` | `dim_disease[disease_key]` |

`dim_access` y `mart_data_quality` quedan **sin** relaciones.

**GATE 6.C**
- [x] *Manage relationships* lista exactamente 13, todas *:1, Single, activas. Ninguna marcada como *limited* (línea con corchetes/paréntesis en Model view). Si aparece una: revisar modos de 6.B. Las 9–13 (Import → Dual) son regulares porque Dual también tiene copia Import.
- [x] DAX query view:
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_disease[disease_key], "casos", SUM ( fct_nndss_weekly[cases_week] ) )
ORDER BY dim_disease[disease_key]
```
  **Expected (A2):** CHL 3.189.987 · GON 1.060.446 · SYP_CONG 24 · SYP_PS 20.953 (HIV y SYP_EARLY no aparecen).
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "n", COUNTROWS ( fct_oregon_monthly ) )
ORDER BY dim_demographic[demographic_type]
```
  **Expected:** 6 tipos (`Age Group`, `Geography`, `Race (alone or in combination)`, `Race (primary/least common race)`, `Sex`, `Statewide`), suma de `n` = 25.125.

## Task 6.D — Fechas, orden y limpieza
- [x] **D1.** Seleccionar `dim_date` → *Table tools → Mark as date table* → columna `date`. Si la opción está deshabilitada (Dual), **anotar** "Mark as date table no disponible en Dual" para el README y seguir; no cambiar `dim_date` a Import. **Hallazgo (2026-10-15): "Mark as date table" funcionó sobre `dim_date` en Dual.**
- [x] **D2.** *Sort by column*: `dim_date[month_name]` por `month_number`; `dim_epi_month[month_label]` por `epi_month_key`.
- [x] **D3.** *Summarization = Don't summarize* en: todas las `*_key`, `mmwr_year`, `mmwr_week`, `month`, `month_number`, `year`, `quarter`, `period_days`.
- [x] **D4.** *Hide in report view*: todas las `*_key` (salvo `geo_key` de `dim_geography`), `fact_id`, `max_prev_52w`, `cum_ytd`, `cum_ytd_prev`, `first_reported_m1`, `current_m1`. **Ocultar tablas** `dim_access` y `agg_weekly_national`.
- [x] **D5.** *Data category*: `dim_geography[state_name]` → *State or Province*; `dim_geography[county_name]` → *County*.
- [x] **D6.** *Home → Enter data* → una columna `x`, sin filas → nombre `_Measures` → Load. Ocultar `x`.

**GATE 6.D:** date table marcada (o hallazgo anotado) · un visual de tabla con `month_name` ordena Jan…Dec.

## Task 6.E — Medidas NNDSS
En `_Measures` → *Table tools → New measure*. Crear **en este orden**. *Measure tools → Display folder* = `NNDSS`.

```dax
Cases NNDSS = SUM ( fct_nndss_weekly[cases_week] )
```
Formato `#,##0`.
```dax
Cases NNDSS (with population) =
CALCULATE ( [Cases NNDSS], fct_nndss_weekly[population] > 0 )
```
```dax
Person-Years NNDSS =
DIVIDE (
    SUMX (
        FILTER (
            fct_nndss_weekly,
            NOT ISBLANK ( fct_nndss_weekly[cases_week] )
                && fct_nndss_weekly[population] > 0
        ),
        fct_nndss_weekly[population]
    ),
    365.25 / 7
)
```
Formato `#,##0`.
```dax
Rate per 100k NNDSS =
DIVIDE ( [Cases NNDSS (with population)], [Person-Years NNDSS] ) * 100000
```
Formato `0.0`. Tasa **anualizada** (persona-años).
```dax
Cases LY (MMWR aligned) =
VAR weeks = VALUES ( dim_mmwr_week[mmwr_week] )
VAR prevYears =
    SELECTCOLUMNS ( VALUES ( dim_mmwr_week[mmwr_year] ), "y", dim_mmwr_week[mmwr_year] - 1 )
RETURN
    CALCULATE (
        [Cases NNDSS],
        REMOVEFILTERS ( dim_mmwr_week ),
        TREATAS ( weeks, dim_mmwr_week[mmwr_week] ),
        TREATAS ( prevYears, dim_mmwr_week[mmwr_year] )
    )
```
```dax
YoY % (MMWR aligned) =
DIVIDE ( [Cases NNDSS] - [Cases LY (MMWR aligned)], [Cases LY (MMWR aligned)] )
```
Formato `0.0%`.
```dax
Cases LY (SAMEPERIODLASTYEAR) =
CALCULATE ( [Cases NNDSS], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```
Solo con campos de `dim_date` en el visual (si además filtra `dim_mmwr_week`, se anula).
```dax
Corridor P75 =
VAR w = SELECTEDVALUE ( dim_mmwr_week[mmwr_week] )
VAR y = SELECTEDVALUE ( dim_mmwr_week[mmwr_year] )
VAR hist =
    FILTER (
        ALL ( dim_mmwr_week[mmwr_year] ),
        VAR yr = dim_mmwr_week[mmwr_year]
        RETURN
            yr >= y - 5 && yr < y
                && NOT ISBLANK (
                    CALCULATE (
                        [Cases NNDSS],
                        REMOVEFILTERS ( dim_mmwr_week ),
                        dim_mmwr_week[mmwr_week] = w,
                        dim_mmwr_week[mmwr_year] = yr
                    )
                )
    )
RETURN
    IF (
        NOT ISBLANK ( w ) && NOT ISBLANK ( y ),
        PERCENTILEX.INC (
            hist,
            VAR yr = dim_mmwr_week[mmwr_year]
            RETURN
                CALCULATE (
                    [Cases NNDSS],
                    REMOVEFILTERS ( dim_mmwr_week ),
                    dim_mmwr_week[mmwr_week] = w,
                    dim_mmwr_week[mmwr_year] = yr
                ),
            0.75
        )
    )
```
`Corridor P25` y `Corridor P50`: misma fórmula con `0.25` y `0.5` en la última línea. **Hallazgo (2026-10-15):** sin el `NOT ISBLANK(...)` dentro de `hist`, el año 2021 (existe en `dim_mmwr_week`, sin hechos) entraba como valor bajo y E5 daba 387 · 748 · 872 en vez de 657,75 · 810 · 885,75. Con el filtro, E5 coincide.
```dax
Excess over P75 =
VAR p75 = [Corridor P75]
RETURN IF ( NOT ISBLANK ( p75 ), MAX ( 0, [Cases NNDSS] - p75 ) )
```
```dax
States in Outbreak =
COUNTROWS ( FILTER ( VALUES ( dim_geography[state_code] ), [Cases NNDSS] > [Corridor P75] ) )
```
```dax
Reference Week =
CALCULATE ( MAX ( dim_mmwr_week[epi_week_key] ), dim_mmwr_week[is_reference_week] = TRUE () )
```
```dax
Latest Week With Data = MAX ( fct_nndss_weekly[epi_week_key] )
```
Formato de las dos últimas: `0`.

**GATE 6.E** (DAX query view; cada bloque por separado):

*E1 (A3)*
```dax
EVALUATE ROW ( "v", CALCULATE ( [Cases NNDSS], dim_geography[geo_key] = "CA",
        dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202452 ) )
```
→ **499**

*E2 (A4)*
```dax
EVALUATE ROW (
    "CA_CHL_2024", CALCULATE ( [Rate per 100k NNDSS], dim_geography[geo_key] = "CA",
        dim_disease[disease_key] = "CHL", dim_mmwr_week[mmwr_year] = 2024 ),
    "GON_2025", CALCULATE ( [Rate per 100k NNDSS], dim_disease[disease_key] = "GON",
        dim_mmwr_week[mmwr_year] = 2025 )
)
```
→ **259,434 · 62,036** (±0,001). ~63,0 = se está usando una sola población.

*E3 (A5)*
```dax
EVALUATE ROW (
    "cases", CALCULATE ( [Cases NNDSS], dim_disease[disease_key] = "GON",
        dim_mmwr_week[mmwr_year] = 2026, dim_mmwr_week[mmwr_week] <= 40 ),
    "ly_mmwr", CALCULATE ( [Cases LY (MMWR aligned)], dim_disease[disease_key] = "GON",
        dim_mmwr_week[mmwr_year] = 2026, dim_mmwr_week[mmwr_week] <= 40 ),
    "yoy", CALCULATE ( [YoY % (MMWR aligned)], dim_disease[disease_key] = "GON",
        dim_mmwr_week[mmwr_year] = 2026, dim_mmwr_week[mmwr_week] <= 40 ),
    "ly_sply", CALCULATE ( [Cases LY (SAMEPERIODLASTYEAR)], dim_disease[disease_key] = "GON",
        DATESBETWEEN ( dim_date[date], DATE ( 2026, 1, 1 ), DATE ( 2026, 10, 4 ) ) )
)
```
→ **163.363 · 167.261 · −0,0233 · 164.428** (la diferencia 2.833 = semana 2025-W1, que empieza el 2024-12-29).

*E4 (A5b)*
```dax
EVALUATE ROW (
    "cases", CALCULATE ( [Cases NNDSS], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "ly_mmwr", CALCULATE ( [Cases LY (MMWR aligned)], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "ly_sply", CALCULATE ( [Cases LY (SAMEPERIODLASTYEAR)], dim_disease[disease_key] = "GON",
        DATESBETWEEN ( dim_date[date], DATE ( 2026, 10, 4 ), DATE ( 2026, 10, 4 ) ) )
)
```
→ **4.627 · 4.830 · (vacío)**. El vacío es el resultado esperado (2025-10-04 es sábado; ninguna semana empieza ese día).

*E5 (A6)*
```dax
EVALUATE ROW (
    "p25", CALCULATE ( [Corridor P25], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "p50", CALCULATE ( [Corridor P50], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "p75", CALCULATE ( [Corridor P75], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "cases", CALCULATE ( [Cases NNDSS], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "excess", CALCULATE ( [Excess over P75], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 )
)
```
→ **657,75 · 810 · 885,75 · 1 · 0**

*E6 (A7)*
```dax
EVALUATE ROW (
    "w40", CALCULATE ( [States in Outbreak], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "w38", CALCULATE ( [States in Outbreak], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202638 )
)
```
→ **11 · 15**

*E7 (A8)* `EVALUATE ROW ( "ref", [Reference Week], "latest", [Latest Week With Data] )` → **202638 · 202640**

*E8* `EVALUATE ROW ( "w53_2025", CALCULATE ( [Cases NNDSS], dim_mmwr_week[epi_week_key] = 202553 ), "w53_2026", CALCULATE ( [Cases NNDSS], dim_mmwr_week[epi_week_key] = 202653 ) )` → **> 0 · vacío**

- [x] E1–E8 correctos · [x] ningún "casi" sin explicar.

## Task 6.F — Medidas Oregon, calidad, QA
Display folder `Oregon`:
```dax
Cases Oregon =
VAR t = SELECTEDVALUE ( dim_demographic[demographic_type], "Geography" )
RETURN
    CALCULATE ( SUM ( fct_oregon_monthly[cases] ), KEEPFILTERS ( dim_demographic[demographic_type] = t ) )
```
```dax
Cases Oregon (statewide) =
CALCULATE ( SUM ( fct_oregon_monthly[cases] ), dim_demographic[demographic_type] = "Statewide" )
```
```dax
Cases Oregon (rate base) =
CALCULATE ( [Cases Oregon], fct_oregon_monthly[is_masked] = FALSE (), fct_oregon_monthly[population] > 0 )
```
```dax
Person-Years Oregon =
VAR t = SELECTEDVALUE ( dim_demographic[demographic_type], "Geography" )
RETURN
    CALCULATE (
        SUMX (
            dim_epi_month,
            dim_epi_month[period_days]
                * CALCULATE (
                    SUM ( fct_oregon_monthly[population] ),
                    fct_oregon_monthly[is_masked] = FALSE (),
                    fct_oregon_monthly[population] > 0
                )
        ) / 365.25,
        KEEPFILTERS ( dim_demographic[demographic_type] = t )
    )
```
```dax
Rate per 100k Oregon =
DIVIDE ( [Cases Oregon (rate base)], [Person-Years Oregon] ) * 100000
```
```dax
% Suppressed Cells =
VAR t = SELECTEDVALUE ( dim_demographic[demographic_type], "Geography" )
RETURN
    CALCULATE (
        DIVIDE (
            COUNTROWS ( FILTER ( fct_oregon_monthly, fct_oregon_monthly[is_masked] ) ) + 0,
            COUNTROWS ( fct_oregon_monthly )
        ),
        KEEPFILTERS ( dim_demographic[demographic_type] = t )
    )
```
```dax
Share of Statewide Captured = DIVIDE ( [Cases Oregon], [Cases Oregon (statewide)] )
```
Formatos: casos `#,##0`; tasa `0.0`; los dos `%` en `0.0%`.

Folder `Quality / Revisions`:
```dax
Revisions (n) = SUM ( mart_revisions[n_revisions] )
```
```dax
Revision Delta (abs) = SUMX ( mart_revisions, ABS ( mart_revisions[delta] ) )
```
```dax
Revisions Status =
IF ( ISBLANK ( [Revisions (n)] ) || [Revisions (n)] = 0, "No revisions recorded yet", FORMAT ( [Revisions (n)], "#,##0" ) & " revisions" )
```
```dax
Latest Ingest (UTC) = MAX ( mart_data_quality[last_ingested_at] )
```
Folder `QA` (cuatro medidas separadas):
```dax
QA Geo Rows = COUNTROWS ( dim_geography )
```
```dax
QA Access Rows = COUNTROWS ( dim_access )
```
```dax
QA Demographic Rows = COUNTROWS ( dim_demographic )
```
```dax
QA Revision Rows = COUNTROWS ( mart_revisions )
```

**GATE 6.F**

*F1 (A9)*
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "chl", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "CHL" ) )
ORDER BY dim_demographic[demographic_type]
```
→ Age Group **81.886** · Geography **80.587** · Race (alone) **92.237** · Race (primary) **81.803** · Sex **81.733** · Statewide **82.066**. Además: una tarjeta en el lienzo con `Cases Oregon` y filtro CHL, sin filtros de demografía → **80.587** (nunca 500.312 ni 162.653).

*F2 (A9b)*
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_level], FILTER ( ALL ( dim_demographic[demographic_type] ), dim_demographic[demographic_type] = "Sex" ),
    "chl", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "CHL" ) )
```
→ Female **52.038** · Male **29.695** · Nonbinary/Unknown vacíos.

*F3 (A10)*
```dax
EVALUATE ROW (
    "m01", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[epi_month_key] = 202601 ),
    "y2025", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[mmwr_year] = 2025 ),
    "all", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL" ),
    "rate2025", CALCULATE ( [Rate per 100k Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[mmwr_year] = 2025 )
)
```
→ **294 · 3.376 · 23.787 · 414,658**

*F4 (A11)*
```dax
EVALUATE SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "supp", [% Suppressed Cells] ) ORDER BY dim_demographic[demographic_type]
```
→ Age Group **0,688** · Geography **0,792** · Race (alone) **0,583** · Race (primary) **0,659** · Sex **0,607** · Statewide **0,000**

*F5 (A12)*
```dax
EVALUATE ROW (
    "hiv_visible", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "HIV" ),
    "hiv_state", CALCULATE ( [Cases Oregon (statewide)], dim_disease[disease_key] = "HIV" ),
    "hiv_share", CALCULATE ( [Share of Statewide Captured], dim_disease[disease_key] = "HIV" ),
    "chl_share", CALCULATE ( [Share of Statewide Captured], dim_disease[disease_key] = "CHL" )
)
```
→ **376 · 1.291 · 0,291 · 0,982**

*F6* `EVALUATE ROW ( "rev", [Revisions (n)], "status", [Revisions Status], "ingest", [Latest Ingest (UTC)] )` → **0** · "No revisions recorded yet" · fecha de la última corrida de CI (≤ 8 días).

- [x] F1–F6 correctos.

## Task 6.G — Agregación
- [x] **G1.** Panel Data → clic derecho `agg_weekly_national` → **Manage aggregations**:

| Columna agg | Summarization | Detail table | Detail column |
|---|---|---|---|
| `cases_week` | Sum | `fct_nndss_weekly` | `cases_week` |
| `epi_week_key` | GroupBy | `fct_nndss_weekly` | `epi_week_key` |
| `disease_key` | GroupBy | `fct_nndss_weekly` | `disease_key` |

  *Apply all* sin errores (si se queja de tipos: `cases_week` Decimal en ambas, ver A4).
- [x] **G2.** `agg_weekly_national` queda oculta.

**GATE 6.G** — página temporal `_AGG` con dos tablas:
- Visual **A**: `dim_mmwr_week[mmwr_year]`, `dim_disease[disease_key]`, `[Cases NNDSS]` (debe acertar la agregación).
- Visual **B**: `dim_geography[state_code]`, `[Cases NNDSS]` (debe ir a DirectQuery).

- [x] **Prueba 1 — Performance analyzer.** *Optimize → Performance analyzer → Start recording → Refresh visuals*. A: sin fila "Direct query". B: con "Direct query".
- [x] **Prueba 2 — DAX Studio.** *External Tools → DAX Studio* → activar *All Queries* y *Server Timings* → `EVALUATE SUMMARIZECOLUMNS ( dim_mmwr_week[mmwr_year], dim_disease[disease_key], "c", [Cases NNDSS] )`. Esperado: evento de *aggregate table rewrite* con match y **sin** SQL al origen. Repetir con `dim_geography[state_code]`: sin match y con SQL.
- [x] **Prueba 3 — decisiva (Neon SQL Editor, como dueño):**
  1. `REVOKE SELECT ON analytics_marts.fct_nndss_weekly FROM pbi_reader;`
  2. Desktop: *Refresh visuals* en `_AGG`. Esperado: **A muestra datos**, **B da error de permiso**.
  3. `GRANT SELECT ON analytics_marts.fct_nndss_weekly TO pbi_reader;`
  4. Refresh: B vuelve. **No seguir sin el GRANT verificado** (el CI también lo repone en el próximo `dbt build`, pero no dejarlo colgado).
- [ ] Borrar la página `_AGG` (o dejarla oculta).

## Task 6.H — Guardar y versionar
- [x] **H1.** *File → Save*. En el explorador: `data_model\STI_Surveillance_Model.pbip`, `STI_Surveillance_Model.SemanticModel\definition\` con `model.tmdl`, `relationships.tmdl`, `tables\*.tmdl` (13 archivos: 12 tablas + `_Measures`) y `STI_Surveillance_Model.Report\`.
- [x] **H2.** Git Bash: `git grep -nE "np[g]_|PASSWORD|password" -- data_model` → **vacío**. El host de Neon sí aparece en las consultas M (no es credencial; decisión registrada).
- [x] **H3.** `git status` no lista `.pbix`, `localSettings.json` ni `cache.abf` (el `.gitignore` que genera el PBIP los excluye).
- [x] **H4.** Commit + push:
```
feat(pbi): composite semantic model with aggregations and epidemiological measures
```

**GATE FINAL Task 6:** P y 6.A–6.H en ✔ con capturas.

---

## Task 7 — RLS y OLS

`dim_access`: `ana@TENANT.onmicrosoft.com` (OR, Multnomah County) · `luis@…` (CA, *) · `admin@…` (*, *) · `sofia@…` (OR, *). En Desktop *View as → Other user* acepta cualquier texto: no hace falta tenant real hasta 7.E.

### 7.A — Roles RLS (Desktop)
*Modeling → Manage roles → New* (si se abre el editor nuevo, pasar a *Switch to DAX editor*).
- [x] **`State_Analyst`**, tabla `dim_geography`:
```dax
COUNTROWS (
    FILTER (
        dim_access,
        dim_access[user_principal_name] = USERPRINCIPALNAME ()
            && ( dim_access[state_code] = "*" || dim_access[state_code] = dim_geography[state_code] )
    )
) > 0
```
- [x] **`County_Analyst`**, tabla `dim_geography`:
```dax
COUNTROWS (
    FILTER (
        dim_access,
        dim_access[user_principal_name] = USERPRINCIPALNAME ()
            && ( dim_access[state_code] = "*" || dim_access[state_code] = dim_geography[state_code] )
            && ( dim_access[county_name] = "*" || dim_access[county_name] = dim_geography[county_name] )
    )
) > 0
```
- [x] En **ambos**, tabla `dim_access`: `dim_access[user_principal_name] = USERPRINCIPALNAME ()`
- [x] **`Admin`**: sin filtros.

**GATE 7.A:** 3 roles, sin errores de sintaxis · *Save*. Si *View as* de 7.C da un error de DirectQuery/RLS con dimensiones Dual → contingencia: `dim_geography` a Import (no tiene vuelta: hacerlo en una copia del `.pbip` primero), repetir GATES 6.C–6.G, anotar. **Hallazgo (2026-10-15):** el editor de roles rechazó el filtro RLS sobre `dim_geography` (Dual) con "A calculated column or RLS expression on a DirectQuery table cannot reference tables from a different data source", porque `dim_access` es Import. Se aplicó esta contingencia (2026-10-17) en una copia: con `dim_geography` en Import el editor acepta los 3 roles; GATES 6.C, 6.E, 6.F y 6.G (pruebas 1 y 2) se repitieron con los mismos valores. Diferencia: la consulta por `state_code` pasa de JOIN a `WHERE geo_key IN (…~5.664 claves…)` (~2,3 s), firma de relación *limited* (Desktop no la dibuja).

### 7.B — Página `_QA`
- [x] Segmentadores `dim_disease[disease_key]` y `dim_mmwr_week[mmwr_year]`.
- [x] Tarjetas: `QA Geo Rows`, `QA Access Rows`, `QA Demographic Rows`, `QA Revision Rows`, `Cases NNDSS`, `Cases Oregon`, `Cases Oregon (statewide)`.
- [x] Tabla 1: `dim_geography[geo_key]` + `Cases NNDSS`. Tabla 2: `dim_demographic[sex]` + `Cases Oregon`. Observado (2026-10-17): con `SYP_EARLY` la tabla 1 queda vacía (sin hechos NNDSS, esperado); en la tabla 2 la fila `sex` vacía y el total repiten el corte `Geography` por el `SELECTEDVALUE` de `Cases Oregon` (sin doble conteo); `Female`/`Male` solo aparecen filtrando `demographic_type = Sex`.
- [ ] Ocultar la página (clic derecho en la pestaña → *Hide page*) antes de publicar.

### GATE 7.C — Matriz RLS
*Modeling → View as* → marcar rol + **Other user** → UPN. Segmentadores GON + 2025 para `Cases NNDSS`; cambiar a CHL (sin año) para las dos columnas de Oregon.

| # | Rol | Other user | Geo Rows | Access Rows | NNDSS GON 2025 | Oregon statewide CHL | Oregon CHL |
|---|---|---|---|---|---|---|---|
| 1 | State_Analyst | `ana@TENANT.onmicrosoft.com` | 38 | 1 | 4.073 | 82.066 | 80.587 |
| 2 | State_Analyst | `luis@TENANT.onmicrosoft.com` | 1 | 1 | 31.479 | vacío | vacío |
| 3 | State_Analyst | `sofia@TENANT.onmicrosoft.com` | 38 | 1 | 4.073 | 82.066 | 80.587 |
| 4 | State_Analyst | `ANA@tenant.onmicrosoft.com` | = fila 1 | | | | |
| 5 | State_Analyst | `nadie@TENANT.onmicrosoft.com` | 0 / vacío | 0 / vacío | vacío | vacío | vacío |
| 6 | County_Analyst | `ana@TENANT.onmicrosoft.com` | 1 | 1 | vacío | vacío | 23.787 |
| 7 | County_Analyst | `luis@TENANT.onmicrosoft.com` | 1 | 1 | 31.479 | vacío | vacío |
| 8 | County_Analyst | `sofia@TENANT.onmicrosoft.com` | 38 | 1 | 4.073 | 82.066 | 80.587 |
| 9 | County_Analyst | `nadie@TENANT.onmicrosoft.com` | 0 / vacío | 0 / vacío | vacío | vacío | vacío |
| 10 | Admin | cualquiera | 93 | 4 | 217.373 | 82.066 | 80.587 |

Fila 6: el condado limitado oculta la fila estatal `OR` (su `county_name` es vacío), y con ella todos los cortes demográficos. Filas 5/9: `COUNTROWS` sobre tabla vacía muestra *(Blank)*; ambos cuentan como 0.
- [x] 10 filas coinciden · [x] `nadie` no ve ningún dato · [x] tabla 1 nunca muestra estados ajenos · [ ] capturas `docs/img/rls_01.png` … `rls_10.png`.

### 7.D — OLS con Tabular Editor 2
- [x] **D1.** *External Tools → Tabular Editor*. *Roles* → clic derecho → *Create New Role* → `Restricted_Epidemiologist`, *Model Permission* = Read.
- [x] **D2.** Seleccionar `dim_demographic[race_group]` → propiedades → *Object Level Security* → `Restricted_Epidemiologist` = **None**. Igual con `age_group`, **`demographic_level`** (repite los valores; sin ella el OLS no oculta nada) y la **tabla** `mart_revisions`.
- [x] **D3.** Rol `Restricted_State_Analyst`: Read + mismos filtros RLS de `State_Analyst` (en `dim_geography` y `dim_access`, propiedad *Row Level Security* de cada tabla) + las mismas 4 restricciones OLS. (RLS y OLS de un usuario deben estar en un mismo rol.)
- [x] **D4.** `Ctrl+S` en TE2 → volver a Desktop → *File → Save*.
- [x] **D5.** `git diff -- data_model` → en los `.tmdl` de roles aparece `metadataPermission: none` para las 3 columnas y la tabla, y el filtro en `Restricted_State_Analyst`. Si no, el OLS no se guardó: repetir D4.

**GATE 7.D** (*View as → Restricted_Epidemiologist*, Other user `ana@TENANT.onmicrosoft.com`; en `_QA` agregar visuales temporales):
- [x] `race_group` + `Cases Oregon` → **error** de campo inaccesible. Igual `age_group`, `demographic_level` y tarjeta `QA Revision Rows`.
- [x] `sex` + `Cases Oregon` (CHL) → **funciona**: 52.038 / 29.695.
- [x] `QA Demographic Rows` = **39**.
- [x] `Restricted_State_Analyst` + `ana@…` → `QA Geo Rows` = 38 **y** los 4 visuales restringidos fallan.
- [x] Combinación: *View as* con `State_Analyst` **y** `Restricted_Epidemiologist` a la vez → anotar textual lo que pasa (va a Limitaciones del README). **Resultado (2026-10-17, Desktop):** con `State_Analyst` + `Restricted_Epidemiologist` + `ana@…`, `QA Geo Rows` = 93 (el RLS se une: el rol sin filtro anula al de 38) y `QA Revision Rows` falla con "This field was deleted from the model and can't be used in this visual" (el OLS se mantiene). Limitación: no asignar a un mismo usuario un rol con RLS y otro solo con OLS; usar `Restricted_State_Analyst`.
- [x] **Si Desktop muestra datos donde debía fallar:** no aprobar; anotar "Desktop View as no aplica OLS" y 7.E pasa a ser la prueba obligatoria.
- [ ] Capturas `docs/img/ols_*.png`. Commit:
```
feat(security): dynamic RLS (state/county) and OLS roles with tested matrix
```

### 7.E — Prueba en el servicio (copia Import) — **PENDIENTE (sin tenant, 2026-10-17)**
DirectQuery a Postgres en el servicio requiere gateway: no se instala; se prueba con una copia.
- [ ] **E1.** Desde el `.pbip`: *File → Save as* → `.pbix` **fuera del repo** (ej. `C:\pbi_tmp\STI_ServiceTest.pbix`).
- [ ] **E2.** En la copia: los 2 hechos y las 6 dimensiones a **Import** → *Refresh*.
- [ ] **E3.** En la copia repetir GATE 6.A, E1 y F3: mismos números.
- [ ] **E4.** Publicar a un workspace **privado** (trial de Fabric o developer tenant M365). Nunca *Publish to web*.
- [ ] **E5.** Dominio real para `dim_access`:
  1. En el repo, editar `dbt/seeds/dim_access.csv`: reemplazar `TENANT.onmicrosoft.com` por el dominio real y los nombres por las cuentas de prueba reales (mantener las 4 filas y sus permisos).
  2. Commit + push: `chore(seed): real tenant accounts for service RLS test`.
  3. GitHub → Actions → *weekly_ingest* → **Run workflow** (corre `dbt seed`). Esperar verde.
  4. Neon SQL Editor: `select * from analytics_seeds.dim_access;` → 4 filas con el dominio real.
  5. En la copia: *Refresh* → republicar.
- [ ] **E6.** Servicio → modelo semántico → *Security* → asignar cada cuenta de prueba a su rol (`State_Analyst`, `County_Analyst`, `Restricted_State_Analyst`, `Admin`) → *Test as role*; luego entrar con cada cuenta en ventana privada.

**GATE 7.E:** filas 1, 2, 5, 6, 10 de la matriz y las pruebas OLS de 7.D con cuentas reales → mismos valores, y **el OLS bloquea** (aquí es obligatorio). Capturas `docs/img/service_rls_*.png`, `service_ols_*.png`. Después: borrar la copia del workspace y el `.pbix` local.

---

## Task 9.2 — Informe de 7 páginas
- [ ] *View → Themes → Browse for themes* → `theme\dark_accessible.json`.
- [ ] Colores fijos por enfermedad (*Format → Colors* en cada visual con leyenda): CHL `#56B4E9` · GON `#E69F00` · SYP_PS `#009E73` · SYP_EARLY `#F0E442` · SYP_CONG `#EF7B3A` · HIV `#CC79A7`. Mapas de tasa: rampa `#4F7CA3` → `#F0E442`.
- [ ] Cada visual: título, *Alt text* (*Format → General → Alt text*) con la lectura clave, y orden de tabulación (*View → Selection → Tab order*) izquierda→derecha, arriba→abajo.

| Pág. | Contenido | Verificación |
|---|---|---|
| 1 Resumen | Segmentadores enfermedad (CHL/GON/SYP_PS/SYP_CONG) y año. Tarjetas: `Cases NNDSS`, `Rate per 100k NNDSS`, `YoY % (MMWR aligned)`, `States in Outbreak`, `Reference Week`, `Latest Week With Data`. Línea semanal (`dim_mmwr_week[mmwr_week]`) con `Cases NNDSS` + P25/P50/P75 | GON·2025: 217.373 y 62,0. GON·2026 sem. 1–40: −2,3 % |
| 2 Mapa | Mapa de relleno por `state_name` con `Rate per 100k NNDSS`; tabla top 10 | 50 estados + DC; territorios sin población = sin dato, no 0 |
| 3 Ranking | Barras por estado: tasa y `Excess over P75` (semana de referencia) | CA GON 2024-W52 = 499 |
| 4 Corredor | Año en curso vs P25/P50/P75 para un estado; nota "corredor con 4 años (2022–2025)" | CA GON sem. 40: 657,75 · 810 · 885,75 |
| 5 Oregon condados | Barras/mapa por `county_name` con `Rate per 100k Oregon`; tarjetas `% Suppressed Cells` y `Share of Statewide Captured`; nota de supresión (<6 casos) | Multnomah CHL 2025: 3.376 y 414,7; supresión Geography 79,2 % |
| 6 Demografía | Un visual por corte (sexo, edad, raza), cada uno con filtro de visual `demographic_type` = ese corte; aviso "bloqueado para el rol restringido" | CHL sexo 52.038/29.695; edad = A14 |
| 7 Calidad | Tabla `mart_data_quality`; `Revisions Status`; `Latest Ingest (UTC)` | "No revisions recorded yet"; ingesta ≤ 8 días |

**GATE 9.2**
- [ ] Teclado: cada página recorrible solo con Tab/Shift+Tab/Enter.
- [ ] Daltonismo: capturas de págs. 1, 2, 5 por un simulador (protanopia/deuteranopia/tritanopia); enfermedades distinguibles por color y etiqueta.
- [ ] Alt text en 100 % de los visuales (*Selection pane*).
- [ ] Ninguna tasa sin "por 100.000, anualizada"; ninguna página de Oregon sin aviso de supresión.
- [ ] Ningún texto < 11 pt; nada depende solo del color.
- [ ] `_QA` oculta. Capturas `docs/img/page_1.png` … `page_7.png`. Commit:
```
feat(report): 7-page accessible report
```

---

## Troubleshooting
| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Timeout o "connection refused" en el primer intento | Neon suspendió el cómputo (5 min inactivo) | Reintentar a los 5–10 s |
| "We couldn't authenticate…" / `password authentication failed` | Pestaña Windows en vez de Database, o contraseña mal copiada | *File → Options and settings → Data source settings* → el host → *Edit Permissions* → *Edit* credenciales → Database |
| Error SSL / certificado | Conexión sin cifrar | En *Data source settings → Edit Permissions*, dejar marcado *Encrypt connections* |
| `permission denied for table …` | Tabla fuera de `analytics_marts` o GRANT perdido (p. ej. Prueba 3 sin restaurar) | Neon SQL Editor: `GRANT SELECT ON ALL TABLES IN SCHEMA analytics_marts TO pbi_reader;` |
| `canceling statement due to statement timeout` | Consulta DirectQuery > 60 s | Reducir el visual (filtrar año/enfermedad); no subir el timeout |
| Storage mode Dual deshabilitado | La tabla se cargó en Import | Borrarla y volver a cargarla en la pasada DirectQuery (6.A1) |
| No aparece *Save as .pbip* | Preview feature apagada | P5 y reiniciar Desktop |
| TE2/DAX Studio no aparecen en *External Tools* | Instalados con Desktop abierto | Cerrar y reabrir Desktop |
| Conteos mayores que las anclas | Ingesta nueva | Correr `qa_anchors.sql` y comparar contra eso |

## Anclas (carga 2026-10-14, verificadas 2026-10-15)
| Id | Ancla | Valor |
|---|---|---|
| A1 | Filas de las 12 tablas (orden de GATE 6.A) | 6 / 93 / 303 / 69 / 39 / 2.191 / 55.776 / 25.125 / 996 / 55.776 / 3 / 4 |
| A2 | Casos NNDSS por enfermedad | CHL 3.189.987 · GON 1.060.446 · SYP_PS 20.953 · SYP_CONG 24 |
| A3 | CA GON 2024-W52 | 499 |
| A4 | Tasa anualizada: CA CHL 2024 · nacional GON 2025 | 259,434 · 62,036 |
| A5 | GON 2026 sem. 1–40: casos · LY MMWR · YoY · SPLY | 163.363 · 167.261 · −2,33 % · 164.428 |
| A5b | GON 2026-W40: casos · LY MMWR · SPLY | 4.627 · 4.830 · vacío |
| A6 | Corredor CA GON sem. 40: P25 · P50 · P75 · casos · exceso | 657,75 · 810 · 885,75 · 1 · 0 |
| A7 | Estados en brote GON: W40 · W38 | 11 · 15 |
| A8 | Semana de referencia · última | 202638 · 202640 |
| A9 | Oregon CHL por corte | Age 81.886 · Geography 80.587 · Race alone 92.237 · Race primary 81.803 · Sex 81.733 · Statewide 82.066 |
| A9b | Oregon CHL por sexo | Female 52.038 · Male 29.695 |
| A10 | Multnomah CHL: 2026-M01 · 2025 · total · tasa 2025 | 294 · 3.376 · 23.787 · 414,658 |
| A11 | % suprimido por corte | Geography 79,2 · Statewide 0,0 · Sex 60,7 · Age 68,8 · Race alone 58,3 · Race primary 65,9 |
| A12 | Cobertura condados/estatal | HIV 376/1.291 (29,1 %) · CHL 80.587/82.066 (98,2 %) |
| A13 | NNDSS GON 2025: OR · CA · nacional | 4.073 · 31.479 · 217.373 |
| A14 | Oregon CHL por edad | 20–29 41.900 · 10–19 16.587 · 30–39 15.456 · 40–49 5.457 · 50–59 1.991 · 60–69 485 · <5 10 |

## Rediseño del informe (2026-10-18) — validar en Desktop
El layout de ambos informes (ES y EN) lo genera `scripts/build_report_layout.py` (grilla de 8 px, navegación superior, filtros sincronizados, leyenda de colores, pie con fuentes) y lo comprueba `tests/test_report_layout.py`. Para cambiar el diseño se edita el script y se vuelve a correr; no editar posiciones a mano.

Pasos para validar (cerrar Desktop antes de `git pull`):
- [ ] Abrir `STI_Surveillance_Model.pbip` y `STI_Surveillance_Model_EN.pbip`: sin errores de carga. Si Desktop rechaza algún botón de navegación o el formato de color, anotar el mensaje exacto.
- [ ] Los 7 botones de la cabecera navegan a su página (Ctrl+clic en Desktop) y el de la página actual está resaltado.
- [ ] Cambiar Enfermedad y Año en una página: se sincroniza en las demás (Oregon tiene su propio grupo de año).
- [ ] Las barras toman el color de la enfermedad elegida (medida `Disease Color`); la línea de Resumen/Corredor queda en color neutro porque Power BI no admite color por medida en series de línea.
- [ ] Las cifras de las tarjetas no cambiaron (A3, A4, A9, A10). Tomar `page_1…7`.

Paleta de enfermedades (validador del skill `dataviz`, modo oscuro): contraste y separación para daltónicos OK; falla el piso de visión normal entre `#CC79A7` y `#EF7B3A` (ΔE 14,9 frente a 15) y la banda de luminosidad. Se mantienen los colores del plan original porque la selección es única (nunca van juntos en un gráfico) y cada uno lleva etiqueta.
