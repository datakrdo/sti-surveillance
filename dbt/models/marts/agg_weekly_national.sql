select epi_week_key, disease_key, sum(cases_week) as cases_week
from {{ ref('fct_nndss_weekly') }}
group by 1, 2
