select
    mmwr_year,
    month,
    mmwr_year * 100 + month as epi_month_key,
    report_period_start,
    report_period_end,
    disease_name as disease_source_name,
    case when demographic = 'Geography' and geo_unit = 'state' then 'Statewide' else demographic end as demographic_type,
    case when demographic = 'Geography' then 'All' else demographic_level end as demographic_level,
    case when geo_unit = 'county' then demographic_level end as county_name,
    'OR' as state_code,
    confirmation_status,
    cases,
    is_masked,
    population
from {{ source('raw', 'oregon_monthly') }}
