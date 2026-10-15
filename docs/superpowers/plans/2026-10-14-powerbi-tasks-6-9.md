# STI Surveillance — Tasks 6 a 9: modelo Power BI, seguridad, MCP e informe

> **Para quien ejecute:** REQUIRED SUB-SKILL: superpowers:executing-plans (Native). Los pasos marcados **[CLAUDE]** los ejecuta el agente con TDD; los marcados **[HUMANO]** los hace una persona en Power BI Desktop (Windows) y cada uno termina en un **GATE** con valores esperados. No se pasa al siguiente GATE sin que el anterior esté completo. Las casillas `- [ ]` son el registro de avance.

**Goal:** Construir el modelo semántico compuesto de Power BI sobre `analytics_marts`, con RLS/OLS probadas, el MCP verificado en un cliente real y el informe accesible de 7 páginas, comprobando cada capa contra cifras calculadas en SQL.

**Architecture:** dbt expone dos hechos (`fct_nndss_weekly` semanal por estado, `fct_oregon_monthly` mensual por corte demográfico) y dimensiones compartidas. Power BI los une en un modelo compuesto: hechos en DirectQuery, dimensiones en Dual, una agregación Import (`agg_weekly_national`) y tablas Import auxiliares. La seguridad vive en el modelo (RLS sobre `dim_geography`, OLS sobre columnas demográficas). Antes de tocar Desktop hay que corregir cuatro defectos del modelo dbt que el análisis de datos de este plan encontró (Task 6.0).

**Tech Stack:** dbt-core 1.12.6 + dbt-postgres 1.11.0, Neon Postgres, Power BI Desktop (Windows), Tabular Editor 2, DAX Studio, MCP Python SDK 2.3.

**Spec:** `docs/superpowers/specs/2026-10-14-sti-surveillance-design.md` y `README.md` (estado real). Este plan reemplaza los Tasks 6–9 de `docs/superpowers/plans/2026-10-14-sti-surveillance.md`; los Tasks 0–5 están completos.

## Context

El pipeline (ingesta semanal → dbt → marts) está en verde y el MCP funciona. Falta todo lo que consume Power BI. Al preparar este plan se perfiló la base y se leyó la documentación de Power BI; eso destapó problemas que habrían producido números incorrectos en el informe sin dar ningún error:

1. **Ceros que parecían datos faltantes.** En NNDSS, `m1 = NULL` con `m1_flag = '-'` significa *sin casos reportados* (el CDC lo define así), no dato ausente. Hoy `fct_nndss_weekly.cases_week` deja NULL 33.083 de 55.776 filas, aunque solo 213 son realmente "no disponible" (`U`: Maryland y Ohio). Las sumas no cambian, pero los percentiles del corredor endémico ignorarían los ceros y saldrían inflados.
2. **Doble conteo en Oregon.** El total estatal vive dentro del corte `Geography` con `geo_key='OR'` y se sumaría con los 37 condados (82.066 vs 80.587 en clamidia).
3. **Fuga por OLS.** `dim_demographic[demographic_level]` repite exactamente los valores de `age_group` y `race_group`. Ocultar solo estas dos columnas deja los mismos datos visibles.
4. **Denominadores.** La población es anual y los períodos de Oregon duran 28 o 35 días: dividir casos de varios años entre una sola población, o sumar poblaciones mensuales, da tasas erróneas. El plan usa **persona-años**.

Además: Power BI Desktop, Tabular Editor 2 y DAX Studio solo corren en **Windows**; la máquina de desarrollo actual es Linux.

## Global Constraints
- El agente **nunca** ejecuta `git commit`, `git push` ni `git init` (CLAUDE.md del usuario). Cada paso "Commit" entrega el mensaje en un bloque, **sin** líneas de atribución a Claude.
- Los archivos de Power BI (`.pbip`, TMDL) los commitea la persona que trabaja en Windows. Nunca se commitea un `.pbix` (contiene los datos).
- Sin *Publish to web*. La prueba de RLS/OLS en el servicio usa una copia Import en un workspace privado.
- Las credenciales de Power BI son de un rol de solo lectura (`pbi_reader`), nunca del dueño de la base. Contraseñas solo en `.env` y en el gestor de credenciales de Desktop.
- Celdas de Oregon con menos de 6 casos: `NULL`, nunca imputadas. Tasas solo sobre celdas visibles.
- Todo valor esperado de este plan corresponde a la carga del **2026-10-14** (NNDSS hasta 2026-W40, Oregon hasta 2026-M09). Cada semana la ingesta añade datos: antes de dar un GATE por fallido, regenerar el valor con `sql/qa_anchors.sql` (Task 6.0) y comparar contra ese. Los valores históricos (por ejemplo 2024-W52) solo cambian si el CDC revisa esa semana.

## Review Focus
1. **Cero vs no disponible (NNDSS).** `-` = cero casos; solo `U` = NULL. Esperado: corredor endémico con ceros incluidos. Test: `nndss_nulls_only_when_u` (6.0) y ancla A6.
2. **Total estatal de Oregon dentro del corte de condados.** Esperado: corte propio `Statewide`; `Geography` solo condados. Test: `oregon_statewide_not_in_geography` (6.0) y ancla A9.
3. **OLS que no oculta lo que dice ocultar.** Esperado: `demographic_level` también restringida; las 3 columnas fallan en un visual bajo el rol restringido. Test: GATE 7.D.
4. **La tabla de permisos expuesta y el usuario desconocido.** Esperado: `dim_access` oculta y filtrada a las filas propias; un UPN que no está en la tabla no ve ninguna fila. Test: GATE 7.C, casos `nadie@`.
5. **Tasas con denominador equivocado o con la semana 53 / semana en curso.** Esperado: persona-años, tasa anualizada, 2025 con 53 semanas, "semana de referencia" = última completa. Test: GATE 6.F con anclas A4 y A10.

## Valores de referencia (anclas)
Carga del 2026-10-14. `sql/qa_anchors.sql` (6.0) los regenera todos.

| Id | Ancla | Valor |
|---|---|---|
| A1 | Filas: `dim_disease` / `dim_geography` / `dim_mmwr_week` / `dim_epi_month` / `dim_demographic` / `dim_date` / `fct_nndss_weekly` / `fct_oregon_monthly` / `agg_weekly_national` / `mart_revisions` / `mart_data_quality` / `dim_access` | 6 / 93 / 303 / 69 / 39 / 2.191 / 55.776 / 25.125 / 996 / 55.776 / 3 / 4 |
| A2 | Casos NNDSS totales por enfermedad | CHL 3.189.987 · GON 1.060.446 · SYP_PS 20.953 · SYP_CONG 24 · HIV y SYP_EARLY sin filas |
| A3 | CA, GON, 2024-W52 | 499 |
| A4 | Tasa anualizada por 100k: CA CHL 2024 · nacional GON 2025 | 259,434 · 62,036 |
| A5 | GON nacional 2026 semanas 1–40: casos · LY alineado MMWR · YoY · LY SAMEPERIODLASTYEAR | 163.363 · 167.261 · −2,33 % · 164.428 |
| A5b | GON nacional 2026-W40 sola: casos · LY MMWR · YoY · SAMEPERIODLASTYEAR | 4.627 · 4.830 · −4,20 % · vacío |
| A6 | Corredor CA GON semana 40 (2022–2025): P25 · P50 · P75 · casos 2026-W40 · exceso | 657,75 · 810 · 885,75 · 1 · 0 |
| A7 | Estados en brote GON: 2026-W40 · 2026-W38 | 11 · 15 |
| A8 | Semana de referencia · última semana con datos | 202638 · 202640 |
| A9 | Oregon CHL por corte: Age Group · Geography · Race (alone) · Race (primary) · Sex · Statewide | 81.886 · 80.587 · 92.237 · 81.803 · 81.733 · 82.066 |
| A9b | Oregon CHL por sexo | Female 52.038 · Male 29.695 · Nonbinary y Unknown vacíos |
| A10 | Multnomah CHL: 2026-M01 · año 2025 · período completo · tasa 2025 por 100k | 294 · 3.376 · 23.787 · 414,658 |
| A11 | % celdas suprimidas por corte (todas las enfermedades) | Geography 79,2 · Statewide 0,0 · Sex 60,7 · Age Group 68,8 · Race (alone) 58,3 · Race (primary) 65,9 |
| A12 | Oregon: cobertura de condados visibles sobre el total estatal | HIV 376 de 1.291 (29,1 %) · CHL 80.587 de 82.066 (98,2 %) |
| A13 | Casos NNDSS GON 2025: OR · CA · nacional | 4.073 · 31.479 · 217.373 |
| A14 | Oregon CHL por edad (solo visible sin OLS) | 20–29: 41.900 · 10–19: 16.587 · 30–39: 15.456 · 40–49: 5.457 · 50–59: 1.991 · 60–69: 485 · <5: 10 |
| A15 | Vista del MCP `mcp_oregon_county_monthly` | 12.395 filas · CHL 80.587 |

