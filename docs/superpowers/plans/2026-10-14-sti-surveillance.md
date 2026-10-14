# STI Surveillance Platform (NNDSS + Oregon) Implementation Plan

> **Nota:** este es el plan original. Lo que cambió al ejecutarlo (cron semanal, versiones fijadas, vista del MCP, `fact_id` md5, `demographic_level='All'` para Geography) está en `README.md` y en la spec.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context
`powerbi_consolidado.md` define un portfolio Senior Data Analyst (Postgres gratis + dbt + Power BI PBIP compuesto + RLS/OLS + MCP), pero la fuente era genérica ("CDC NNDSS / AtlasPlus / WHO") y la demografía (edad/sexo/condado) quedaba sin fuente real o sintética. Este plan fija las fuentes **testeadas en vivo el 2026-10-14** y reescribe el modelo para que RLS y OLS operen sobre campos reales.

**Decisión del usuario:** fuente híbrida NNDSS (nacional semanal) + Oregon (mensual, demográfica).

### Fuentes testeadas (todas gratis, sin API key, SoQL/CSV)
| Fuente | Endpoint | Estado del test | Volumen ETS | Clave natural (unicidad verificada) |
|---|---|---|---|---|
| CDC NNDSS Weekly | `https://data.cdc.gov/resource/x9gk-5huc.json` | 200 OK, datos hasta MMWR 2026-W40 | 69.720 filas, 2022–2026, 70 ubicaciones | `(year, week, label, states)` |
| Oregon Monthly Reportable Disease | `https://data.oregon.gov/resource/rk77-sqhz.json` | 200 OK, `run_date=2026-10-14`, hasta 2026-M09 | ~25.460 filas, 2021–2026 | `(mmwr_year, month, disease_name, demographic, demographic_level, confirmation_status)` |
| Census PEP Vintage 2025 | `https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv` | 200 OK (53 KB) | 66 filas, `POPESTIMATE2020..2025` | `NAME` |

Descartadas: California CHHS (CKAN OK pero termina en 2021), Illinois IDPH (≤2016), NYC HIV (≤2022, anual), AtlasPlus (sin API), Census API (ahora exige key → se usa el CSV estático).

**Campos NNDSS:** `states, year, week, label, m1(casos semana), m2(máx 52 sem previas), m3(acumulado año), m4(acumulado año previo), m*_flag, location1(estado), location2(división/región), sort_order, geocode`.
Labels ETS: `Chlamydia trachomatis infection`, `Gonorrhea`, `Syphilis, Primary and secondary`, `Syphilis, Congenital`.

**Campos Oregon:** `mmwr_year, month, report_period_start/end, disease_name, demographic (Geography|Sex|Age Group|Race (alone or in combination)|Race (primary/least common race)), demographic_level, geo_name, geo_unit (county|state), age_group, confirmation_status, count_masked ('NA' si <6), count_label ('<6'), masked (0/1), population, pop_source, run_date`.
Enfermedades ETS: `Chlamydia, Gonorrhea, Early syphilis, Congenital syphilis, HIV`. **Cada fila es un marginal**: una sola dimensión demográfica por fila (no hay cruces sexo×edad).

---

**Goal:** Pipeline semanal gratuito NNDSS+Oregon → Postgres → dbt → modelo compuesto Power BI con RLS (estado/condado), OLS (raza/edad/revisiones) y servidor MCP read-only.

**Architecture:** `scripts/ingest.py` hace full-reload idempotente (upsert) de las 3 fuentes a `raw.*` (son ~100k filas: sin lógica incremental). `dbt snapshot` captura revisiones de `m1` (retraso de notificación). dbt construye dos hechos (`fct_nndss_weekly` grano semana×estado×enfermedad; `fct_oregon_monthly` grano mes×slice demográfico×enfermedad) con dimensiones compartidas `dim_disease` y `dim_geography`.

