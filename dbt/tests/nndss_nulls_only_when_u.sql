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
