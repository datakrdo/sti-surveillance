select f.epi_week_key, f.disease_key
from (select epi_week_key, disease_key, sum(cases_week) c from {{ ref('fct_nndss_weekly') }} group by 1, 2) f
join (select epi_week_key, disease_key, sum(cases_week) c from {{ ref('agg_weekly_national') }} group by 1, 2) a
  using (epi_week_key, disease_key)
where f.c is distinct from a.c