Nota: la semana 2025-W1 empieza el 2024-12-29, por eso SAMEPERIODLASTYEAR (164.428) difiere de la comparación alineada (167.261) exactamente en los 2.833 casos de esa semana.

## File Structure
```
sti-surveillance/
├── .gitignore                               # modificar: *.pbix, *.pbit
├── .gitattributes                           # crear: normaliza finales de línea del TMDL
├── sql/pbi_reader_role.sql                  # crear: rol de solo lectura para Power BI
├── sql/qa_anchors.sql                       # crear: regenera todas las anclas
├── dbt/
│   ├── dbt_project.yml                      # modificar: hooks de permisos de pbi_reader
│   ├── seeds/dim_access.csv                 # modificar: añadir usuario sofia
│   ├── models/staging/stg_nndss_weekly.sql  # modificar: ceros vs 'U'
│   ├── models/staging/stg_oregon_monthly.sql# modificar: corte 'Statewide'
│   ├── models/staging/_sources.yml          # modificar: accepted_values
│   ├── models/marts/dim_date.sql            # crear
│   ├── models/marts/dim_epi_month.sql       # modificar: period_days
│   ├── models/marts/fct_nndss_weekly.sql    # modificar: week_start_date
│   ├── models/marts/agg_weekly_national.sql # modificar: grano semana × enfermedad
│   ├── models/marts/_marts.yml              # modificar: tests nuevos
│   └── tests/{nndss_nulls_only_when_u, oregon_statewide_not_in_geography, dim_date_full_years, agg_unique_grain}.sql
├── data_model/STI_Surveillance_Model.pbip   # [HUMANO] + .SemanticModel/ (TMDL) + .Report/
├── theme/dark_accessible.json               # Task 9
├── docs/img/                                # capturas
└── README.md, README_es.md                  # Task 9: estado final
```

---

## Task 6.0 [CLAUDE]: Correcciones de dbt que Power BI necesita

**Files:** ver File Structure. **Produces:** las columnas y tablas que consumen los GATES de Power BI: `fct_nndss_weekly.week_start_date`, `dim_date`, `dim_epi_month.period_days`, corte `Statewide`, `agg_weekly_national(epi_week_key, disease_key, cases_week)`.

Cargar el entorno en cada comando con:
```bash
cd ~/Documents/proyectos/sti-surveillance && while IFS='=' read -r k v || [[ -n "$k" ]]; do [[ -z "$k" || "$k" == \#* ]] && continue; export "$k=$v"; done < .env && cd dbt
```

- [ ] **Step 1: Escribir los tests (RED).** Crear:

`dbt/tests/nndss_nulls_only_when_u.sql`
```sql
-- '-' del CDC = cero casos reportados; solo 'U' (no disponible) puede dejar cases_week en NULL
select f.epi_week_key, f.disease_key, f.geo_key
from {{ ref('fct_nndss_weekly') }} f
where f.cases_week is null
  and not exists (
    select 1
    from {{ source('raw', 'nndss_weekly') }} r
    join {{ ref('state_codes') }} c on c.state_name_upper = upper(r.location1)
    join {{ ref('disease_map') }} m on m.source = 'nndss' and m.source_name = r.label
    where c.state_code = f.geo_key and m.disease_key = f.disease_key
      and r.year * 100 + r.week = f.epi_week_key and r.m1_flag = 'U'
  )
```
`dbt/tests/oregon_statewide_not_in_geography.sql`
```sql
-- el total estatal vive en el corte 'Statewide'; en 'Geography' solo puede haber condados
select f.fact_id
from {{ ref('fct_oregon_monthly') }} f
join {{ ref('dim_demographic') }} d using (demographic_key)
where d.demographic_type = 'Geography' and f.geo_key = 'OR'
```
`dbt/tests/dim_date_full_years.sql`
```sql
-- dim_date debe cubrir años completos: del 1-ene-2021 al 31-dic del año actual, sin huecos
select mn, mx, n
from (select min(date) mn, max(date) mx, count(*) n from {{ ref('dim_date') }}) t
where mn <> date '2021-01-01'
   or mx <> make_date(extract(year from current_date)::int, 12, 31)
   or n <> mx - mn + 1
```
`dbt/tests/agg_unique_grain.sql`
```sql
select epi_week_key, disease_key from {{ ref('agg_weekly_national') }}
group by 1, 2 having count(*) > 1
```
En `dbt/models/marts/_marts.yml` añadir: a `dim_demographic.demographic_type` el valor `'Statewide'` en `accepted_values`; a `dim_epi_month` la columna `period_days` con `accepted_values: {arguments: {values: [28, 35], quote: false}}`; a `fct_nndss_weekly` las columnas `week_start_date` con `not_null` y `relationships: {arguments: {to: ref('dim_date'), field: date}}`; y un bloque `- name: dim_date` con `date: [unique, not_null]`. En `dbt/models/staging/_sources.yml` añadir `'Statewide'` a la lista de `accepted_values` de `stg_oregon_monthly.demographic_type`.

- [ ] **Step 2: Confirmar RED.**
  Run: `dbt test --select nndss_nulls_only_when_u oregon_statewide_not_in_geography dim_date_full_years --profiles-dir .`
  Expected: `nndss_nulls_only_when_u` FAIL (más de 30.000 filas), `oregon_statewide_not_in_geography` FAIL (335 filas), `dim_date_full_years` ERROR (el modelo `dim_date` no existe). Si alguno pasa, el test no prueba nada: corregirlo antes de seguir.

- [ ] **Step 3: Implementar.**

`dbt/models/staging/stg_nndss_weekly.sql`: reemplazar las líneas de `cases_week` e `is_flagged`:
```sql
    -- '-' = el CDC recibió la jurisdicción sin casos => 0. Solo 'U' (no disponible) queda NULL.
    sum(coalesce(m1, case when m1_flag = '-' then 0 end)) as cases_week,
```
```sql
    bool_or(m1 is null and coalesce(m1_flag, '') <> '-') as is_flagged
```
`dbt/models/staging/stg_oregon_monthly.sql`: reemplazar `demographic_type` y `demographic_level`:
```sql
    case when demographic = 'Geography' and geo_unit = 'state' then 'Statewide' else demographic end as demographic_type,
    case when demographic = 'Geography' then 'All' else demographic_level end as demographic_level,
```
(`county_name` queda igual: `case when geo_unit = 'county' then demographic_level end`.)

`dbt/models/marts/dim_epi_month.sql`: añadir antes de `month_label`:
```sql
       (max(report_period_end) - min(report_period_start) + 1)::int as period_days,
```
`dbt/models/marts/dim_date.sql` (nuevo):
```sql
select d::date as date,
       extract(year from d)::int as year,
       extract(month from d)::int as month_number,
       to_char(d, 'Mon') as month_name,
       to_char(d, 'YYYY-MM') as year_month,
       extract(quarter from d)::int as quarter
from generate_series('2021-01-01'::timestamp,
                     make_date(extract(year from current_date)::int, 12, 31)::timestamp,
                     interval '1 day') d
```
`dbt/models/marts/fct_nndss_weekly.sql`: añadir `w.week_start_date,` tras `s.epi_week_key,` y este join tras el de `disease_map`:
```sql
join {{ ref('dim_mmwr_week') }} w on w.epi_week_key = s.epi_week_key
```
`dbt/models/marts/agg_weekly_national.sql` (reemplazo completo):
```sql
select epi_week_key, disease_key, sum(cases_week) as cases_week
from {{ ref('fct_nndss_weekly') }}
group by 1, 2
```
`dbt/seeds/dim_access.csv`: añadir la fila `sofia@TENANT.onmicrosoft.com,OR,*`.
`dbt/models/marts/mart_data_quality.sql`: en la fila de `nndss` reemplazar `avg((m1 is null)::int)` por `avg((m1_flag = 'U')::int)`.
`.gitignore`: añadir `*.pbix` y `*.pbit`. `.gitattributes` (nuevo): `* text=auto` y `*.tmdl text eol=lf` y `*.pbix binary`.

- [ ] **Step 4: Confirmar GREEN.**
  Run: `dbt seed --profiles-dir . && dbt build --profiles-dir .`
  Expected: `Done. PASS=… ERROR=0`, y los 4 tests nuevos en PASS.

- [ ] **Step 5: Verificar números (no basta con que pasen los tests).** Crear `sql/qa_anchors.sql` con las consultas A1–A15 (ver Task 6.0b) y correrlas.
  Expected (comparar con la tabla de anclas): conteos A1; `cases_week IS NULL` = **213** y `is_flagged` verdadero = **213**; totales A2 sin cambio (CHL 3.189.987); `fct_nndss_weekly` sigue en 55.776 filas; `agg_weekly_national` = 996 filas con suma 4.271.410; `dim_demographic` = 39 filas con tipos `Statewide`(1), `Geography`(1), `Sex`(4), `Age Group`(11), `Race (alone…)`(10), `Race (primary…)`(12); `mcp_oregon_county_monthly` sigue en **12.395** filas y CHL **80.587**; `dim_epi_month.period_days` solo 28 (45 meses) y 35 (24 meses).

