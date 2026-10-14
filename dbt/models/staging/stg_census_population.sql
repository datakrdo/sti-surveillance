select
    c.state_code,
    p.year,
    p.population,
    case p.region when '1' then 'Northeast' when '2' then 'Midwest' when '3' then 'South' when '4' then 'West' end as census_region,
    p.division as census_division
from {{ source('raw', 'census_population') }} p
join {{ ref('state_codes') }} c on c.state_name_upper = upper(p.name)
where c.state_name_upper <> 'NEW YORK CITY'
