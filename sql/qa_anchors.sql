-- Regenera los valores de referencia (anclas A1-A15) del plan de Power BI.
-- Cada consulta lleva su ancla; correr en el SQL Editor de Neon o con psql.

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