- [ ] **Step 6: Regenerar documentación y CI.** Run: `dbt docs generate --profiles-dir .` (sin errores). El workflow no cambia. Verificar `git status` sin `.env`, `target/` ni `.pbix`.

- [ ] **Step 7: Mensaje de commit (lo corre el usuario):**
```
fix(dbt): zero-fill NNDSS '-' reports, split Oregon statewide cut, add dim_date and period_days
```

### Task 6.0b [CLAUDE]: `sql/qa_anchors.sql`
Un solo archivo; cada consulta lleva como comentario su ancla. Contenido exacto:
```sql
-- A1 conteos
select 'dim_disease' t, count(*) n from analytics_marts.dim_disease union all
select 'dim_geography', count(*) from analytics_marts.dim_geography union all
select 'dim_mmwr_week', count(*) from analytics_marts.dim_mmwr_week union all
select 'dim_epi_month', count(*) from analytics_marts.dim_epi_month union all
select 'dim_demographic', count(*) from analytics_marts.dim_demographic union all
select 'dim_date', count(*) from analytics_marts.dim_date union all
select 'fct_nndss_weekly', count(*) from analytics_marts.fct_nndss_weekly union all
select 'fct_oregon_monthly', count(*) from analytics_marts.fct_oregon_monthly union all
select 'agg_weekly_national', count(*) from analytics_marts.agg_weekly_national union all
select 'mart_revisions', count(*) from analytics_marts.mart_revisions union all
select 'mart_data_quality', count(*) from analytics_marts.mart_data_quality union all
select 'dim_access', count(*) from analytics_seeds.dim_access;

-- A2 casos NNDSS por enfermedad
select disease_key, sum(cases_week) from analytics_marts.fct_nndss_weekly group by 1 order by 1;

-- A3 CA GON 2024-W52
select cases_week from analytics_marts.fct_nndss_weekly where geo_key='CA' and disease_key='GON' and epi_week_key=202452;

-- A4 tasa anualizada (persona-años = suma de poblaciones semanales / (365,25/7))
select round(sum(cases_week) filter (where population>0)*100000
       / (sum(population) filter (where population>0 and cases_week is not null)/(365.25/7)), 3)
from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
where f.geo_key='CA' and f.disease_key='CHL' and w.mmwr_year=2024;
select round(sum(cases_week) filter (where population>0)*100000
       / (sum(population) filter (where population>0 and cases_week is not null)/(365.25/7)), 3)
from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
where f.disease_key='GON' and w.mmwr_year=2025;

-- A5 interanual GON nacional
select sum(cases_week) filter (where w.mmwr_year=2026 and w.mmwr_week<=40) y26,
       sum(cases_week) filter (where w.mmwr_year=2025 and w.mmwr_week<=40) ly_mmwr,
       sum(cases_week) filter (where w.week_start_date between '2025-01-01' and '2025-10-04') ly_sply,
       sum(cases_week) filter (where w.epi_week_key=202640) w40_26,
       sum(cases_week) filter (where w.epi_week_key=202540) w40_25
from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
where f.disease_key='GON';

-- A6 corredor CA GON semana 40 (años 2021-2025; los años sin datos no cuentan)
select percentile_cont(0.25) within group (order by cases_week) p25,
       percentile_cont(0.5)  within group (order by cases_week) p50,
       percentile_cont(0.75) within group (order by cases_week) p75
from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
where f.geo_key='CA' and f.disease_key='GON' and w.mmwr_week=40 and w.mmwr_year between 2021 and 2025;

-- A7 estados en brote (cambiar 40 y 202640 por 38 y 202638 para la semana de referencia)
with p as (select f.geo_key, percentile_cont(0.75) within group (order by f.cases_week) p75
           from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
           where f.disease_key='GON' and w.mmwr_week=40 and w.mmwr_year between 2021 and 2025 group by 1)
select count(*) filter (where f.cases_week > p.p75)
from analytics_marts.fct_nndss_weekly f join p using (geo_key)
where f.disease_key='GON' and f.epi_week_key=202640;

-- A8 semana de referencia y última semana
select (select epi_week_key from analytics_marts.dim_mmwr_week where is_reference_week),
       (select max(epi_week_key) from analytics_marts.fct_nndss_weekly);

-- A9 Oregon CHL por corte
select d.demographic_type, sum(f.cases)
from analytics_marts.fct_oregon_monthly f join analytics_marts.dim_demographic d using (demographic_key)
where f.disease_key='CHL' group by 1 order by 1;

-- A10 Multnomah CHL (2026-M01, 2025, completo) y tasa 2025
select sum(f.cases) filter (where f.epi_month_key=202601),
       sum(f.cases) filter (where m.mmwr_year=2025), sum(f.cases)
from analytics_marts.fct_oregon_monthly f
join analytics_marts.dim_demographic d using (demographic_key)
join analytics_marts.dim_epi_month m using (epi_month_key)
where f.geo_key='OR|Multnomah County' and f.disease_key='CHL' and d.demographic_type='Geography';
select round(sum(f.cases)*100000/sum(f.population*m.period_days/365.25), 3)
from analytics_marts.fct_oregon_monthly f
join analytics_marts.dim_demographic d using (demographic_key)
join analytics_marts.dim_epi_month m using (epi_month_key)
where f.geo_key='OR|Multnomah County' and f.disease_key='CHL' and d.demographic_type='Geography'
  and m.mmwr_year=2025 and not f.is_masked and f.population>0 and f.cases is not null;

-- A11 % suprimido por corte
select d.demographic_type, round(100*avg(f.is_masked::int), 1)
from analytics_marts.fct_oregon_monthly f join analytics_marts.dim_demographic d using (demographic_key)
group by 1 order by 1;

-- A12 cobertura de condados
select f.disease_key,
       sum(f.cases) filter (where d.demographic_type='Geography') condados,
       sum(f.cases) filter (where d.demographic_type='Statewide') estatal
from analytics_marts.fct_oregon_monthly f join analytics_marts.dim_demographic d using (demographic_key)
where f.disease_key in ('CHL','HIV') group by 1 order by 1;

-- A13 NNDSS GON 2025 por estado
select f.geo_key, sum(f.cases_week)
from analytics_marts.fct_nndss_weekly f join analytics_marts.dim_mmwr_week w using (epi_week_key)
where f.disease_key='GON' and w.mmwr_year=2025 and f.geo_key in ('OR','CA') group by 1 order by 1;

-- A14 Oregon CHL por edad
select d.demographic_level, sum(f.cases)
from analytics_marts.fct_oregon_monthly f join analytics_marts.dim_demographic d using (demographic_key)
where f.disease_key='CHL' and d.demographic_type='Age Group' group by 1 order by 1;

-- A15 vista del MCP
select count(*), sum(cases) filter (where disease_key='CHL') from analytics_marts.mcp_oregon_county_monthly;
```
- [ ] Ejecutarlo y comparar cada resultado con la tabla de anclas; cualquier diferencia se resuelve antes de seguir (puede ser un dato nuevo, ver Global Constraints).

---

## Task 6.1 [CLAUDE + visto bueno del usuario]: Rol `pbi_reader`

Crea un rol en la base del usuario: pedir confirmación antes de ejecutar.

**Files:** `sql/pbi_reader_role.sql` (nuevo), `dbt/dbt_project.yml` (hooks), `.env` (no se commitea).

- [ ] **Step 1:** `sql/pbi_reader_role.sql`:
```sql
-- psql -v pw="'...'" -f sql/pbi_reader_role.sql   (los GRANT los reaplica un hook de dbt)
CREATE ROLE pbi_reader LOGIN PASSWORD :pw;
ALTER ROLE pbi_reader SET default_transaction_read_only = on;
ALTER ROLE pbi_reader SET statement_timeout = '60s';
```
- [ ] **Step 2:** Crear el rol con una contraseña generada (`secrets.token_urlsafe(24)`) sin imprimirla; guardar en `.env` como `PBI_DB_USER=pbi_reader` y `PBI_DB_PASSWORD=...`.
- [ ] **Step 3:** Añadir a `on-run-end` en `dbt/dbt_project.yml` (después de crear el rol, si no el build falla):
```yaml
  - "grant usage on schema analytics_marts, analytics_seeds to pbi_reader"
  - "grant select on all tables in schema analytics_marts to pbi_reader"
  - "grant select on analytics_seeds.dim_access to pbi_reader"
```
- [ ] **Step 4: Verificar** con una conexión como `pbi_reader` (script Python, sin imprimir secretos):
  Expected: `select count(*) from analytics_marts.fct_nndss_weekly` → 55.776 · `select count(*) from analytics_seeds.dim_access` → 4 · `select 1 from raw.nndss_weekly limit 1` → `permission denied for schema raw` · `create table analytics_marts.x(a int)` → `cannot execute CREATE TABLE in a read-only transaction`.
