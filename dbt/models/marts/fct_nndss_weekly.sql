-- población: Census PEP del año MMWR (si > 2025 se usa 2025)
select
    md5(s.epi_week_key::text || '|' || m.disease_key || '|' || s.state_code) as fact_id,
    s.epi_week_key, m.disease_key, s.state_code as geo_key,
    s.cases_week, s.max_prev_52w, s.cum_ytd, s.cum_ytd_prev,
    p.population, s.is_flagged
from {{ ref('stg_nndss_weekly') }} s
join {{ ref('disease_map') }} m on m.source = 'nndss' and m.source_name = s.disease_source_name
left join {{ ref('stg_census_population') }} p on p.state_code = s.state_code and p.year = least(s.mmwr_year, 2025)
