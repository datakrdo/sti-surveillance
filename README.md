# STI Surveillance Platform

Pipeline gratuito de vigilancia epidemiológica de ETS en EE.UU.: CDC NNDSS + Oregon → Postgres (Neon) → dbt → modelo compuesto Power BI (PBIP/TMDL) con RLS/OLS → servidor MCP read-only.

## Fuentes (probadas el 2026-10-14)
| Fuente | Endpoint | Grano |
|---|---|---|
| CDC NNDSS Weekly | `data.cdc.gov/resource/x9gk-5huc` | semana × estado × enfermedad |
| Oregon Monthly Reportable Disease | `data.oregon.gov/resource/rk77-sqhz` | mes × condado/sexo/edad/raza × enfermedad |
| Census PEP 2025 | `www2.census.gov/.../NST-EST2025-ALLDATA.csv` | estado × año |

## Cómo correrlo
```
cp .env.example .env   # completar con Neon
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
psql "$DATABASE_URL" -f sql/raw_schema.sql
set -a; . ./.env; set +a
.venv/bin/python -m scripts.ingest
cd dbt && ../.venv/bin/dbt seed && ../.venv/bin/dbt snapshot && ../.venv/bin/dbt build
```

## Límites
- Oregon publica marginales: no se pueden cruzar sexo × edad × raza.
- Celdas con menos de 6 casos vienen enmascaradas; las tasas se calculan solo sobre celdas visibles.
- HIV existe solo en Oregon; NNDSS no lo publica.
- Sífilis primaria/secundaria (NNDSS) y sífilis temprana (Oregon) no son comparables.
- NNDSS ETS empieza en 2022: el corredor endémico usa los años disponibles.
- La población de 2026 usa la estimación Census de 2025.
- `Asymptomatic_Ratio` del plan original se eliminó: no existe en ninguna fuente.
- RLS y OLS no se combinan entre roles: quien necesite ambas usa un único rol.