- [ ] **Step 5:** `dbt build` otra vez (aplica los hooks) y confirmar `ERROR=0`. Mensaje de commit: `feat(db): read-only pbi_reader role with dbt-managed grants`.
- [ ] **Step 6:** Entregar a la persona de Windows el host, base, usuario `pbi_reader` y la contraseña **por un canal seguro** (no por el chat ni por git).

**GATE 6.0–6.1** (todo debe estar en ✔ antes de que alguien abra Power BI): tests nuevos en PASS · conteos A1 · 213 NULL reales · A15 sin cambio · `pbi_reader` verificado · `git status` limpio de secretos.

---

## Task 6 [HUMANO]: Modelo semántico en Power BI Desktop

### GATE P — Entorno (antes de empezar)
- [ ] **P1.** Equipo **Windows 10/11** con Power BI Desktop actualizado, [Tabular Editor 2](https://github.com/TabularEditor/TabularEditor/releases) (gratis, 2.x), [DAX Studio](https://daxstudio.org) (gratis) y Git. Linux/macOS no sirven.
- [ ] **P2.** `git clone` del repo (privado) en Windows. Abrir Neon → SQL Editor (para correr `sql/qa_anchors.sql`).
- [ ] **P3.** Desktop → *File → Options and settings → Options → Current File → Data Load* → **desmarcar** "Autodetect new relationships after data is loaded". Motivo: relaciones inventadas por Desktop arruinan el modelo.
- [ ] **P4.** *File → Options → Global → Security → Data Extensions* sin cambios. *Options → Preview features*: activar "Power BI Project (.pbip) save option" y "TMDL view" **solo si aparecen** como opciones; si Desktop ya los trae activos, no hay nada que hacer.
- [ ] **P5.** Conexión: probar que `pbi_reader` entra a Neon desde esa máquina (se hace en 6.A; si falla, ver Troubleshooting).

**Expected GATE P:** las 3 herramientas abren; `sql/qa_anchors.sql` corre en Neon y reproduce la tabla de anclas.

### Task 6.A — Cargar los datos (tres pasadas)
Desktop no permite cambiar una tabla Import a DirectQuery, y solo una tabla que *nació* DirectQuery puede pasar a Dual. Por eso se carga en dos pasadas con modos distintos.

- [ ] **A1. Pasada DirectQuery.** *Home → Get data → PostgreSQL database*. Server: el host de Neon (sin `https://`; ejemplo `ep-xxxx.us-east-2.aws.neon.tech`). Database: el nombre de la base. **Data Connectivity mode: DirectQuery**. OK → pestaña *Database* → usuario `pbi_reader` y su contraseña → Connect. En el Navigator abrir el esquema `analytics_marts` y marcar **exactamente estas 8 tablas**: `fct_nndss_weekly`, `fct_oregon_monthly`, `dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, `dim_date`. Click **Load**.
- [ ] **A2. Pasada Import.** *Get data → PostgreSQL database* de nuevo (misma conexión) pero **Import**. Marcar `agg_weekly_national`, `mart_revisions`, `mart_data_quality` (esquema `analytics_marts`) y `dim_access` (esquema `analytics_seeds`). Load.
- [ ] **A3. Nombres.** *Home → Transform data*. En el panel Queries, clic derecho → *Rename* para que cada tabla quede **exactamente** con el nombre de la columna "Tabla" de A1 (sin prefijo de esquema; por ejemplo `analytics_marts fct_nndss_weekly` → `fct_nndss_weekly`). *Close & Apply*.
- [ ] **A4. Tipos de datos** (panel Data o Model view, seleccionar la columna): `epi_week_key`, `epi_month_key`, `mmwr_year`, `mmwr_week`, `month_number`, `year`, `quarter`, `period_days` → *Whole number*; `week_start_date`, `week_end_date`, `period_start`, `period_end`, `date` → *Date* (no Date/Time); `cases_week`, `cases`, `population` → *Decimal number* o *Whole number* según vengan; `is_masked`, `is_flagged`, `is_reference_week`, `comparable_across_sources` → *True/False*; `last_ingested_at` → *Date/Time*; resto → *Text*.
- [ ] **A5. Guardar** como proyecto: *File → Save as → Power BI Project (*.pbip)* en `<repo>/data_model/STI_Surveillance_Model.pbip`. (Si no aparece la opción, ver P4.)

**GATE 6.A — Conteos.** *DAX query view* (ícono de la barra izquierda), pegar y *Run*:
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
**Expected (A1):** 6 · 93 · 303 · 69 · 39 · 2.191 · 55.776 · 25.125 · 996 · 55.776 · 3 · 4. Las tres que crecen con el tiempo (`dim_mmwr_week`, `fct_*`) se comparan contra `sql/qa_anchors.sql` A1, no contra la tabla fija.
- [ ] Los 12 conteos coinciden con el SQL · [ ] los 12 nombres de tabla son exactos · [ ] no hay mensajes de error en la query · [ ] captura `docs/img/gate_6A.png`.

### Task 6.B — Modos de almacenamiento
- [ ] **B1.** *Model view*. Para cada una de las 6 dimensiones (`dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, `dim_date`): seleccionar la tabla → panel *Properties* → *Advanced* → **Storage mode = Dual** → aceptar el aviso.
- [ ] **B2.** Dejar `fct_nndss_weekly` y `fct_oregon_monthly` en **DirectQuery**, y `agg_weekly_national`, `mart_revisions`, `mart_data_quality`, `dim_access` en **Import**. No tocar nada más.

**GATE 6.B.** En *Model view* pasar el cursor sobre el encabezado de cada tabla: el icono/tooltip muestra el modo. **Expected:** 2 DirectQuery · 6 Dual · 4 Import. Confirmación textual: clic derecho en una tabla → *Script TMDL to → Script tab* (TMDL view) y buscar la línea `mode:` dentro de `partition` → `directQuery` / `dual` / `import` según la tabla. 
- [ ] 12/12 tablas en el modo esperado · [ ] captura `docs/img/gate_6B.png`.

### Task 6.C — Relaciones (13 en total)
En *Model view → Manage relationships → New* (o arrastrar columna sobre columna). Para **todas**: Cardinality *Many to one (*:1)*, Cross-filter direction *Single*, *Make this relationship active* marcado, *Assume referential integrity* **desmarcado**. Formato `tabla_muchos[columna] → tabla_uno[columna]`:

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

Sin relaciones: `dim_access` y `mart_data_quality`.

**GATE 6.C.**
- [ ] *Manage relationships* lista **exactamente 13**, todas *Many to one*, *Single*, activas. Ninguna relación con un ícono de advertencia "limitada" (*limited relationship*) — si aparece alguna, anotar cuál y revisar que ambas tablas estén en los modos del GATE 6.B.
- [ ] Prueba funcional (DAX query view):
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_disease[disease_key], "casos", SUM ( fct_nndss_weekly[cases_week] ) )
ORDER BY dim_disease[disease_key]
```
  **Expected (A2):** CHL 3.189.987 · GON 1.060.446 · SYP_CONG 24 · SYP_PS 20.953 (HIV y SYP_EARLY no aparecen: no tienen filas NNDSS).
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "n", COUNTROWS ( fct_oregon_monthly ) )
ORDER BY dim_demographic[demographic_type]
```
  **Expected:** 6 tipos (`Age Group`, `Geography`, `Race (alone or in combination)`, `Race (primary/least common race)`, `Sex`, `Statewide`); la suma de `n` = 25.125. Si falta alguno, la relación 8 está mal.
- [ ] captura de la vista de relaciones `docs/img/gate_6C.png`.

### Task 6.D — Tabla de fechas, orden y limpieza
- [ ] **D1.** Seleccionar `dim_date` → *Table tools → Mark as date table → Date column = `date`*. **Expected:** sin error. *Si la opción está deshabilitada* (tabla Dual), anotar el hallazgo en `README.md` y continuar: SAMEPERIODLASTYEAR se probará igual en 6.E; no cambiar `dim_date` a Import (generaría una relación limitada contra el hecho DirectQuery).
- [ ] **D2.** *Sort by column:* `dim_date[month_name]` por `month_number`; `dim_date[year_month]` no necesita; `dim_epi_month[month_label]` por `epi_month_key`; `dim_geography[state_name]` ninguna.
- [ ] **D3.** *Summarize by = Don't summarize* en todas las columnas de clave y de año/semana (`*_key`, `mmwr_year`, `mmwr_week`, `month`, `year`, `period_days`).
- [ ] **D4.** Ocultar (*Hide in report view*): todas las columnas `*_key` salvo `geo_key` si se usa en visuales, `fact_id`, `cum_ytd*`, `max_prev_52w`; **ocultar las tablas** `dim_access` y `agg_weekly_national`; `dim_access` además no debe aparecer en ningún visual.
- [ ] **D5.** Categorías de datos: `dim_geography[state_name]` → *State or Province*; `dim_geography[county_name]` → *County*.
- [ ] **D6.** Crear la tabla de medidas: *Home → Enter data* → una columna `x` → nombre de tabla `_Measures` → Load. Ocultar la columna `x`.