**Tech Stack:** Python 3.12 (requests, psycopg2-binary, pytest), Neon Postgres (free), dbt-core 1.12.6 + dbt-postgres 1.11.0, Power BI Desktop (PBIP/TMDL), Tabular Editor 2, MCPServer (`mcp` 2.3), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-14-sti-surveillance-design.md` (Task 0 lo crea a partir de este Context + `powerbi_consolidado.md`).

## Global Constraints
- Ubicación del proyecto: `~/proyectos/sti-surveillance/`.
- **Nunca** `git commit`/`git push`/`git init` por el agente (CLAUDE.md del usuario): cada paso "Commit" = entregar el mensaje en un bloque de texto, sin líneas de atribución a Claude.
- Repo GitHub privado.
- Secretos solo en `.env` (local, gitignored) y GitHub Secrets: `DATABASE_URL`.
- Python 3.12; dependencias: `requests psycopg2-binary dbt-core dbt-postgres pytest mcp` con versiones fijadas (sin fijar dbt-core pip resuelve una beta sin soporte de postgres).
- No publicar con Publish to web.
- Casos enmascarados de Oregon (`masked=1`) se guardan como `NULL` + `is_masked=true`; **nunca** se imputan.
- Agregados NNDSS (`location1 IS NULL`: divisiones, "U.S. Residents", "Non-U.S. Residents") se excluyen del hecho.

## Review Focus
1. **Doble conteo en Oregon por marginales**: sumar casos sin filtrar `Demographic_Type` suma Geography+Sex+Age+Race×2 (≈5×). Esperado: toda medida Oregon fuerza `Demographic_Type` (default `Geography`, geo_unit=county). Test dbt + medida DAX.
2. **New York vs New York City en NNDSS**: NNDSS reporta `New York` (sin NYC) y `New York City` por separado; Census solo tiene NY estado. Esperado: staging suma NYC dentro de `NY`. Test: 0 filas con `state_code IS NULL` en el hecho.
3. **Celdas `<6` en Oregon**: la mayoría de las filas de condado están enmascaradas. Esperado: `cases NULL`, tasas calculadas solo sobre celdas no enmascaradas, KPI "% celdas suprimidas" visible. Test en ingest.
4. **Nombres sucios**: Oregon trae `"Multnomah  County"` (doble espacio) duplicado con `"Multnomah County"`. Esperado: normalización de espacios, 36 condados + `Unknown County`. Test dbt `unique` sobre `geo_key`.
5. **Mapeo de enfermedades entre fuentes**: `Syphilis, Primary and secondary` (NNDSS) ≠ `Early syphilis` (Oregon, incluye early latent); HIV solo existe en Oregon. Esperado: `dim_disease` con `disease_group` comparable y flag `comparable_across_sources=false` para sífilis P&S/early. Test `accepted_values`.

---

## File Structure
```
sti-surveillance/
├── .github/workflows/weekly_ingest.yml  # cron semanal: ingest → dbt snapshot → dbt build
├── .gitignore, .env.example, requirements.txt, README.md
├── scripts/ingest.py                    # fetch + normalize + upsert (3 fuentes)
├── tests/test_ingest.py                 # tests puros de normalización
├── sql/raw_schema.sql                   # DDL raw.*
├── sql/mcp_reader_role.sql              # rol read-only + REVOKE columnas OLS
├── dbt/
│   ├── dbt_project.yml, profiles.yml (env_var)
│   ├── seeds/disease_map.csv, seeds/state_codes.csv, seeds/dim_access.csv
│   ├── snapshots/snap_nndss_weekly.sql
│   ├── models/staging/{_sources.yml, stg_nndss_weekly.sql, stg_oregon_monthly.sql, stg_census_population.sql}
│   └── models/marts/{_marts.yml, dim_disease.sql, dim_geography.sql, dim_mmwr_week.sql, dim_epi_month.sql,
│                     dim_demographic.sql, fct_nndss_weekly.sql, fct_oregon_monthly.sql,
│                     agg_weekly_national.sql, mart_revisions.sql, mart_data_quality.sql, exposures.yml}
├── data_model/STI_Surveillance_Model.pbip (+ .SemanticModel/ TMDL, .Report/)
├── theme/dark_accessible.json
├── mcp/mcp_server.py, mcp/requirements.txt
└── docs/{superpowers/specs/, superpowers/plans/, img/}
```

---

### Task 0: Scaffold + spec

**Files:** Create `sti-surveillance/{.gitignore,.env.example,requirements.txt}`, `docs/superpowers/specs/2026-10-14-sti-surveillance-design.md`, `docs/superpowers/plans/2026-10-14-sti-surveillance.md` (copia de este plan).

- [ ] **Step 1:** Crear directorio y archivos:

`.gitignore`
```
.env
dbt/target/
dbt/logs/
dbt/dbt_packages/
**/.pbi/localSettings.json
**/.pbi/cache.abf
__pycache__/
.venv/
```
`.env.example`
```
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
```
`requirements.txt`
```
requests==2.32.*
psycopg2-binary==2.9.*
dbt-core==1.12.6
dbt-postgres==1.11.0
pytest==8.*
```
- [ ] **Step 2:** Spec = sección Context de este plan + secciones 3–8 de `powerbi_consolidado.md` reescritas con el modelo de Task 4/6/7. Self-review: sin TBD, sin contradicciones.
- [ ] **Step 3:** Usuario corre `git init` y crea repo privado. Mensaje sugerido: `chore: scaffold sti-surveillance project and design spec`.

### Task 1: Base Neon + esquema raw

**Files:** Create `sql/raw_schema.sql`.

**Produces:** tablas `raw.nndss_weekly`, `raw.oregon_monthly`, `raw.census_population` (columnas abajo; Task 2 escribe en ellas).

- [ ] **Step 1:** Usuario crea proyecto Neon free, copia la connection string a `.env` y a GitHub Secret `NEON_DATABASE_URL`.
- [ ] **Step 2:** Escribir DDL:
```sql
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.nndss_weekly (
  year int, week int, label text, states text,
  location1 text, location2 text,
  m1 numeric, m1_flag text, m2 numeric, m2_flag text,
  m3 numeric, m3_flag text, m4 numeric, m4_flag text,
  sort_order text, ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (year, week, label, states)
);

