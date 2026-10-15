select d::date as date,
       extract(year from d)::int as year,
       extract(month from d)::int as month_number,
       to_char(d, 'Mon') as month_name,
       to_char(d, 'YYYY-MM') as year_month,
       extract(quarter from d)::int as quarter
from generate_series('2021-01-01'::timestamp,
                     make_date(extract(year from current_date)::int, 12, 31)::timestamp,
                     interval '1 day') d
