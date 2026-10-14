select 'nndss' as source, max(ingested_at) as last_ingested_at, max(year * 100 + week)::text as max_period,
       count(*) as n_rows, null::numeric as pct_masked, avg((m1 is null)::int) as pct_flagged,
       (select count(distinct location1) from {{ source('raw', 'nndss_weekly') }} w
         where location1 is not null and (w.year * 100 + w.week) = (select max(year * 100 + week) from {{ source('raw', 'nndss_weekly') }} where m1 is not null)
           and w.m1 is not null)::int as n_states_reporting_last_week
from {{ source('raw', 'nndss_weekly') }}
union all
select 'oregon', max(ingested_at), max(mmwr_year * 100 + month)::text, count(*),
       avg(is_masked::int), null, null
from {{ source('raw', 'oregon_monthly') }}
union all
select 'census', max(ingested_at), max(year)::text, count(*), null, null, null
from {{ source('raw', 'census_population') }}
