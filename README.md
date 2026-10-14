🇬🇧 [English](README.md) · 🇪🇸 [Español](README_es.md)

# sti-surveillance 🧬

**Can a free-tier stack keep sexually transmitted infection (STI) surveillance data current, honest about its gaps, and safe to hand to an AI assistant?**

A weekly pipeline for chlamydia, gonorrhea, syphilis and HIV in the United States. It combines two open sources: CDC's national weekly notifications (NNDSS) and Oregon's reportable-disease data, which adds county, sex, age and race. Data lands in Postgres (Neon), dbt models it into a star schema, and a read-only MCP server lets an AI query it without being able to change it or read restricted columns. A Power BI model with row- and object-level security is designed but not built yet (see [Phases](#phases-)).

Sources: [CDC NNDSS Weekly](https://data.cdc.gov/resource/x9gk-5huc), [Oregon Monthly Reportable Disease](https://data.oregon.gov/resource/rk77-sqhz) and [Census PEP 2025](https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv). All free, no API key.

## Read this before using the numbers ⚠️

- **Oregon publishes one cut per row** (county, or sex, or age, or race), never a cross of them. Adding all cuts counts each case about 5 times: chlamydia sums to 500,312 across every cut and to 80,587 across counties only.
- **70.7% of Oregon rows are masked** (fewer than 6 cases). `cases` stays `NULL`, never zero, so county sums understate the state total.
- **NNDSS counts are provisional** and get revised after publication; the snapshot records every change.
- **HIV exists only in Oregon.** NNDSS does not publish it, so there is no national HIV series here.
- **Primary and secondary syphilis (NNDSS) and early syphilis (Oregon) are different definitions** and are not comparable.

## Tools 🛠️

- Python 3.12, requests, psycopg2, pytest
- Neon Postgres, dbt-core 1.12 + dbt-postgres 1.11
- GitHub Actions (weekly), MCP Python SDK 2.3
- Power BI (PBIP/TMDL) and Tabular Editor 2 — planned

## Skills 🧠

- Ingestion from open APIs into a warehouse: paginated SoQL, idempotent upsert on natural keys, an empty-source guard that aborts before touching the database
- Dimensional modeling with dbt: `unique`/`relationships` tests, singular tests that catch double counting, a snapshot that tracks revisions, an exposure for lineage
- Statistical disclosure control: small-cell suppression kept as `NULL` plus a flag
- Safe AI access to a database: read-only role, grants re-applied by a dbt hook, a single-cut view, and a regex as a second line only
- CI debugging: traced a failing run to an unpinned dependency that resolved to a beta

## Design decisions 🧭

- **Two sources, not one.** No single free API has recent STI data with demographics: NNDSS is national and weekly but has no demographics or HIV; Oregon has both. Other portals were ruled out by freshness (California ends in 2021, Illinois in 2016, NYC HIV is annual to 2022) or lack of an API (AtlasPlus).
- **Full load with upsert, not incremental.** Each run pulls about 95,000 rows in around a minute and upserts by key, so reruns are idempotent. Incremental logic would add complexity for no gain at this size. Only `snap_nndss_weekly` keeps history between runs.
- **Weekly, not daily.** NNDSS publishes weekly, Oregon declares monthly and Census is annual. The workflow runs Thursdays 06:00 UTC; dbt freshness warns at 8 days and errors at 15.
- **Masked cells stay `NULL`.** They are never imputed, and rates must use visible cells only.
- **The MCP sees one cut.** `mcp_oregon_county_monthly` holds counties and the `Geography` cut only, so any `SUM` is additive. The role has no access to the multi-cut fact or to `dim_demographic`.
- **New York City is folded into NY** to match Census; `max_prev_52w` for NY is a sum and informative only.
- **Pinned versions.** Without a `dbt-core` pin, pip picked a beta `dbt` with no postgres support and the first CI run failed.

## How it works 🏗️

```
CDC NNDSS (Socrata) ─┐
Oregon (Socrata)     ─┼─► scripts/ingest.py ─► Neon raw.* ─► dbt ─► analytics_marts.* ─► Power BI (planned)
Census PEP (CSV)     ─┘     (GitHub Actions, weekly)          │                    └─► MCP server (read-only)
                                                              └─ snapshot of NNDSS m1 → mart_revisions
```

`analytics_marts` holds `dim_disease`, `dim_geography`, `dim_mmwr_week`, `dim_epi_month`, `dim_demographic`, the facts `fct_nndss_weekly` and `fct_oregon_monthly`, `agg_weekly_national`, `mart_revisions`, `mart_data_quality` and the MCP view. Fact ids are text `md5` keys.

The MCP server (`mcp/mcp_server.py`) exposes one SQL tool and the TMDL as a resource. Protection comes in three layers: the Postgres role `mcp_reader` (read-only, 10 s timeout, grants only on `analytics_marts`), no access to the multi-cut fact, `dim_demographic` or `mart_revisions`, and a regex on DML and restricted names.

## Data sources 📎

| Source | Endpoint | Grain | Rows loaded |
|---|---|---|---|
| CDC NNDSS Weekly | `data.cdc.gov/resource/x9gk-5huc` | week × state × disease | 69,720 |
| Oregon Monthly Reportable Disease | `data.oregon.gov/resource/rk77-sqhz` | month × (county, sex, age or race) × disease | 25,125 |
| Census PEP 2025 | `NST-EST2025-ALLDATA.csv` | state × year | 396 |

Cadence seen on 2026-10-14: NNDSS weekly, Oregon declared monthly (it regenerated alongside its weekly dataset that day), Census annual. Only one publication date per source was observed, so the NNDSS weekday is not confirmed.

## Results 📊

- `dbt build`: 57 of 58 nodes pass; the remaining one is the snapshot, a no-op. No deprecation warnings.
- Cross-checks against the APIs: California gonorrhea in week 2024-W52 = 499 cases and Multnomah chlamydia in 2026-M01 = 294, both matching the source.
- The MCP view gives the same totals as an independent query for all five diseases.
- Ingestion is idempotent: two consecutive runs leave identical row counts.
- The weekly workflow runs green end to end (pytest, ingest, seed, snapshot, build, freshness) in about 1 min 17 s.
- MCP guardrails verified from Python: a valid query returns JSON, DML and restricted columns are blocked, and the database refuses writes and the `raw` schema on its own.

## Limitations ⚠️

- No demographic crosses (sex × age × race); Oregon does not publish them.
- NNDSS STI series start in 2022, so an endemic corridor would have only the available years.
- 2026 population uses the 2025 Census estimate.
- `dim_access.csv` has fictional users on a `TENANT` domain; replace it before testing row-level security.
- `Asymptomatic_Ratio` from the original plan was dropped: no source has it.
- Row- and object-level security cannot be split across two roles for one user; a user needing both gets a single combined role.

## Structure

```
sti-surveillance/
├── .github/workflows/weekly_ingest.yml   # pytest → ingest → dbt seed/snapshot/build → freshness
├── scripts/ingest.py                     # fetch, normalise, upsert
├── sql/                                  # raw schema, mcp_reader role
├── dbt/
│   ├── models/staging, models/marts      # views and tables, with tests
│   ├── seeds/                            # disease_map, state_codes, dim_access
│   ├── snapshots/snap_nndss_weekly.sql
│   └── tests/                            # singular grain tests
├── mcp/mcp_server.py
├── tests/test_ingest.py
└── docs/superpowers/                     # design spec and implementation plan
```

## Quick start 🚀

Needs Python 3.12 or newer and a Neon project (without the connection pooler).

```bash
cp .env.example .env     # fill DATABASE_URL, PGHOST, PGUSER, PGPASSWORD, PGDATABASE
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r mcp/requirements.txt
# load .env (Neon URLs can contain '&', so `source` breaks)
while IFS='=' read -r k v || [[ -n "$k" ]]; do [[ -z "$k" || "$k" == \#* ]] && continue; export "$k=$v"; done < .env
psql "$DATABASE_URL" -f sql/raw_schema.sql
.venv/bin/python -m scripts.ingest
cd dbt && ../.venv/bin/dbt seed --profiles-dir . && ../.venv/bin/dbt snapshot --profiles-dir . && ../.venv/bin/dbt build --profiles-dir .
```

MCP role, once: `psql "$DATABASE_URL" -v pw="'<password>'" -f sql/mcp_reader_role.sql`, then store its URL in `.env` as `MCP_DATABASE_URL`. The grants are applied by the dbt `on-run-end` hook at every build.

CI needs the repo secrets `NEON_DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD` and `PGDATABASE`.

## Tests

```bash
.venv/bin/pytest tests -q      # 6 tests on the normalisers and the dedupe
cd dbt && ../.venv/bin/dbt build --profiles-dir .
```

## Phases ✅

- [x] Source search and live testing of the APIs
- [x] Idempotent ingestion with unit tests
- [x] dbt staging, star schema, snapshot, tests and exposure
- [x] Weekly GitHub Actions workflow
- [x] Read-only MCP server with a single-cut view
- [ ] MCP tested from Claude Desktop (valid query, DML block, restricted-column block)
- [ ] Power BI semantic model: relations, DAX measures, aggregations
- [ ] Row-level security by county and object-level security on race, age and revisions, tested with *View as*
- [ ] Accessible dark theme and the 7-page report
- [ ] Screenshots in `docs/img/`

## Out of scope (deliberately)

- A national HIV series: the only free source with an API and recent data is Oregon.
- Incremental loading and an orchestrator: the full load takes about a minute.
- Publishing the report with Power BI *Publish to web*: it exposes the data and does not support row-level security.
- Imputing masked cells.

## License

MIT — see the `LICENSE` file. Data: CDC (Office of Public Health Data, Surveillance, and Technology), Oregon Health Authority (attributed as "OHA PHD ACDP") and U.S. Census Bureau. The two Socrata datasets declare no license in their metadata, so check each portal's terms before redistributing the data.