**GATE 6.D.** Sin error al marcar la tabla de fechas (o hallazgo anotado) · `month_name` ordena Jan…Dec · captura `docs/img/gate_6D.png`.

### Task 6.E — Medidas NNDSS
Crear en la tabla `_Measures` (*Table tools → New measure*; pegar el nombre y la fórmula; formato en *Measure tools*). Orden fijo: cada una depende de las anteriores. Display folder `NNDSS`.

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
Formato `0.0`. Es una tasa **anualizada**: cada fila semanal aporta 1/52,18 años de la población de su año.
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
**Solo se usa con campos de `dim_date`.** Si el visual también filtra con `dim_mmwr_week`, el resultado se anula.
```dax
Corridor P75 =
VAR w = SELECTEDVALUE ( dim_mmwr_week[mmwr_week] )
VAR y = SELECTEDVALUE ( dim_mmwr_week[mmwr_year] )
VAR hist =
    FILTER (
        ALL ( dim_mmwr_week[mmwr_year] ),
        dim_mmwr_week[mmwr_year] >= y - 5 && dim_mmwr_week[mmwr_year] < y
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
`Corridor P25` y `Corridor P50`: la misma fórmula con `0.25` y `0.5` al final.
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
Formato de ambas: `0` (sin separador de miles).

**GATE 6.E — Pruebas (DAX query view).** Cada bloque se ejecuta y se compara con la columna Expected.

*E1 — Caso base A3.*
```dax
EVALUATE ROW ( "v", CALCULATE ( [Cases NNDSS], dim_geography[geo_key] = "CA",
        dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202452 ) )
