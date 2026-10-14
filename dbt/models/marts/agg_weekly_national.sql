select f.epi_week_key, f.disease_key, coalesce(g.census_region, 'Territories') as census_region,
       sum(f.cases_week) as cases_week, sum(f.population) as population
from {{ ref('fct_nndss_weekly') }} f
join {{ ref('dim_geography') }} g on g.geo_key = f.geo_key
group by 1, 2, 3
