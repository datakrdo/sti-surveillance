select epi_month_key, mmwr_year, month,
       min(report_period_start) as period_start, max(report_period_end) as period_end,
       mmwr_year || '-' || lpad(month::text, 2, '0') as month_label
from {{ ref('stg_oregon_monthly') }}
group by 1, 2, 3
