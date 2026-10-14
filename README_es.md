🇬🇧 [English](README.md) · 🇪🇸 [Español](README_es.md)

# sti-surveillance 🧬

**¿Puede un stack gratuito mantener al día los datos de vigilancia de infecciones de transmisión sexual (ITS), ser honesto sobre sus vacíos y ser seguro para dárselo a un asistente de IA?**

Un pipeline semanal para clamidia, gonorrea, sífilis y VIH en Estados Unidos. Combina dos fuentes abiertas: las notificaciones semanales nacionales del CDC (NNDSS) y los datos de enfermedades de notificación obligatoria de Oregon, que añaden condado, sexo, edad y raza. Los datos llegan a Postgres (Neon), dbt los modela en un esquema en estrella y un servidor MCP de solo lectura permite que una IA los consulte sin poder modificarlos ni leer columnas restringidas. Un modelo de Power BI con seguridad a nivel de fila y de objeto está diseñado pero todavía no construido (ver [Fases](#fases-)).

Fuentes: [CDC NNDSS Weekly](https://data.cdc.gov/resource/x9gk-5huc), [Oregon Monthly Reportable Disease](https://data.oregon.gov/resource/rk77-sqhz) y [Census PEP 2025](https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv). Todas gratuitas y sin API key.

## Leer antes de usar los números ⚠️

- **Oregon publica un solo corte por fila** (condado, o sexo, o edad, o raza), nunca un cruce. Sumar todos los cortes cuenta cada caso unas 5 veces: la clamidia suma 500.312 con todos los cortes y 80.587 solo con condados.
- **El 70,7 % de las filas de Oregon están enmascaradas** (menos de 6 casos). `cases` queda en `NULL`, nunca en cero, así que las sumas por condado subestiman el total estatal.
- **Los conteos de NNDSS son provisionales** y se revisan después de publicarse; el snapshot registra cada cambio.
- **El VIH existe solo en Oregon.** NNDSS no lo publica, así que aquí no hay serie nacional de VIH.
- **Sífilis primaria y secundaria (NNDSS) y sífilis temprana (Oregon) son definiciones distintas** y no son comparables.

## Herramientas 🛠️

- Python 3.12, requests, psycopg2, pytest
- Neon Postgres, dbt-core 1.12 + dbt-postgres 1.11
- GitHub Actions (semanal), MCP Python SDK 2.3
- Power BI (PBIP/TMDL) y Tabular Editor 2 — planificados

## Habilidades 🧠

- Ingesta desde APIs abiertas a un warehouse: SoQL paginado, upsert idempotente por claves naturales y una guarda contra fuentes vacías que aborta antes de tocar la base
- Modelado dimensional con dbt: tests `unique`/`relationships`, tests singulares que atrapan doble conteo, un snapshot que registra revisiones y una exposure para el linaje
- Control de divulgación estadística: supresión de celdas pequeñas conservada como `NULL` más una marca
- Acceso seguro de una IA a una base de datos: rol de solo lectura, permisos reaplicados por un hook de dbt, una vista de un solo corte y un regex solo como segunda línea
- Depuración de CI: rastreé un run fallido hasta una dependencia sin fijar que resolvió a una beta

## Decisiones de diseño 🧭

- **Dos fuentes, no una.** Ninguna API gratuita trae ITS recientes con demografía: NNDSS es nacional y semanal pero sin demografía ni VIH; Oregon tiene ambos. Se descartaron otros portales por antigüedad (California termina en 2021, Illinois en 2016, el VIH de NYC es anual hasta 2022) o por no tener API (AtlasPlus).
- **Carga completa con upsert, no incremental.** Cada corrida trae unas 95.000 filas en cerca de un minuto y hace upsert por clave, así que repetirla es idempotente. La lógica incremental sumaría complejidad sin beneficio a este tamaño. Solo `snap_nndss_weekly` guarda historia entre corridas.
- **Semanal, no diario.** NNDSS publica cada semana, Oregon declara frecuencia mensual y Census es anual. El workflow corre los jueves 06:00 UTC; la frescura de dbt avisa a los 8 días y da error a los 15.
- **Las celdas enmascaradas quedan en `NULL`.** Nunca se imputan, y las tasas deben usar solo celdas visibles.
- **El MCP ve un solo corte.** `mcp_oregon_county_monthly` tiene solo condados y el corte `Geography`, así que cualquier `SUM` es aditivo. El rol no tiene acceso al hecho multicorte ni a `dim_demographic`.
- **New York City se suma a NY** para coincidir con Census; `max_prev_52w` de NY es una suma y solo informativo.
- **Versiones fijadas.** Sin fijar `dbt-core`, pip eligió una beta de `dbt` sin soporte de postgres y el primer run de CI falló.

## Cómo funciona 🏗️

```
CDC NNDSS (Socrata) ─┐
Oregon (Socrata)     ─┼─► scripts/ingest.py ─► Neon raw.* ─► dbt ─► analytics_marts.* ─► Power BI (planificado)
Census PEP (CSV)     ─┘     (GitHub Actions, semanal)         │                    └─► servidor MCP (solo lectura)
                                                              └─ snapshot de NNDSS m1 → mart_revisions
```

`analytics_marts` contiene `dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, los hechos `fct_nndss_weekly` y `fct_oregon_monthly`, `agg_weekly_national`, `mart_revisions`, `mart_data_quality` y la vista del MCP. Los ids de hechos son claves `md5` en texto.

El servidor MCP (`mcp/mcp_server.py`) expone una tool de SQL y el TMDL como resource. La protección tiene tres capas: el rol Postgres `mcp_reader` (solo lectura, timeout de 10 s, permisos solo sobre `analytics_marts`), sin acceso al hecho multicorte, a `dim_demographic` ni a `mart_revisions`, y un regex sobre DML y nombres restringidos.

## Fuentes de datos 📎

| Fuente | Endpoint | Grano | Filas cargadas |
|---|---|---|---|
| CDC NNDSS Weekly | `data.cdc.gov/resource/x9gk-5huc` | semana × estado × enfermedad | 69.720 |
| Oregon Monthly Reportable Disease | `data.oregon.gov/resource/rk77-sqhz` | mes × (condado, sexo, edad o raza) × enfermedad | 25.125 |
| Census PEP 2025 | `NST-EST2025-ALLDATA.csv` | estado × año | 396 |

Cadencia vista el 2026-10-14: NNDSS semanal, Oregon declara mensual (se regeneró ese día junto con su dataset semanal), Census anual. Solo se observó una fecha de publicación por fuente, así que el día de la semana de NNDSS no está confirmado.

## Resultados 📊

- `dbt build`: pasan 57 de 58 nodos; el restante es el snapshot, un no-op. Sin avisos de deprecación.
- Contraste con las APIs: gonorrea de California en la semana 2024-W52 = 499 casos y clamidia de Multnomah en 2026-M01 = 294, ambos iguales a la fuente.
- La vista del MCP da los mismos totales que una consulta independiente para las cinco enfermedades.
- La ingesta es idempotente: dos corridas seguidas dejan los mismos conteos.
- El workflow semanal corre en verde de punta a punta (pytest, ingesta, seed, snapshot, build, frescura) en unos 1 min 17 s.
- Protecciones del MCP verificadas desde Python: una consulta válida devuelve JSON, el DML y las columnas restringidas se bloquean, y la propia base rechaza escrituras y el esquema `raw`.

## Limitaciones ⚠️

- No hay cruces demográficos (sexo × edad × raza); Oregon no los publica.
- Las series de ITS de NNDSS empiezan en 2022, así que un corredor endémico tendría solo los años disponibles.
- La población de 2026 usa la estimación Census de 2025.
- `dim_access.csv` trae usuarios ficticios con el dominio `TENANT`; hay que reemplazarlo antes de probar la seguridad a nivel de fila.
- `Asymptomatic_Ratio` del plan original se eliminó: ninguna fuente lo tiene.
- La seguridad a nivel de fila y de objeto no se puede repartir en dos roles para un mismo usuario; quien necesite ambas recibe un único rol combinado.

## Estructura

```
sti-surveillance/
├── .github/workflows/weekly_ingest.yml   # pytest → ingesta → dbt seed/snapshot/build → frescura
├── scripts/ingest.py                     # descarga, normaliza, upsert
├── sql/                                  # esquema raw, rol mcp_reader
├── dbt/
│   ├── models/staging, models/marts      # vistas y tablas, con tests
│   ├── seeds/                            # disease_map, state_codes, dim_access
│   ├── snapshots/snap_nndss_weekly.sql
│   └── tests/                            # tests singulares de grano
├── mcp/mcp_server.py
├── tests/test_ingest.py
└── docs/superpowers/                     # spec de diseño y plan de implementación
```

## Inicio rápido 🚀

Requiere Python 3.12 o superior y un proyecto Neon (sin el connection pooler).

```bash
cp .env.example .env     # completar DATABASE_URL, PGHOST, PGUSER, PGPASSWORD, PGDATABASE
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r mcp/requirements.txt
# cargar .env (las URLs de Neon pueden traer '&', por eso `source` falla)
while IFS='=' read -r k v || [[ -n "$k" ]]; do [[ -z "$k" || "$k" == \#* ]] && continue; export "$k=$v"; done < .env
psql "$DATABASE_URL" -f sql/raw_schema.sql
.venv/bin/python -m scripts.ingest
cd dbt && ../.venv/bin/dbt seed --profiles-dir . && ../.venv/bin/dbt snapshot --profiles-dir . && ../.venv/bin/dbt build --profiles-dir .
```

Rol del MCP, una sola vez: `psql "$DATABASE_URL" -v pw="'<contraseña>'" -f sql/mcp_reader_role.sql` y guardar su URL en `.env` como `MCP_DATABASE_URL`. Los permisos los aplica el hook `on-run-end` de dbt en cada build.

El CI necesita los secrets del repo `NEON_DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD` y `PGDATABASE`.

## Tests

```bash
.venv/bin/pytest tests -q      # 6 tests sobre los normalizadores y la deduplicación
cd dbt && ../.venv/bin/dbt build --profiles-dir .
```

## Fases ✅

- [x] Búsqueda de fuentes y prueba en vivo de las APIs
- [x] Ingesta idempotente con tests unitarios
- [x] dbt: staging, esquema en estrella, snapshot, tests y exposure
- [x] Workflow semanal de GitHub Actions
- [x] Servidor MCP de solo lectura con vista de un solo corte
- [ ] MCP probado desde Claude Desktop (consulta válida, bloqueo de DML, bloqueo de columna restringida)
- [ ] Modelo semántico de Power BI: relaciones, medidas DAX, agregaciones
- [ ] Seguridad a nivel de fila por condado y de objeto sobre raza, edad y revisiones, probada con *View as*
- [ ] Tema oscuro accesible y el informe de 7 páginas
- [ ] Capturas en `docs/img/`

## Fuera de alcance (a propósito)

- Una serie nacional de VIH: la única fuente gratuita con API y datos recientes es Oregon.
- Carga incremental y un orquestador: la carga completa tarda cerca de un minuto.
- Publicar el informe con *Publish to web* de Power BI: expone los datos y no soporta seguridad a nivel de fila.
- Imputar las celdas enmascaradas.

## Licencia

MIT — ver el archivo `LICENSE`. Datos: CDC (Office of Public Health Data, Surveillance, and Technology), Oregon Health Authority (atribuida como "OHA PHD ACDP") y U.S. Census Bureau. Los dos datasets de Socrata no declaran licencia en sus metadatos, así que conviene revisar los términos de cada portal antes de redistribuir los datos.
