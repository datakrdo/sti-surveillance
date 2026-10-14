with reg as (
    select distinct on (state_code) state_code, census_region, census_division
    from {{ ref('stg_census_population') }} order by state_code, year desc
),
states as (
    select distinct c.state_code, c.state_name, r.census_region, r.census_division
    from {{ ref('state_codes') }} c left join reg r using (state_code)
)
select state_code as geo_key, state_code, state_name, null::text as county_name, 'state' as geo_level, census_region, census_division
from states
union all
select distinct 'OR|' || o.county_name, 'OR', 'Oregon', o.county_name, 'county', s.census_region, s.census_division
from {{ ref('stg_oregon_monthly') }} o
join states s on s.state_code = 'OR'
where o.county_name is not null