CREATE TABLE IF NOT EXISTS raw.oregon_monthly (
  mmwr_year int, month int, report_period_start date, report_period_end date,
  disease_name text, demographic text, demographic_level text,
  geo_name text, geo_unit text, age_group text, confirmation_status text,
  cases int, is_masked boolean, count_label text,
  population numeric, pop_source text, run_date date,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (mmwr_year, month, disease_name, demographic, demographic_level, confirmation_status)
);

CREATE TABLE IF NOT EXISTS raw.census_population (
  name text, year int, population bigint, region text, division text,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (name, year)
);
```
- [ ] **Step 3:** Aplicar y verificar: `psql "$DATABASE_URL" -f sql/raw_schema.sql && psql "$DATABASE_URL" -c '\dt raw.*'` → 3 tablas.
- [ ] **Step 4:** Mensaje: `feat(db): raw schema for NNDSS, Oregon and Census sources`.

### Task 2: Ingesta (`scripts/ingest.py`)

**Files:** Create `scripts/ingest.py`, `tests/test_ingest.py`.

**Interfaces — Produces:** `soql(url, where) -> list[dict]`, `norm_nndss(r) -> tuple`, `norm_oregon(r) -> tuple`, `norm_census(row) -> list[tuple]`, `main()`.

- [ ] **Step 1: Test que falla** (`tests/test_ingest.py`):
```python
from scripts.ingest import norm_nndss, norm_oregon, norm_census

def test_oregon_masked_is_null_not_zero():
    r = {"mmwr_year": "2026", "month": "8", "report_period_start": "2026-08-02T00:00:00.000",
         "report_period_end": "2026-08-29T00:00:00.000", "disease_name": "Gonorrhea",
         "demographic": "Sex", "demographic_level": "Nonbinary", "geo_name": "Oregon",
         "geo_unit": "state", "age_group": "total", "confirmation_status": "confirmed and presumptive",
         "count_masked": "NA", "count_label": "<6", "masked": "1", "population": "NA",
         "pop_source": "NA", "run_date": "2026-10-14T00:00:00.000"}
    t = norm_oregon(r)
    assert t[11] is None and t[12] is True and t[14] is None

def test_oregon_malformed_date():
    from scripts.ingest import day
    assert day("2021:1:03T00:00:00.000") == "2021-01-03"
    assert day("2026-08-29T00:00:00.000") == "2026-08-29"

def test_oregon_collapses_whitespace():
    r = {"mmwr_year": "2026", "month": "1", "disease_name": "Chlamydia", "demographic": "Geography",
         "demographic_level": "Multnomah  County", "geo_name": "Multnomah", "geo_unit": "county",
         "confirmation_status": "confirmed", "count_masked": "294", "masked": "0", "population": "801546"}
    t = norm_oregon(r)
    assert t[6] == "Multnomah County" and t[11] == 294 and t[12] is False

def test_nndss_missing_counts_are_null():
    r = {"year": "2026", "week": "40", "label": "Gonorrhea", "states": "CALIFORNIA",
         "location1": "CALIFORNIA", "m1_flag": "-", "m2": "1453", "sort_order": "x"}
    t = norm_nndss(r)
    assert t[:4] == (2026, 40, "Gonorrhea", "CALIFORNIA") and t[6] is None and t[8] == 1453.0

def test_census_unpivots_years():
    row = {"NAME": "Oregon", "REGION": "4", "DIVISION": "9",
           **{f"POPESTIMATE{y}": str(4_200_000 + y) for y in range(2020, 2026)}}
    out = norm_census(row)
    assert len(out) == 6 and out[0] == ("Oregon", 2020, 4_202_020, "4", "9")
```
- [ ] **Step 2:** `pytest tests/test_ingest.py -v` → FAIL (`ModuleNotFoundError`). Crear `scripts/__init__.py` vacío.
- [ ] **Step 3: Implementación mínima:**
```python
import csv, io, os, re
import requests, psycopg2
from psycopg2.extras import execute_values

NNDSS = "https://data.cdc.gov/resource/x9gk-5huc.json"
OREGON = "https://data.oregon.gov/resource/rk77-sqhz.json"
CENSUS = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv"
NNDSS_LABELS = ("Chlamydia trachomatis infection", "Gonorrhea", "Syphilis, Primary and secondary", "Syphilis, Congenital")
OREGON_DISEASES = ("Chlamydia", "Gonorrhea", "Early syphilis", "Congenital syphilis", "HIV")
PAGE = 50000

def soql(url, where):
    rows, offset = [], 0
    while True:
        r = requests.get(url, params={"$where": where, "$order": ":id", "$limit": PAGE, "$offset": offset}, timeout=120)
        r.raise_for_status()
        page = r.json()
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE

def num(v):
    return None if v in (None, "", "NA") else float(v)

def clean(v):
    return re.sub(r"\s+", " ", v).strip() if v else v

def day(v):  # Oregon trae '2021:1:03T...' en algunos start
    if not v:
        return None
    y, m, d = re.split(r"[-:]", v.split("T")[0])
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

