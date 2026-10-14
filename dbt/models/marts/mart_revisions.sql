with agg as (
    select year, week, label, location1,
           (array_agg(m1 order by dbt_valid_from asc))[1] as first_m1,
           (array_agg(m1 order by dbt_valid_from desc))[1] as current_m1,
           count(*) - 1 as n_revisions
    from {{ ref('snap_nndss_weekly') }}
    where location1 is not null
    group by 1, 2, 3, 4
)
select a.year * 100 + a.week as epi_week_key, c.state_code as geo_key, m.disease_key,
       sum(first_m1) as first_reported_m1, sum(current_m1) as current_m1,
       sum(n_revisions) as n_revisions, sum(current_m1) - sum(first_m1) as delta
from agg a
join {{ ref('state_codes') }} c on c.state_name_upper = upper(a.location1)
join {{ ref('disease_map') }} m on m.source = 'nndss' and m.source_name = a.label
group by 1, 2, 3
