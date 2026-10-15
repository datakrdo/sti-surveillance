select epi_week_key, disease_key from {{ ref('agg_weekly_national') }}
group by 1, 2 having count(*) > 1
