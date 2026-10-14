-- ponytail: max_prev_52w de NY+NYC se suma (no es un max real); solo informativo
with j as (
    select s.*, c.state_code
    from {{ source('raw', 'nndss_weekly') }} s
    left join {{ ref('state_codes') }} c on c.state_name_upper = upper(s.location1)
    where s.location1 is not null
)
select
    year as mmwr_year,
    week as mmwr_week,
    year * 100 + week as epi_week_key,
    label as disease_source_name,
    state_code,
    sum(m1) as cases_week,
    sum(m2) as max_prev_52w,
    sum(m3) as cum_ytd,
    sum(m4) as cum_ytd_prev,
    bool_or(m1 is null) as is_flagged
from j
group by 1, 2, 3, 4, 5