```
Expected: **499**.

*E2 — Tasa anualizada (A4).*
```dax
EVALUATE ROW (
    "CA_CHL_2024", CALCULATE ( [Rate per 100k NNDSS], dim_geography[geo_key] = "CA",
        dim_disease[disease_key] = "CHL", dim_mmwr_week[mmwr_year] = 2024 ),
    "GON_2025", CALCULATE ( [Rate per 100k NNDSS], dim_disease[disease_key] = "GON",
        dim_mmwr_week[mmwr_year] = 2025 )
)
```
Expected: **259,434** y **62,036** (tolerancia ±0,001). Si 2025 da ~63,0 se está dividiendo por una sola población en lugar de persona-años.

*E3 — Interanual en rango (A5).*
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
Expected: **163.363 · 167.261 · −0,0233 · 164.428**. La diferencia 167.261 − 164.428 = 2.833 son los casos de la semana 2025-W1 (empieza el 2024-12-29).

*E4 — Interanual de una semana (A5b).*
```dax
EVALUATE ROW (
    "cases", CALCULATE ( [Cases NNDSS], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "ly_mmwr", CALCULATE ( [Cases LY (MMWR aligned)], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "ly_sply", CALCULATE ( [Cases LY (SAMEPERIODLASTYEAR)], dim_disease[disease_key] = "GON",
        DATESBETWEEN ( dim_date[date], DATE ( 2026, 10, 4 ), DATE ( 2026, 10, 4 ) ) )
)
```
Expected: **4.627 · 4.830 · (vacío)**. El vacío no es un error: es el resultado negativo que se documenta (los datos son semanales, el 2025-10-04 es sábado y no hay semana que empiece ese día).

*E5 — Corredor y exceso (A6).*
```dax
EVALUATE ROW (
    "p25", CALCULATE ( [Corridor P25], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "p50", CALCULATE ( [Corridor P50], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "p75", CALCULATE ( [Corridor P75], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "cases", CALCULATE ( [Cases NNDSS], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "excess", CALCULATE ( [Excess over P75], dim_geography[geo_key] = "CA", dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 )
)
```
Expected: **657,75 · 810 · 885,75 · 1 · 0**. (CA tiene 1 caso en la semana en curso por retraso de notificación; por eso la página usa la semana de referencia.)

*E6 — Estados en brote (A7).*
```dax
EVALUATE ROW (
    "w40", CALCULATE ( [States in Outbreak], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202640 ),
    "w38", CALCULATE ( [States in Outbreak], dim_disease[disease_key] = "GON", dim_mmwr_week[epi_week_key] = 202638 )
)
```
Expected: **11** y **15**.

*E7 — Semana de referencia (A8).*
```dax
EVALUATE ROW ( "ref", [Reference Week], "latest", [Latest Week With Data] )
```
Expected: **202638 · 202640**.

*E8 — Semana 53.* `EVALUATE ROW ( "w53_2025", CALCULATE ( [Cases NNDSS], dim_mmwr_week[epi_week_key] = 202553 ) )` → número > 0; `... = 202653` → vacío. (2025 tiene 53 semanas MMWR, 2026 todavía no.)

- [ ] E1–E8 todos con el valor esperado · [ ] ningún valor "casi" correcto sin explicación · [ ] captura `docs/img/gate_6E.png`.

### Task 6.F — Medidas de Oregon, calidad y revisiones
Display folder `Oregon`.
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
            FILTER (
                fct_oregon_monthly,
                NOT fct_oregon_monthly[is_masked]
                    && NOT ISBLANK ( fct_oregon_monthly[cases] )
                    && fct_oregon_monthly[population] > 0
            ),
            fct_oregon_monthly[population] * RELATED ( dim_epi_month[period_days] ) / 365.25
        ),
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
            COUNTROWS ( FILTER ( fct_oregon_monthly, fct_oregon_monthly[is_masked] ) ),
            COUNTROWS ( fct_oregon_monthly )
        ),
        KEEPFILTERS ( dim_demographic[demographic_type] = t )
    )
```
```dax
Share of Statewide Captured = DIVIDE ( [Cases Oregon], [Cases Oregon (statewide)] )
```
Formatos: casos `#,##0`; tasa `0.0`; los dos últimos `0.0%`. Folder `Quality / Revisions`:
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
Folder `QA` (se usan en el Task 7):
```dax
QA Geo Rows = COUNTROWS ( dim_geography )
QA Access Rows = COUNTROWS ( dim_access )
QA Demographic Rows = COUNTROWS ( dim_demographic )
QA Revision Rows = COUNTROWS ( mart_revisions )
```

**GATE 6.F.**

*F1 — Sin doble conteo (A9).*
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "chl", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "CHL" ) )
ORDER BY dim_demographic[demographic_type]
```
Expected: **Age Group 81.886 · Geography 80.587 · Race (alone) 92.237 · Race (primary) 81.803 · Sex 81.733 · Statewide 82.066**. Una tarjeta *sin* filtros de demografía debe mostrar `Cases Oregon` CHL = **80.587** (no 500.312, no 162.653).

*F2 — Sexo (A9b).*
```dax
EVALUATE
SUMMARIZECOLUMNS ( dim_demographic[demographic_level], FILTER ( ALL ( dim_demographic[demographic_type] ), dim_demographic[demographic_type] = "Sex" ),
    "chl", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "CHL" ) )
```
Expected: Female **52.038** · Male **29.695** · Nonbinary y Unknown vacíos (suprimidos).

*F3 — Caso Multnomah (A10).*
```dax
EVALUATE ROW (
    "m01", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[epi_month_key] = 202601 ),
    "y2025", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[mmwr_year] = 2025 ),
    "all", CALCULATE ( [Cases Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL" ),
    "rate2025", CALCULATE ( [Rate per 100k Oregon], dim_geography[geo_key] = "OR|Multnomah County", dim_disease[disease_key] = "CHL", dim_epi_month[mmwr_year] = 2025 )
)
```
Expected: **294 · 3.376 · 23.787 · 414,658**. (2025 suma 371 días porque tiene 53 semanas MMWR; por eso los persona-años son 1,0157 × población.)

*F4 — Supresión por corte (A11).*
```dax
EVALUATE SUMMARIZECOLUMNS ( dim_demographic[demographic_type], "supp", [% Suppressed Cells] ) ORDER BY dim_demographic[demographic_type]
```
Expected: Age Group **0,688** · Geography **0,792** · Race (alone) **0,583** · Race (primary) **0,659** · Sex **0,607** · Statewide **0,000**.

*F5 — Cobertura (A12).*
```dax
EVALUATE ROW (
    "hiv_visible", CALCULATE ( [Cases Oregon], dim_disease[disease_key] = "HIV" ),
    "hiv_state", CALCULATE ( [Cases Oregon (statewide)], dim_disease[disease_key] = "HIV" ),
    "hiv_share", CALCULATE ( [Share of Statewide Captured], dim_disease[disease_key] = "HIV" ),
    "chl_share", CALCULATE ( [Share of Statewide Captured], dim_disease[disease_key] = "CHL" )
)
```
Expected: **376 · 1.291 · 0,291 · 0,982**.

*F6 — Revisiones y calidad.*
```dax
EVALUATE ROW ( "rev", [Revisions (n)], "status", [Revisions Status], "ingest", [Latest Ingest (UTC)] )
```
Expected: `rev` = **0**, `status` = "No revisions recorded yet", `ingest` = fecha de la última corrida del workflow. (Mientras el CDC no revise ninguna semana, `mart_revisions` es todo ceros: es el estado real, no un fallo.)

- [ ] F1–F6 correctos · [ ] captura `docs/img/gate_6F.png`.

### Task 6.G — Agregaciones
- [ ] **G1.** Clic derecho en `agg_weekly_national` (Model view o panel Data) → **Manage aggregations**. Tres filas:

| Columna de la tabla agg | Summarization | Detail table | Detail column |
|---|---|---|---|
| `cases_week` | Sum | `fct_nndss_weekly` | `cases_week` |
| `epi_week_key` | GroupBy | `fct_nndss_weekly` | `epi_week_key` |
| `disease_key` | GroupBy | `fct_nndss_weekly` | `disease_key` |

  *Apply all.* Esperado: sin errores de validación. Si se queja de tipos de datos, `cases_week` debe ser *Decimal number* en ambas tablas.
- [ ] **G2.** Confirmar que `agg_weekly_national` ahora está oculta.

**GATE 6.G — La agregación realmente se usa.** Tres pruebas, de menos a más contundente:

- **Prueba 1 — Performance Analyzer.** En *Report view* crear una tabla con `dim_mmwr_week[mmwr_year]`, `dim_disease[disease_key]` y `[Cases NNDSS]` (visual A) y otra con `dim_geography[state_code]` y `[Cases NNDSS]` (visual B). *View → Performance analyzer → Start recording → Refresh visuals*. **Expected:** el visual A muestra solo "DAX query" y "Visual display" (sin "Direct query"); el visual B muestra además **Direct query** con milisegundos. A = acierto de agregación; B = fallo, como debe ser (la agregación no tiene estado).
- **Prueba 2 — Rastro de DAX Studio.** Conectar DAX Studio al modelo abierto, *View → All Queries* + *Server Timings*, ejecutar `EVALUATE SUMMARIZECOLUMNS ( dim_mmwr_week[mmwr_year], dim_disease[disease_key], "c", [Cases NNDSS] )`. **Expected:** en el rastro un evento de reescritura de tabla agregada con coincidencia encontrada y **ninguna** consulta SQL al origen. Con `dim_geography[state_code]` en lugar de `mmwr_year`: reescritura fallida y consulta SQL presente.
- **Prueba 3 (decisiva) [CLAUDE].** El agente ejecuta `REVOKE SELECT ON analytics_marts.fct_nndss_weekly FROM pbi_reader;`. En Desktop, *Refresh* sobre la página: **Expected:** el visual A sigue mostrando datos (viene de Import) y el visual B muestra error de permiso. El agente restaura con `GRANT SELECT ON analytics_marts.fct_nndss_weekly TO pbi_reader;` (o corriendo `dbt build`) y confirma que B vuelve. Es la prueba que no admite interpretación.

- [ ] Prueba 1 · [ ] Prueba 2 · [ ] Prueba 3 (con permiso restaurado y verificado) · [ ] capturas `docs/img/agg_hit.png` y `docs/img/agg_miss.png`.

### Task 6.H — Guardar, versionar y cerrar el Task
- [ ] **H1.** *File → Save*. Verificar en el explorador de archivos que existen `data_model/STI_Surveillance_Model.pbip`, `STI_Surveillance_Model.SemanticModel/definition/` con `model.tmdl`, `relationships.tmdl` y `tables/*.tmdl` (12 archivos de tabla), y `STI_Surveillance_Model.Report/`.
- [ ] **H2.** Búsqueda de secretos antes de commitear (PowerShell o Git Bash): `git grep -nE "npg_|PASSWORD|pbi_reader" -- data_model` → **sin resultados**. El host de Neon sí aparece en las consultas M del TMDL: no es una credencial (la contraseña vive en el gestor de credenciales de Desktop). **Decisión registrada:** se versiona el host; si el repo pasara a público, se rota el rol `pbi_reader` y se parametriza el host.
- [ ] **H3.** `git status` no debe listar `.pbi/localSettings.json`, `cache.abf` ni ningún `.pbix`.
- [ ] **H4.** [CLAUDE, tras el push y `git pull` en Linux] Verificar que el recurso MCP lee el modelo:
```bash
MCP_DATABASE_URL=x .venv/bin/python -I -c "import sys; sys.path.insert(0,'mcp'); import mcp_server as m; t=m.get_powerbi_schema(); print(len(t), 'measure' in t and 'Cases NNDSS' in t)"
```
  Expected: longitud > 10.000 y `True`.
- [ ] **H5.** Mensaje de commit (lo corre la persona de Windows): `feat(pbi): composite semantic model with aggregations and epidemiological measures`.

**GATE FINAL DEL TASK 6:** GATES P, 6.A–6.H todos en ✔ con sus capturas · ninguna medida devolvió un valor "aproximado" sin explicar · modelo guardado como PBIP y versionado.

---

## Task 7 [HUMANO]: Seguridad RLS y OLS

**Qué se protege.** `dim_access(user_principal_name, state_code, county_name)` define qué ve cada persona; `*` es comodín por columna. Usuarios del seed: `ana@TENANT…` (OR, Multnomah County), `luis@…` (CA, *), `admin@…` (*, *), `sofia@…` (OR, *). En Desktop no hace falta un tenant real: *View as → Other user* acepta cualquier texto. El dominio real solo hace falta en la prueba del servicio (7.E).

### Task 7.A — Roles RLS (en Desktop)
*Modeling → Manage roles → New*. En cada rol, *Table filter DAX expression*:

- [ ] **`State_Analyst`** — tabla `dim_geography`:
```dax
COUNTROWS (
    FILTER (
        dim_access,
        dim_access[user_principal_name] = USERPRINCIPALNAME ()
            && ( dim_access[state_code] = "*" || dim_access[state_code] = dim_geography[state_code] )
    )
) > 0
```
- [ ] **`County_Analyst`** — tabla `dim_geography` (mismo patrón; exige coincidir también el condado):
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
- [ ] En **ambos** roles, tabla `dim_access`: `dim_access[user_principal_name] = USERPRINCIPALNAME ()` (cada persona solo ve su propia fila; sin esto cualquiera vería los permisos de los demás).
- [ ] **`Admin`**: rol sin filtros.

**GATE 7.A.** *Manage roles* muestra los 3 roles; los filtros no muestran error de sintaxis (cada uno con el ✔ verde) · captura `docs/img/gate_7A.png`.

### Task 7.B — Página QA (para probar con *View as*)
*View as* afecta a los visuales del informe, no a la pestaña DAX query: las pruebas de seguridad se hacen en una página.
- [ ] Crear la página `_QA` con: segmentadores `dim_disease[disease_key]` y `dim_mmwr_week[mmwr_year]`; tarjetas con `QA Geo Rows`, `QA Access Rows`, `QA Demographic Rows`, `[Cases NNDSS]`, `[Cases Oregon]`, `[Cases Oregon (statewide)]`; tabla con `dim_geography[geo_key]` y `[Cases NNDSS]`; tabla con `dim_demographic[sex]` y `[Cases Oregon]`.
- [ ] Dejarla **oculta** al publicar (clic derecho en la pestaña → *Hide page*).

### GATE 7.C — Matriz RLS (View as)
*Modeling → View as*: marcar el rol, marcar **Other user** y escribir el UPN. Con `dim_disease = GON` y `mmwr_year = 2025` en los segmentadores salvo donde se indique CHL. Copiar los valores a la tabla de resultados.

| # | Rol | Other user | `QA Geo Rows` | `QA Access Rows` | `[Cases NNDSS]` GON 2025 | Cases Oregon (statewide) CHL | Cases Oregon CHL (Geography) |
|---|---|---|---|---|---|---|---|
| 1 | State_Analyst | `ana@TENANT.onmicrosoft.com` | **38** | **1** | **4.073** | **82.066** | **80.587** |
| 2 | State_Analyst | `luis@TENANT.onmicrosoft.com` | **1** | **1** | **31.479** | vacío | vacío |
| 3 | State_Analyst | `sofia@TENANT.onmicrosoft.com` | **38** | **1** | **4.073** | **82.066** | **80.587** |
| 4 | State_Analyst | `ANA@tenant.onmicrosoft.com` (mayúsculas) | igual que fila 1 | | | | |
| 5 | State_Analyst | `nadie@TENANT.onmicrosoft.com` | **0** | **0** | vacío | vacío | vacío |
| 6 | County_Analyst | `ana@TENANT.onmicrosoft.com` | **1** | **1** | vacío | vacío | **23.787** |
| 7 | County_Analyst | `luis@TENANT.onmicrosoft.com` | **1** | **1** | **31.479** | vacío | vacío |
| 8 | County_Analyst | `sofia@TENANT.onmicrosoft.com` | **38** | **1** | **4.073** | **82.066** | **80.587** |
| 9 | County_Analyst | `nadie@TENANT.onmicrosoft.com` | **0** | **0** | vacío | vacío | vacío |
| 10 | Admin | cualquiera | **93** | **4** | **217.373** (todos) | **82.066** | **80.587** |

Notas que explican los valores: en la fila 1 `Cases Oregon (statewide)` se ve porque el estado `OR` está permitido; en la fila 6 no, porque el condado limitado oculta la fila estatal (`county_name` vacío ≠ `Multnomah County`) y con ella todos los cortes demográficos, que cuelgan de `geo_key='OR'`. Las filas 2 y 7 coinciden: `luis` tiene condado `*`, que deja pasar la fila de `CA`.
- [ ] Filas 1–10 coinciden · [ ] la fila 5/9 (`nadie`) no muestra **ningún** dato, ni siquiera ceros · [ ] la tabla `dim_access` nunca muestra filas de otras personas · [ ] captura de cada fila en `docs/img/rls_01.png` … `rls_10.png`.
- [ ] **Prueba negativa de combinación:** en *View as* marcar **a la vez** `State_Analyst` y `Restricted_Epidemiologist` (cuando exista, 7.D). Anotar el comportamiento exacto observado en `README.md` ("Limitaciones"). No se asume resultado.

### Task 7.D — OLS con Tabular Editor 2 (sobre el modelo abierto en Desktop)
- [ ] **D1.** Desktop → *External Tools → Tabular Editor*. En TE2: clic derecho en *Roles → Create new role* → nombre `Restricted_Epidemiologist`; *Model Permission* = `Read`.
- [ ] **D2.** Seleccionar la columna `dim_demographic[race_group]` → en el panel de propiedades, *Object Level Security*: para el rol `Restricted_Epidemiologist` poner **None**. Repetir con `dim_demographic[age_group]`, `dim_demographic[demographic_level]` (**incluida**: contiene los mismos valores; sin ella el OLS es decorativo) y la tabla `mart_revisions` (seleccionar la tabla → *Object Level Security* = None).
- [ ] **D3.** Crear el rol `Restricted_State_Analyst`: *Model Permission* = Read, mismo filtro RLS de `State_Analyst` en `dim_geography` y en `dim_access`, y las mismas 4 restricciones OLS. (Un usuario no puede estar en un rol con RLS y en otro con OLS: se combinan en uno solo.)
- [ ] **D4.** `Ctrl+S` en TE2 (aplica al modelo de Desktop). En Desktop: *File → Save*.
- [ ] **D5.** Revisar el diff en git de `definition/roles/*.tmdl`: debe aparecer `metadataPermission: none` bajo cada columna/tabla restringida, y el filtro RLS en `Restricted_State_Analyst`. Si falta, el OLS no se guardó.

**GATE 7.D — Pruebas OLS** (*View as → Restricted_Epidemiologist*, Other user `ana@TENANT.onmicrosoft.com`):
- [ ] Un visual con `dim_demographic[race_group]` y `[Cases Oregon]` → **error** ("no se puede acceder al campo") en vez de datos.
- [ ] Ídem con `age_group`, con `demographic_level` y con una tarjeta `QA Revision Rows` (tabla `mart_revisions`).
- [ ] Un visual con `dim_demographic[sex]` y `[Cases Oregon]` (CHL) → **funciona**: Female **52.038**, Male **29.695**.
- [ ] `QA Demographic Rows` → **39** (la tabla existe; solo faltan columnas).
- [ ] Con `Restricted_State_Analyst` y `ana@…`: `QA Geo Rows` = **38** *y* los 4 visuales anteriores fallan igual.
- [ ] **Si Desktop devuelve datos donde se esperaba error** (Desktop no aplica OLS en *View as*): no se da el GATE por aprobado. Se anota en el README y la verificación pasa a 7.E, que es obligatoria entonces.
- [ ] Capturas `docs/img/ols_*.png`.

### Task 7.E — Prueba en el servicio (copia Import)
DirectQuery a PostgreSQL requiere un gateway; no se instala. Se prueba la seguridad con una **copia** del modelo.
- [ ] **E1.** *Save as* `STI_Surveillance_ServiceTest.pbix` **fuera del repo** (es un `.pbix`: contiene datos, está en `.gitignore`).
- [ ] **E2.** En la copia, *Model view*: cambiar `fct_nndss_weekly`, `fct_oregon_monthly` y las 6 dimensiones a **Import** (acepta el aviso de irreversible; es una copia). La agregación y el resto ya son Import. *Home → Refresh*.
- [ ] **E3.** Repetir en la copia los valores de 6.A (conteos) y 6.E1/6.F3 para confirmar que la copia produce los mismos números.
- [ ] **E4.** Publicar a un workspace **privado** (trial de Fabric o developer tenant de M365). *Nunca* "Publish to web".
- [ ] **E5.** [CLAUDE, antes de E6] Reemplazar `TENANT.onmicrosoft.com` en `dbt/seeds/dim_access.csv` por el dominio real y las cuentas de prueba reales, correr `dbt seed`, y en la copia *Refresh* + volver a publicar.
- [ ] **E6.** En el servicio: modelo semántico → *Security* → asignar cuentas de prueba a cada rol → *Test as role* (por rol) y luego iniciar sesión con cada cuenta de prueba en una ventana privada.

**GATE 7.E.** Repetir las filas 1, 2, 5, 6 y 10 de la matriz 7.C y las pruebas OLS de 7.D con las cuentas reales. **Expected:** mismos valores; el OLS **bloquea** los campos restringidos (aquí sí se exige). Capturas `docs/img/service_rls_*.png`, `docs/img/service_ols_*.png`. Después, **eliminar** la copia del workspace o quitar a los invitados.

**GATE FINAL DEL TASK 7:** 7.A–7.E aprobados · mensaje de commit: `feat(security): dynamic RLS (state/county) and OLS roles with tested matrix`.

---

## Task 8 [CLAUDE + HUMANO]: MCP en un cliente real

La máquina actual es Linux y Claude Desktop no existe para Linux: la prueba se hace con **Claude Code**, y Claude Desktop se deja como segunda verificación en Windows/macOS.

- [ ] **8.1 [CLAUDE]** Registrar el servidor en Claude Code (el valor de `MCP_DATABASE_URL` se lee de `.env` sin imprimirse):
```bash
claude mcp add sti-epidemiology -e MCP_DATABASE_URL="$MCP_DATABASE_URL" -- ~/Documents/proyectos/sti-surveillance/.venv/bin/python ~/Documents/proyectos/sti-surveillance/mcp/mcp_server.py
```
  Verificar la sintaxis con `claude mcp add --help` antes de correrlo, y `claude mcp list` debe mostrar `sti-epidemiology` conectado.
- [ ] **8.2 [HUMANO]** En una sesión nueva de Claude Code, pedir las tres pruebas en lenguaje natural y guardar capturas:
  1. *Consulta válida:* "usa la herramienta para sumar los casos de clamidia de la vista `mcp_oregon_county_monthly`". Expected: **80.587** (A15).
  2. *DML:* "ejecuta `DELETE FROM analytics_marts.fct_oregon_monthly`". Expected: `ERROR: base de datos de solo lectura.`
  3. *OLS:* "muéstrame `race_group` de `analytics_marts.dim_demographic`". Expected: `ERROR [OLS-HIPAA]: acceso denegado a objeto restringido.`
  4. *Doble conteo:* "suma los casos de clamidia de Oregon". Expected: el asistente usa la vista de condados y reporta ~80.587, o explica que existen cortes no aditivos; **no** debe devolver 500.312.
  5. *Recurso:* pedir el esquema de Power BI. Expected: el texto del TMDL con `measure 'Cases NNDSS'`.
- [ ] **8.3 [HUMANO, opcional]** Repetir 1–3 en Claude Desktop con el JSON del README y guardar `docs/img/mcp_*.png`.
- [ ] **8.4** Capturas: `docs/img/mcp_valid.png`, `mcp_dml_block.png`, `mcp_ols_block.png`, `mcp_resource.png`.

**GATE 8:** las tres respuestas esperadas coinciden palabra por palabra · la prueba 4 no devuelve 500.312 · mensaje de commit: `docs: MCP verification screenshots`.

---

## Task 9: Tema accesible, informe de 7 páginas y documentación final

### 9.1 [CLAUDE] Tema `theme/dark_accessible.json` con verificación de contraste
- [ ] **Step 1 (RED):** crear `tests/test_theme_contrast.py`:
```python
import json, pathlib

def lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

THEME = json.loads((pathlib.Path(__file__).parent.parent / "theme" / "dark_accessible.json").read_text())
BG, CARD = "#0F1720", "#18232F"

def test_text_meets_wcag_aa():
    for key in ("foreground", "hyperlink", "visitedHyperlink"):
        for bg in (BG, CARD):
            assert ratio(THEME[key], bg) >= 4.5, (key, bg)

def test_data_colors_meet_non_text_contrast():
    assert len(THEME["dataColors"]) >= 8
    for c in THEME["dataColors"]:
        for bg in (BG, CARD):
            assert ratio(c, bg) >= 3.0, (c, bg)

def test_sequential_map_endpoints_visible():
    assert ratio("#4F7CA3", BG) >= 3.0 and ratio("#F0E442", BG) >= 3.0
```
  Run: `.venv/bin/pytest tests/test_theme_contrast.py -q` → FAIL (el archivo no existe).
- [ ] **Step 2 (GREEN):** crear `theme/dark_accessible.json`:
```json
{
  "name": "STI Dark Accessible",
  "dataColors": ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#EF7B3A", "#CC79A7", "#4A9FD6", "#9AA7B4"],
  "background": "#18232F",
  "foreground": "#E6EDF3",
  "tableAccent": "#56B4E9",
  "good": "#009E73",
  "neutral": "#E69F00",
  "bad": "#EF7B3A",
  "minimum": "#56B4E9",
  "center": "#9AA7B4",
  "maximum": "#EF7B3A",
  "null": "#9AA7B4",
  "hyperlink": "#7FC4F5",
  "visitedHyperlink": "#CC79A7",
  "textClasses": {
    "title": { "fontFace": "Segoe UI Semibold", "fontSize": 14, "color": "#E6EDF3" },
    "label": { "fontFace": "Segoe UI", "fontSize": 11, "color": "#A9B7C6" },
    "callout": { "fontFace": "Segoe UI Semibold", "fontSize": 32, "color": "#E6EDF3" }
  },
  "visualStyles": {
    "page": { "*": { "background": [{ "color": { "solid": { "color": "#0F1720" } }, "transparency": 0 }] } }
  }
}
```
  Run: `pytest tests/test_theme_contrast.py -q` → 3 PASS. Contrastes ya medidos: texto 15,3 (sobre fondo) / 13,5 (sobre tarjeta); atenuado `#A9B7C6` 8,8; hipervínculo 9,6; colores de datos entre 4,6 y 13,7.
- [ ] **Step 3:** mensaje de commit: `feat(theme): accessible dark theme with contrast tests`.

### 9.2 [HUMANO] Informe
*View → Themes → Browse for themes* → `theme/dark_accessible.json`. **Colores fijos por enfermedad** en todas las páginas (para no cambiar de color entre visuales): CHL `#56B4E9` · GON `#E69F00` · SYP_PS `#009E73` · SYP_EARLY `#F0E442` · SYP_CONG `#EF7B3A` · HIV `#CC79A7`. Mapa de tasas: rampa secuencial `#4F7CA3` → `#F0E442`. Cada visual: **título**, **alt text** (*Format → General → Alt text*) con la lectura clave, y orden de tabulación (*View → Selection → Tab order*) de izquierda a derecha y de arriba abajo.

Cada página termina con su verificación contra las anclas.

| Pág. | Contenido | Verificación |
|---|---|---|
| 1 Resumen | Segmentadores: enfermedad (CHL/GON/SYP_PS/SYP_CONG), año. Tarjetas: casos, tasa por 100k, YoY alineado MMWR, estados en brote, semana de referencia, última semana con datos. Línea de casos semanales con el corredor P25/P50/P75 | GON · 2025: casos 217.373, tasa 62,0. GON · 2026 sem. 1–40: YoY −2,3 % |
| 2 Mapa | Mapa de relleno por `state_name` con `[Rate per 100k NNDSS]`; tabla lateral top 10 | Se ven los 50 estados + DC; territorios sin población aparecen "sin dato", no con 0 |
| 3 Ranking | Barras por estado: tasa y exceso sobre P75 (semana de referencia) | CA GON 2024-W52 en la tabla = 499 |
| 4 Corredor | Año en curso contra P25/P50/P75 para un estado elegido; nota "corredor con 4 años (2022–2025)" | CA GON sem. 40: 657,75 · 810 · 885,75 |
| 5 Oregon por condado | Mapa/barras por `county_name` con tasa; tarjeta `% Suppressed Cells`; `Share of Statewide Captured`; nota visible sobre celdas suprimidas | Multnomah CHL 2025: 3.376 casos, tasa 414,7; supresión Geography 79,2 % |
| 6 Demografía | Casos por sexo, edad, raza (cada visual fuerza **un** corte; nunca mezclar tipos); aviso "estos visuales están bloqueados para el rol restringido" | CHL por sexo: 52.038 / 29.695; por edad A14 |
| 7 Calidad | `mart_data_quality` (última ingesta, período máximo, filas, % enmascarado, % `U`); `Revisions Status`; antigüedad de cada fuente | `Revisions Status` = "No revisions recorded yet"; ingesta ≤ 8 días |

**GATE 9.2** (accesibilidad y usabilidad):
- [ ] **Teclado:** recorrer cada página solo con `Tab`/`Shift+Tab`/`Enter`; el orden es lógico y se puede llegar a todos los segmentadores y visuales.
- [ ] **Daltonismo:** capturar las páginas 1, 2 y 5 y pasarlas por un simulador de protanopia, deuteranopia y tritanopia; las enfermedades siguen siendo distinguibles por color y por etiqueta.
- [ ] **Alt text** presente en el 100 % de los visuales (revisar en *Selection pane*).
- [ ] **Sin números sin contexto:** ninguna tasa sin su unidad ("por 100.000, anualizada"); ninguna página de Oregon sin el aviso de supresión.
- [ ] **Contraste visual:** sin texto de menos de 11 pt; nada depende solo del color.
- [ ] Capturas de las 7 páginas en `docs/img/page_1.png` … `page_7.png`; guardar y commitear PBIP. Commit: `feat(report): 7-page accessible report`.

### 9.3 [CLAUDE] README, spec y linaje final
- [ ] Actualizar `README.md` y `README_es.md`: tabla de fases (marcar lo completado), sección *Results* con las verificaciones reales (A1–A15 comprobadas, agregación con Prueba 3, matriz RLS, OLS en servicio), *Design decisions* (Dual, agregación mínima, persona-años, corte `Statewide`, RLS+OLS en un rol, `dim_demographic[demographic_level]` en OLS, rol `pbi_reader`), *Limitations* (SAMEPERIODLASTYEAR en una semana da vacío; corredor con 4 años; SYP_CONG con corredor 0; interpretación del comportamiento observado en la combinación de roles; OLS en *View as*). Insertar las capturas.
- [ ] Actualizar `docs/superpowers/specs/…-design.md` y copiar este plan a `docs/superpowers/plans/2026-10-14-powerbi-tasks-6-9.md`.
- [ ] Marcar la dimensión de linaje: `dbt docs generate` y captura `docs/img/dbt_lineage.png` con la exposure.
- [ ] Commit: `docs: final README, results and screenshots`.

---

## Verificación final (definición de "terminado")
Checklist original de `powerbi_consolidado.md` §10, con la evidencia de este plan:

| Entregable | Evidencia |
|---|---|
| Medidas DAX ejecutadas y validadas contra SQL | GATES 6.E y 6.F: E1–E8 y F1–F6 contra `sql/qa_anchors.sql` |
| *Aggregation hit* verificado | GATE 6.G, Pruebas 1–3 (la 3 con `REVOKE`/`GRANT`) |
| RLS dinámica y OLS probadas en Desktop y en el servicio | GATES 7.C, 7.D y 7.E |
| Capturas en `docs/img/` | gate_6A…6F, agg_hit/miss, rls_01–10, ols_*, service_*, mcp_*, page_1–7, dbt_lineage |
| Tema oscuro accesible | `tests/test_theme_contrast.py` en verde + GATE 9.2 |
| `dbt build` en verde y linaje de la exposure | GATE 6.0–6.1 y `dbt docs generate` |
| MCP probado en un cliente real | GATE 8 |
| Ninguna credencial en el historial | `git log -p | grep -iE 'npg_\|PASSWORD=[A-Za-z0-9]{8,}'` → vacío, y `git grep -nE "npg_\|PASSWORD" -- data_model` → vacío |
| README con arquitectura, decisiones y límites | Task 9.3 |

## Riesgos conocidos (no verificados en este plan)
- RLS sobre una dimensión **Dual** en un modelo compuesto: la documentación consultada no lo prohíbe, pero no se probó. Si *View as* devuelve un error de DirectQuery/RLS en el GATE 7.A, la contingencia es cambiar `dim_geography` y `dim_access` a Import (las relaciones con los hechos pasan a limitadas) y volver a ejecutar los GATES 6.B–6.G; se anota en el README.
- La sintaxis exacta de `role` en TMDL con `metadataPermission` no se pudo confirmar en la documentación; el GATE 7.C la comprueba por el diff, no por memoria.
- Neon suspende el cómputo tras 5 minutos de inactividad: la primera consulta DirectQuery tras una pausa puede tardar unos segundos; no es un fallo.
- Cada ingesta semanal cambia las anclas dependientes de datos nuevos (`fct_*`, semana de referencia, estados en brote de la semana en curso). Los valores históricos citados solo cambian con una revisión del CDC.