def in_list(col, vals):
    return f"{col} in (" + ",".join("'" + v.replace("'", "''") + "'" for v in vals) + ")"

def norm_nndss(r):
    return (int(r["year"]), int(r["week"]), r["label"], r["states"], r.get("location1"), r.get("location2"),
            num(r.get("m1")), r.get("m1_flag"), num(r.get("m2")), r.get("m2_flag"),
            num(r.get("m3")), r.get("m3_flag"), num(r.get("m4")), r.get("m4_flag"), r.get("sort_order"))

def norm_oregon(r):
    cases = num(r.get("count_masked"))
    return (int(r["mmwr_year"]), int(r["month"]), day(r.get("report_period_start")), day(r.get("report_period_end")),
            r["disease_name"], r["demographic"], clean(r["demographic_level"]), clean(r.get("geo_name")),
            r.get("geo_unit"), r.get("age_group"), r["confirmation_status"],
            None if cases is None else int(cases), r.get("masked") == "1", r.get("count_label"),
            num(r.get("population")), r.get("pop_source"), day(r.get("run_date")))

def norm_census(row):
    return [(row["NAME"], y, int(row[f"POPESTIMATE{y}"]), row["REGION"], row["DIVISION"])
            for y in range(2020, 2026) if row.get(f"POPESTIMATE{y}")]

def upsert(cur, table, cols, pk, rows):
    upd = ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in pk) + ",ingested_at=now()"
    execute_values(cur, f"INSERT INTO {table} ({','.join(cols)}) VALUES %s "
                        f"ON CONFLICT ({','.join(pk)}) DO UPDATE SET {upd}", rows, page_size=5000)

def main():
    nndss = [norm_nndss(r) for r in soql(NNDSS, in_list("label", NNDSS_LABELS))]
    oregon = [norm_oregon(r) for r in soql(OREGON, in_list("disease_name", OREGON_DISEASES))]
    census = [t for row in csv.DictReader(io.StringIO(requests.get(CENSUS, timeout=120).text)) for t in norm_census(row)]
    assert nndss and oregon and census, "fuente vacía: abortar sin tocar la base"
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        upsert(cur, "raw.nndss_weekly",
               ["year", "week", "label", "states", "location1", "location2", "m1", "m1_flag", "m2", "m2_flag",
                "m3", "m3_flag", "m4", "m4_flag", "sort_order"], ["year", "week", "label", "states"], nndss)
        upsert(cur, "raw.oregon_monthly",
               ["mmwr_year", "month", "report_period_start", "report_period_end", "disease_name", "demographic",
                "demographic_level", "geo_name", "geo_unit", "age_group", "confirmation_status", "cases",
                "is_masked", "count_label", "population", "pop_source", "run_date"],
               ["mmwr_year", "month", "disease_name", "demographic", "demographic_level", "confirmation_status"], oregon)
        upsert(cur, "raw.census_population", ["name", "year", "population", "region", "division"], ["name", "year"], census)
    print(f"nndss={len(nndss)} oregon={len(oregon)} census={len(census)}")

if __name__ == "__main__":
    main()
