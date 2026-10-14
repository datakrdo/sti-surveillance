with w as (
    select d::date as week_start_date, d::date + 6 as week_end_date, extract(year from d::date + 3)::int as mmwr_year
    from generate_series('2021-01-03'::date, current_date + 7, interval '7 days') d
),
n as (
    select *, row_number() over (partition by mmwr_year order by week_start_date)::int as mmwr_week from w
),
ref as (
    select max(w2.week_end_date) - 14 as ref_end
    from {{ ref('stg_nndss_weekly') }} s
    join n w2 on w2.mmwr_year * 100 + w2.mmwr_week = s.epi_week_key
)
select n.mmwr_year * 100 + n.mmwr_week as epi_week_key, n.mmwr_year, n.mmwr_week,
       n.week_start_date, n.week_end_date,
       (n.week_end_date = ref.ref_end) as is_reference_week
from n cross join ref
