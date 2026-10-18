🇬🇧 [English](README.md) · 🇪🇸 [Español](README_es.md)

# sti-surveillance 🧬

**¿Puede un stack gratuito mantener al día los datos de vigilancia de infecciones de transmisión sexual (ITS), ser honesto sobre sus vacíos y ser seguro para dárselo a un asistente de IA?**

Un pipeline semanal para clamidia, gonorrea, sífilis y VIH en Estados Unidos. Combina dos fuentes abiertas: las notificaciones semanales nacionales del CDC (NNDSS) y los datos de enfermedades de notificación obligatoria de Oregon, que añaden condado, sexo, edad y raza. Los datos llegan a Postgres (Neon), dbt los modela en un esquema en estrella y un servidor MCP de solo lectura permite que una IA los consulte sin poder modificarlos ni leer columnas restringidas. Encima hay un modelo compuesto de Power BI con seguridad a nivel de fila y de objeto y un informe bilingüe de 7 páginas, y una demo estática gratuita más un MCP remoto de solo lectura permiten explorarlo (ver [Demo en vivo](#demo-en-vivo-)).

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
- Power BI (PBIP/TMDL), Tabular Editor 2, DAX Studio
- Sitio estático (JS puro, SVG), GitHub Pages, Cloudflare Workers, Node 22

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
- **Modelo compuesto en Power BI.** Hechos en DirectQuery, cinco dimensiones en Dual y una agregación Import pequeña (`agg_weekly_national`). `dim_geography` es Import y no Dual: el editor de roles rechaza la seguridad por fila sobre una tabla Dual que referencia `dim_access`, que es Import.
- **Tasas en persona-años.** La población es anual y los períodos de Oregon duran 28 o 35 días, así que las tasas dividen por población × tiempo sumados (anualizadas), nunca por una sola población.
- **Cero no es dato faltante.** En NNDSS un `-` significa sin casos reportados y se carga como 0; solo `U` queda `NULL` (213 filas, Maryland y Ohio). El total estatal de Oregon es un corte propio, `Statewide`, para que la suma de condados no duplique.
- **Un solo rol por usuario.** La seguridad por fila y por objeto viven juntas en `Restricted_State_Analyst`; `demographic_level` también está restringida porque repite los valores de `age_group` y `race_group`.
- **Rol `pbi_reader` de solo lectura** para Power BI; los permisos los reaplica el mismo hook de dbt que los del MCP.
- **Versiones fijadas.** Sin fijar `dbt-core`, pip eligió una beta de `dbt` sin soporte de postgres y el primer run de CI falló.

## Cómo funciona 🏗️

```
CDC NNDSS (Socrata) ─┐
Oregon (Socrata)     ─┼─► scripts/ingest.py ─► Neon raw.* ─► dbt ─► analytics_marts.* ─► Power BI
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

- `dbt build`: pasan 70 de 70 nodos.
- Contraste con las APIs: gonorrea de California en la semana 2024-W52 = 499 casos y clamidia de Multnomah en 2026-M01 = 294, ambos iguales a la fuente.
- La vista del MCP da los mismos totales que una consulta independiente para las cinco enfermedades.
- La ingesta es idempotente: dos corridas seguidas dejan los mismos conteos.
- El workflow semanal corre en verde de punta a punta (pytest, ingesta, seed, snapshot, build, frescura) en unos 1 min 17 s.
- Modelo de Power BI contrastado con anclas en SQL: 12 conteos de tablas, totales de NNDSS y Oregon, tasas anualizadas (clamidia de CA 2024 = 259,434 por 100 mil), interanual en dos formas (alineada por MMWR y `SAMEPERIODLASTYEAR`, que difieren exactamente en los 2.833 casos de la semana 2025-W1), el corredor endémico y los cortes de Oregon (clamidia 80.587 por condado, 82.066 estatal).
- Acierto de la agregación confirmado de tres maneras: Performance Analyzer, DAX Studio (`RewriteAttempted` con coincidencia y escaneo de `agg_weekly_national`, sin SQL) y revocando `SELECT` sobre el hecho a `pbi_reader`: el visual agregado siguió funcionando y el otro falló.
- Seguridad por fila: la matriz de 10 casos en *View as* coincide y un usuario desconocido no ve nada. La seguridad por objeto bloquea `race_group`, `age_group`, `demographic_level` y `mart_revisions` en *View as*, mientras `sex` sigue funcionando.
- Informe: 7 páginas en español e inglés sobre un solo modelo semántico, con el tema oscuro accesible (tests de contraste en `tests/test_theme_contrast.py`).
- Protecciones del MCP verificadas desde Python: una consulta válida devuelve JSON, el DML y las columnas restringidas se bloquean, y la propia base rechaza escrituras y el esquema `raw`.

## Demo en vivo 🌐

Una versión pública y gratuita, sin base de datos ni claves en línea:

- **Sitio estático** (GitHub Pages, `site/`): réplica de 3 vistas del informe (Resumen, Mapa, Corredor) en español e inglés, con 5 preguntas de ejemplo calculadas en el navegador. `?tour=1` rota las vistas solo.
- **MCP remoto de solo lectura** (Cloudflare Workers, `worker/`): 6 herramientas con parámetros validados y sin SQL libre. Lee el mismo JSON agregado que el sitio. Se conecta como conector personalizado en Claude (disponible en todos los planes; el gratuito permite uno) o en cualquier cliente con soporte de MCP remoto: `https://sti-surveillance-mcp.<subdominio>.workers.dev/mcp`.
- **Qué contiene:** solo NNDSS (clamidia, gonorrea, sífilis primaria/secundaria y congénita) por estado y semana, con las mismas definiciones del modelo. El dataset del Oregon Health Authority (condados, demografía) y las revisiones no se publican (las filas del estado de Oregon de NNDSS sí); siguen en el informe de Power BI y en el MCP local de laboratorio (`mcp/`, rol `mcp_reader`).
- **Cómo se actualiza:** el workflow semanal exporta `site/data/*.json` desde Neon y vuelve a publicar Pages; el Worker lee ese JSON, así que no hay que redesplegarlo. Las pruebas comparan las cifras del sitio con las anclas SQL antes de publicar.
- **Fuentes y avisos:** CDC NNDSS (datos provisionales) y U.S. Census Bureau. Proyecto independiente, sin afiliación con estas entidades.

## Limitaciones ⚠️

- No hay cruces demográficos (sexo × edad × raza); Oregon no los publica.
- Las series de ITS de NNDSS empiezan en 2022, así que un corredor endémico tendría solo los años disponibles.
- La población de 2026 usa la estimación Census de 2025.
- `dim_access.csv` trae usuarios ficticios con el dominio `TENANT`; hay que reemplazarlo antes de probar la seguridad a nivel de fila.
- `Asymptomatic_Ratio` del plan original se eliminó: ninguna fuente lo tiene.
- La seguridad por fila y por objeto se probó solo en Power BI Desktop (*View as*). La prueba en el servicio (copia del modelo con Import, workspace privado) no se hizo: no hay tenant de Microsoft 365.
- Asignar a un usuario un rol con filtros de fila y otro que solo restringe objetos une los filtros de fila: `State_Analyst` + `Restricted_Epidemiologist` mostró 93 geografías en vez de 38, y la restricción de objetos se mantuvo.
- `SAMEPERIODLASTYEAR` sobre una sola semana devuelve vacío porque los datos son semanales; el informe usa la comparación alineada por MMWR.
- El corredor endémico usa los años con datos (desde 2022) y la última semana de gonorrea de CA (2026-W40) parece un reporte parcial (hipótesis).
- `Person-Years Oregon` itera por meses para funcionar bien en DirectQuery y ya no descarta las 34 filas visibles con `cases` vacío, así que puede diferir levemente en otros cortes.
- El error `[OLS-HIPAA]` del MCP sale de un filtro de texto en `mcp_server.py` (busca `race_group`, `age_group`, `race_method`, `mart_revisions`), así que es una guarda de demostración, no un permiso. La barrera real es el rol `mcp_reader`: no tiene `SELECT` sobre `dim_demographic`, `fct_oregon_monthly` ni `mart_revisions` (verificado: `permission denied`), es de solo lectura y tiene un timeout de 10 s.

## Estructura

```
sti-surveillance/
├── .github/workflows/weekly_ingest.yml   # pytest → ingesta → dbt seed/snapshot/build → frescura → Pages
├── .github/workflows/pages.yml           # exporta agregados públicos, verifica anclas, publica site/
├── scripts/ingest.py                     # descarga, normaliza, upsert
├── sql/                                  # esquema raw, rol mcp_reader
├── dbt/
│   ├── models/staging, models/marts      # vistas y tablas, con tests
│   ├── seeds/                            # disease_map, state_codes, dim_access
│   ├── snapshots/snap_nndss_weekly.sql
│   └── tests/                            # tests singulares de grano
├── mcp/mcp_server.py
├── data_model/                           # proyecto Power BI (PBIP/TMDL), informes ES y EN
├── theme/dark_accessible.json            # tema oscuro accesible
├── scripts/export_public.py              # agregados públicos para la demo
├── site/                                 # dashboard estático bilingüe (GitHub Pages)
├── worker/                               # MCP remoto de solo lectura (Cloudflare Workers)
├── tests/                                # ingesta, contraste del tema, layout del informe, exportador, sin host real de la base
└── docs/
    ├── PROJECT.md                        # diseño, decisiones, anclas, demo, pendientes
    └── powerbi_windows_runbook.md        # pasos manuales en Power BI Desktop
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

Demo pública, en local: `python -m scripts.export_public` (escribe `site/data/`) y luego `python3 -m http.server -d site 8000`. El MCP remoto: `cd worker && npm install && npx wrangler dev`.

El CI necesita los secrets del repo `NEON_DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD` y `PGDATABASE`.

## Tests

```bash
.venv/bin/pytest -q                       # 38 tests: ingesta, contraste del tema, layout del informe, exportador, sin host real de la base
node --test "site/js/*.test.mjs"          # 15 tests: cálculos contra las anclas SQL, sitio
(cd worker && npm test)                   # 11 tests: herramientas del MCP remoto
cd dbt && ../.venv/bin/dbt build --profiles-dir .
```

## Fases ✅

- [x] Búsqueda de fuentes y prueba en vivo de las APIs
- [x] Ingesta idempotente con tests unitarios
- [x] dbt: staging, esquema en estrella, snapshot, tests y exposure
- [x] Workflow semanal de GitHub Actions
- [x] Servidor MCP de solo lectura con vista de un solo corte
- [x] MCP probado desde Claude Code (consulta válida, bloqueo de DML, bloqueo de columna restringida, recurso de esquema)
- [x] Modelo semántico de Power BI: relaciones, medidas DAX, agregaciones
- [x] Seguridad a nivel de fila por condado y de objeto sobre raza, edad y revisiones, probada con *View as*
- [ ] Mismas pruebas de seguridad en el servicio de Power BI (requiere tenant)
- [x] Tema oscuro accesible y el informe de 7 páginas (falta la revisión manual de accesibilidad)
- [x] Sitio estático bilingüe y MCP remoto (código y tests)
- [ ] Desplegar Pages y el Worker, y probar el MCP público desde Claude
- [ ] Abrir ambos `.pbip` en Desktop tras el rediseño del informe
- [ ] Capturas en `docs/img/` (parcial)

## Fuera de alcance (a propósito)

- Una serie nacional de VIH: la única fuente gratuita con API y datos recientes es Oregon.
- Carga incremental y un orquestador: la carga completa tarda cerca de un minuto.
- Publicar el informe con *Publish to web* de Power BI: expone los datos y no soporta seguridad a nivel de fila.
- Imputar las celdas enmascaradas.

## Licencia

MIT — ver el archivo `LICENSE`. Datos: CDC (Office of Public Health Data, Surveillance, and Technology), Oregon Health Authority (atribuida como "OHA PHD ACDP") y U.S. Census Bureau. Los dos datasets de Socrata no declaran licencia en sus metadatos, así que conviene revisar los términos de cada portal antes de redistribuir los datos.