```
> Nota: tras `clean()`, `"Multnomah  County"` y `"Multnomah County"` pueden colisionar en la PK dentro del mismo batch → `execute_values` falla con "ON CONFLICT DO UPDATE command cannot affect row a second time". Si ocurre, deduplicar con `dict({t[:2]+t[4:7]+t[10:11]: t for t in oregon}.values())` antes del upsert (último gana) y añadir un test que lo cubra.
- [ ] **Step 4:** `pytest tests/test_ingest.py -v` → 5 PASS.
- [ ] **Step 5:** Corrida real: `set -a; . ./.env; set +a; python -m scripts.ingest` → `nndss≈69720 oregon≈25460 census≈396`. Segunda corrida: mismos conteos en `SELECT count(*)` (idempotencia).
- [ ] **Step 6:** Mensaje: `feat(ingest): idempotent loader for NNDSS, Oregon and Census PEP`.

### Task 3: dbt staging, seeds y snapshot

**Files:** Create `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/seeds/{disease_map,state_codes,dim_access}.csv`, `dbt/snapshots/snap_nndss_weekly.sql`, `dbt/models/staging/*`.

**Produces:** `stg_nndss_weekly(year, week, epi_week_key, disease_source_name, state_code, cases_week, max_prev_52w, cum_ytd, cum_ytd_prev, flags…)`, `stg_oregon_monthly(epi_month_key, disease_source_name, demographic_type, demographic_level, county_name, state_code, cases, is_masked, population, confirmation_status)`, `stg_census_population(state_code, year, population, census_region, census_division)`.

- [ ] **Step 1:** `profiles.yml`:
```yaml
sti:
  target: prod
  outputs:
    prod:
      type: postgres
      host: "{{ env_var('PGHOST') }}"
      user: "{{ env_var('PGUSER') }}"
      password: "{{ env_var('PGPASSWORD') }}"
      dbname: "{{ env_var('PGDATABASE') }}"
      port: 5432
      schema: analytics
      sslmode: require
      threads: 4
```
(.env agrega `PGHOST/PGUSER/PGPASSWORD/PGDATABASE`; mismo set en GitHub Secrets.)
`dbt_project.yml`: `name: sti`, `profile: sti`, `models: sti: staging: +materialized: view, +schema: staging; marts: +materialized: table, +schema: marts`.
- [ ] **Step 2:** Seeds:
  - `disease_map.csv`: `source,source_name,disease_key,disease_name,disease_group,pathogen_type,transmission_mode,comparable_across_sources` con filas: NNDSS Chlamydia→`CHL`; Oregon Chlamydia→`CHL`; ambos Gonorrhea→`GON`; NNDSS `Syphilis, Primary and secondary`→`SYP_PS` (`comparable=false`); Oregon `Early syphilis`→`SYP_EARLY` (`comparable=false`, mismo `disease_group=Syphilis`); ambos congénita→`SYP_CONG`; Oregon HIV→`HIV` (Viral).
  - `state_codes.csv`: `state_name_upper,state_code,state_name` para 50 estados + DC + territorios; `NEW YORK CITY→NY`.
  - `dim_access.csv`: `user_principal_name,state_code,county_name` con usuarios ficticios del developer tenant (ej. `ana@<tenant>.onmicrosoft.com,OR,Multnomah County`; `luis@…,CA,*`; `admin@…,*,*`).
- [ ] **Step 3:** `_sources.yml` con `freshness: {warn_after: {count: 8, period: day}, error_after: {count: 15, period: day}}`, `loaded_at_field: ingested_at` en las 3 tablas raw.
- [ ] **Step 4:** `stg_nndss_weekly.sql`: `WHERE location1 IS NOT NULL`, join `state_codes` por `upper(location1)`, `year*100+week AS epi_week_key`, `m1 AS cases_week`, `m2 AS max_prev_52w`, `m3 AS cum_ytd`, `m4 AS cum_ytd_prev`; luego `GROUP BY` estado para sumar NYC dentro de NY (`sum(m1)`, flags con `max`).
  `stg_oregon_monthly.sql`: `mmwr_year*100+month AS epi_month_key`, `demographic AS demographic_type`, `CASE WHEN geo_unit='county' THEN demographic_level END AS county_name`, `'OR' AS state_code`.
  `stg_census_population.sql`: join `state_codes`, `region/division` decodificados.
- [ ] **Step 5:** `snap_nndss_weekly.sql`:
```sql
{% snapshot snap_nndss_weekly %}
{{ config(target_schema='snapshots', unique_key="year||'-'||week||'-'||label||'-'||states",
          strategy='check', check_cols=['m1']) }}
select * from {{ source('raw', 'nndss_weekly') }}
{% endsnapshot %}
```
- [ ] **Step 6:** Tests en `_sources.yml`/staging: `not_null` en `state_code` de `stg_nndss_weekly` (cubre Review Focus #2), `accepted_values` de `demographic_type` (5 valores).
- [ ] **Step 7:** `cd dbt && dbt seed && dbt snapshot && dbt build --select staging` → verde. `dbt source freshness` → pass.
- [ ] **Step 8:** Mensaje: `feat(dbt): staging, seeds and NNDSS revision snapshot`.

### Task 4: dbt marts

**Files:** Create `dbt/models/marts/*.sql`, `_marts.yml`, `exposures.yml`.

**Produces (consumido por Power BI y MCP):**
| Modelo | Grano / columnas clave |
|---|---|
| `dim_disease` | `disease_key` PK, disease_name, disease_group, pathogen_type, transmission_mode, comparable_across_sources |
| `dim_geography` | `geo_key` PK (`state_code` o `state_code||'|'||county_name`), state_code, state_name, county_name (null a nivel estado), geo_level (state/county), census_region, census_division |
| `dim_mmwr_week` | `epi_week_key` PK, mmwr_year, mmwr_week, week_start_date (domingo), week_end_date, is_reference_week |
| `dim_epi_month` | `epi_month_key` PK, mmwr_year, month, period_start, period_end, month_label |
| `dim_demographic` | `demographic_key` PK, demographic_type, demographic_level, sex, age_group, race_group, race_method (alone_or_combo / primary) |
| `fct_nndss_weekly` | `fact_id` PK, epi_week_key, disease_key, geo_key, cases_week, max_prev_52w, cum_ytd, cum_ytd_prev, population (Census año), is_flagged |
| `fct_oregon_monthly` | `fact_id` PK, epi_month_key, disease_key, geo_key, demographic_key, confirmation_status, cases (nullable), is_masked, population |
| `agg_weekly_national` | epi_week_key, disease_key, census_region, sum(cases_week), sum(population) |
| `mart_revisions` | epi_week_key, geo_key, disease_key, first_reported_m1, current_m1, n_revisions, delta (desde `snap_nndss_weekly`) |
| `mart_data_quality` | source, last_ingested_at, max_period, n_rows, pct_masked, pct_flagged, n_states_reporting_last_week |

- [ ] **Step 1:** `dim_mmwr_week`: generar con `generate_series` desde 2021-01-03 en saltos de 7 días; semana MMWR = semana domingo–sábado; el año MMWR es el del miércoles (`extract(isoyear …)` NO sirve: usar `extract(year from week_start + 3)` y `row_number() over (partition by that year order by week_start)`). Test: `mmwr_week BETWEEN 1 AND 53`; `epi_week_key` 202640 → `week_start_date = 2026-10-04` (cuadra con el `reportweekbegin` de Oregon weekly).
- [ ] **Step 2:** `is_reference_week` = `week_end_date = (max semana con datos NNDSS) - 14 días` (ajuste a semana).
- [ ] **Step 3:** Hechos y agregación según tabla. `fct_nndss_weekly.population` = Census del `mmwr_year` (si año > 2025 usar 2025; documentado).
- [ ] **Step 4:** Tests `_marts.yml`: `unique`+`not_null` en todas las PK; `relationships` de cada FK; `accepted_values` en `geo_level`, `demographic_type`; test singular `tests/oregon_county_no_double_count.sql`:
```sql
-- falla si un slice Geography/county tiene más de una fila por mes×enfermedad×condado×status
select epi_month_key, disease_key, geo_key, confirmation_status, count(*)
from {{ ref('fct_oregon_monthly') }} f join {{ ref('dim_demographic') }} d using (demographic_key)
where d.demographic_type = 'Geography'
group by 1,2,3,4 having count(*) > 1
```
  y `tests/agg_matches_fact.sql` (suma de `agg_weekly_national` = suma de `fct_nndss_weekly` por semana×enfermedad).
- [ ] **Step 5:** `exposures.yml`: exposure `sti_surveillance_dashboard` (type dashboard, owner jcbatman@gmail.com) depends_on todas las marts.
- [ ] **Step 6:** `dbt build` → todo verde; `dbt docs generate` muestra el linaje hasta la exposure.
- [ ] **Step 7:** Mensaje: `feat(dbt): star schema marts, aggregation, revisions and data quality`.

### Task 5: GitHub Actions

**Files:** Create `.github/workflows/weekly_ingest.yml`.

- [ ] **Step 1:**
```yaml
name: Weekly Epidemiological Data Ingestion
on:
  schedule: [{ cron: '0 6 * * 4' }]   # jueves 06:00 UTC, un día después de la publicación semanal de NNDSS
  workflow_dispatch:
jobs:
  ingest:
    runs-on: ubuntu-latest
    env:
      DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
      PGHOST: ${{ secrets.PGHOST }}
      PGUSER: ${{ secrets.PGUSER }}
      PGPASSWORD: ${{ secrets.PGPASSWORD }}
      PGDATABASE: ${{ secrets.PGDATABASE }}
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with: { python-version: '3.12', cache: 'pip' }
      - run: pip install -r requirements.txt
      - run: pytest tests -q
      - run: python -m scripts.ingest
      - run: dbt seed --project-dir dbt --profiles-dir dbt
      - run: dbt snapshot --project-dir dbt --profiles-dir dbt
      - run: dbt build --project-dir dbt --profiles-dir dbt
      - run: dbt source freshness --project-dir dbt --profiles-dir dbt
```
- [ ] **Step 2:** Usuario carga Secrets, lanza `workflow_dispatch`; verificar job verde.
- [ ] **Step 3:** Mensaje: `ci: weekly ingest, snapshot and dbt build`.

### Task 6: Modelo semántico Power BI (manual en Desktop, guardado como PBIP)

**Files:** Create `data_model/STI_Surveillance_Model.pbip` (+ TMDL).

- [ ] **Step 1:** Get Data → PostgreSQL (Neon host, DB, `sslmode` require; driver Npgsql integrado). Credenciales quedan en `.pbi/localSettings.json` (gitignored).
- [ ] **Step 2:** Modos: dims = **Dual**; `fct_nndss_weekly`, `fct_oregon_monthly` = **DirectQuery**; `agg_weekly_national`, `mart_revisions`, `mart_data_quality` = **Import**; `dim_access` = Import.
- [ ] **Step 3:** Relaciones 1:* simple: `dim_disease`, `dim_geography` → ambos hechos; `dim_mmwr_week` → `fct_nndss_weekly`/`agg_weekly_national`/`mart_revisions`; `dim_epi_month` → `fct_oregon_monthly`; `dim_demographic` → `fct_oregon_monthly`. `dim_access` sin relación. Marcar `dim_mmwr_week` (columna `week_start_date`) como tabla de fechas.
- [ ] **Step 4:** Manage aggregations en `agg_weekly_national`: `cases_week` Sum → `fct_nndss_weekly[cases_week]`; GroupBy epi_week_key, disease_key, census_region. Ocultar la tabla agg.
- [ ] **Step 5:** Medidas (tabla `_Measures`):
```DAX
Cases NNDSS = SUM ( fct_nndss_weekly[cases_week] )
Population NNDSS =
    SUMX ( VALUES ( dim_geography[geo_key] ),
           CALCULATE ( MAX ( fct_nndss_weekly[population] ) ) )
Rate per 100k NNDSS = DIVIDE ( [Cases NNDSS], [Population NNDSS] ) * 100000

-- Oregon: siempre un solo tipo demográfico (Review Focus #1)
Cases Oregon =
VAR t = SELECTEDVALUE ( dim_demographic[demographic_type], "Geography" )
RETURN CALCULATE ( SUM ( fct_oregon_monthly[cases] ),
                   KEEPFILTERS ( dim_demographic[demographic_type] = t ) )
Population Oregon (unmasked) =
VAR t = SELECTEDVALUE ( dim_demographic[demographic_type], "Geography" )
RETURN CALCULATE ( SUM ( fct_oregon_monthly[population] ),
                   KEEPFILTERS ( dim_demographic[demographic_type] = t ),
                   fct_oregon_monthly[is_masked] = FALSE () )
Rate per 100k Oregon = DIVIDE ( [Cases Oregon], [Population Oregon (unmasked)] ) * 100000
% Suppressed Cells =
DIVIDE ( CALCULATE ( COUNTROWS ( fct_oregon_monthly ), fct_oregon_monthly[is_masked] = TRUE () ),
         COUNTROWS ( fct_oregon_monthly ) )

Cases LY (MMWR aligned) =
VAR y = MAX ( dim_mmwr_week[mmwr_year] ) VAR w = MAX ( dim_mmwr_week[mmwr_week] )
RETURN CALCULATE ( [Cases NNDSS], REMOVEFILTERS ( dim_mmwr_week ),
                   dim_mmwr_week[mmwr_year] = y - 1, dim_mmwr_week[mmwr_week] = w )
Cases LY (SAMEPERIODLASTYEAR) = CALCULATE ( [Cases NNDSS], SAMEPERIODLASTYEAR ( dim_mmwr_week[week_start_date] ) )
YoY % = DIVIDE ( [Cases NNDSS] - [Cases LY (MMWR aligned)], [Cases LY (MMWR aligned)] )

Corridor P75 =
VAR y = MAX ( dim_mmwr_week[mmwr_year] ) VAR w = MAX ( dim_mmwr_week[mmwr_week] )
VAR hist = CALCULATETABLE ( VALUES ( dim_mmwr_week[mmwr_year] ), REMOVEFILTERS ( dim_mmwr_week ),
                            dim_mmwr_week[mmwr_year] >= y - 5, dim_mmwr_week[mmwr_year] < y )
RETURN PERCENTILEX.INC ( hist,
         CALCULATE ( [Cases NNDSS], REMOVEFILTERS ( dim_mmwr_week ),
                     dim_mmwr_week[mmwr_week] = w ), 0.75 )
-- Corridor P25 / P50 iguales con 0.25 / 0.5
Excess over P75 = MAX ( 0, [Cases NNDSS] - [Corridor P75] )
States in Outbreak =
    COUNTROWS ( FILTER ( VALUES ( dim_geography[state_code] ), [Cases NNDSS] > [Corridor P75] ) )
Reference Week = CALCULATE ( MAX ( dim_mmwr_week[epi_week_key] ), dim_mmwr_week[is_reference_week] )
```
> NNDSS ETS empieza en 2022: el corredor de 2026 usa 4 años (2022–2025). Se documenta en el README.
- [ ] **Step 6:** Validar contra SQL: para CA, Gonorrhea, 2024-W52, `Cases NNDSS` = 499 (valor del test API). Para Multnomah, Chlamydia, 2026-M01 confirmed: `Cases Oregon` = 294.
- [ ] **Step 7:** DAX Studio / Performance Analyzer: visual national por semana×enfermedad muestra *aggregation hit*. Captura a `docs/img/agg_hit.png`.
- [ ] **Step 8:** Mensaje: `feat(pbi): composite semantic model, aggregations and epi measures`.

### Task 7: Seguridad RLS + OLS

**Files:** Modify TMDL de roles en `data_model/…SemanticModel/definition/roles/`.

- [ ] **Step 1:** Roles (Desktop → Manage roles):
  - `State_Analyst` (RLS sobre `dim_geography`):
```DAX
VAR allowed = CALCULATETABLE ( VALUES ( dim_access[state_code] ),
                               dim_access[user_principal_name] = USERPRINCIPALNAME () )
RETURN "*" IN allowed || dim_geography[state_code] IN allowed
```
  - `County_Analyst` (RLS condado Oregon; filas a nivel estado se ocultan salvo `*`):
```DAX
VAR allowed = CALCULATETABLE ( VALUES ( dim_access[county_name] ),
                               dim_access[user_principal_name] = USERPRINCIPALNAME () )
RETURN dim_geography[state_code] = "OR"
    && ( "*" IN allowed || dim_geography[county_name] IN allowed )
```
  - `Restricted_Epidemiologist` (OLS, en TE2): `dim_demographic[race_group]`, `dim_demographic[race_method]`, `dim_demographic[age_group]` → None; tabla `mart_revisions` → None.
  - `Restricted_State_Analyst` (RLS de State_Analyst + OLS de Restricted_Epidemiologist en **un mismo rol**, porque no se pueden combinar dos roles).
  - `Admin`: sin filtros.
- [ ] **Step 2:** OLS con TE2: External Tools → Tabular Editor 2 → Roles → rol → Table Permissions / Column permissions → None → Ctrl+S. Revisar diff `.tmdl` (`columnPermission … metadataPermission: none`).
- [ ] **Step 3:** Probar con View as en Desktop: cada rol + UPN de `dim_access`. Esperado: State_Analyst `luis@…` solo ve CA; County_Analyst `ana@…` solo Multnomah; Restricted ve error en el visual de raza. Capturas en `docs/img/rls_*.png`, `docs/img/ols_*.png`.
- [ ] **Step 4:** Servicio: workspace con trial de Fabric o developer tenant de M365, publicar, asignar usuarios a roles, "Test as role". Capturas.
- [ ] **Step 5:** Mensaje: `feat(security): dynamic RLS (state/county) and OLS roles`.

### Task 8: Servidor MCP + rol read-only

**Files:** Create `mcp/mcp_server.py`, `mcp/requirements.txt` (`mcp`, `psycopg2-binary`), `sql/mcp_reader_role.sql`.

- [ ] **Step 1:** `sql/mcp_reader_role.sql`:
```sql
CREATE ROLE mcp_reader LOGIN PASSWORD :'pw';   -- psql -v pw=...
ALTER ROLE mcp_reader SET default_transaction_read_only = on;
ALTER ROLE mcp_reader SET statement_timeout = '10s';
GRANT USAGE ON SCHEMA analytics_marts TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics_marts TO mcp_reader;
REVOKE SELECT ON analytics_marts.dim_demographic, analytics_marts.mart_revisions FROM mcp_reader;
GRANT SELECT (demographic_key, demographic_type, demographic_level, sex) ON analytics_marts.dim_demographic TO mcp_reader;
```
(Esquema real = `analytics_marts` por el `+schema` de dbt; verificar con `\dn`.)
- [ ] **Step 2:** `mcp_server.py` = código de §6 de `powerbi_consolidado.md`, cambiando el regex OLS a `r"\b(race_group|race_method|age_group|mart_revisions)\b"`, la ruta TMDL a `data_model/STI_Surveillance_Model.SemanticModel/definition` y `DATABASE_URL` → `MCP_DATABASE_URL` (conexión de `mcp_reader`).
- [ ] **Step 3:** Verificar con Claude Desktop (o `mcp dev mcp/mcp_server.py`):
  - `SELECT disease_key, sum(cases_week) FROM analytics_marts.fct_nndss_weekly GROUP BY 1` → JSON.
  - `DELETE FROM …` → bloqueado por regex; además `SET`/DML directo con el rol → `cannot execute … in a read-only transaction`.
  - `SELECT race_group FROM analytics_marts.dim_demographic` → `ERROR [OLS-HIPAA]`; sin regex → `permission denied for column`.
  Capturas `docs/img/mcp_*.png`.
- [ ] **Step 4:** Mensaje: `feat(mcp): read-only MCP server with OLS guardrails`.

### Task 9: Informe, tema y README

**Files:** Create `theme/dark_accessible.json`, `README.md`; Modify `.Report/`.

- [ ] **Step 1:** Tema oscuro WCAG AA (contraste ≥4.5:1, paleta daltónica tipo Okabe-Ito), alt text y tab order en todos los visuales.
- [ ] **Step 2:** Páginas: 1 Resumen nacional (KPIs NNDSS: casos, tasa/100k, YoY, estados en brote, semana de referencia) · 2 Mapa estados (tasa) · 3 Ranking (tasa, exceso) · 4 Corredor endémico · 5 Oregon por condado (tasa, % suprimido) · 6 Demografía Oregon (sexo/edad/raza; visuales bloqueados por OLS) · 7 Calidad de datos (`mart_data_quality`, `mart_revisions`, freshness).
- [ ] **Step 3:** README: arquitectura, fuentes y endpoints testeados, decisiones (Dual, agg, RLS+OLS en un rol, no publicar), límites (marginales Oregon no cruzables, enmascarado <6, NNDSS ETS desde 2022, sífilis P&S ≠ early, población 2026 = PEP 2025, `Asymptomatic_Ratio` eliminado).
- [ ] **Step 4:** Mensaje: `docs: report pages, accessible theme and README`.

---

## Verification (end-to-end)
1. `pytest tests -q` → verde.
2. `python -m scripts.ingest` dos veces → mismos `count(*)` en `raw.*`.
3. `dbt seed && dbt snapshot && dbt build && dbt source freshness` → verde; `dbt docs generate` con exposure.
4. GitHub Action manual → verde.
5. Power BI: 499 (CA/GON/2024-W52) y 294 (Multnomah/CHL/2026-M01) cuadran con SQL; aggregation hit en DAX Studio.
6. View as por rol (Desktop + servicio) con capturas.
7. MCP: consulta OK, DML bloqueado, OLS bloqueado.
8. `git log -p | grep -iE 'password|neon.tech'` → vacío.

## Execution
Recomendado **Native** (tasks secuenciales con dependencia fuerte de esquemas; Tasks 6–7 son manuales en Desktop y no se delegan a subagentes).
