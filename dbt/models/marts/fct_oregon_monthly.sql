select
    md5(o.epi_month_key::text || '|' || m.disease_key || '|' || coalesce(o.county_name, '') || '|' ||
        o.demographic_type || '|' || o.demographic_level || '|' || o.confirmation_status) as fact_id,
    o.epi_month_key, m.disease_key,
    case when o.county_name is not null then 'OR|' || o.county_name else 'OR' end as geo_key,
    md5(o.demographic_type || '|' || o.demographic_level) as demographic_key,
    o.confirmation_status, o.cases, o.is_masked, o.population
from {{ ref('stg_oregon_monthly') }} o
join {{ ref('disease_map') }} m on m.source = 'oregon' and m.source_name = o.disease_source_name
