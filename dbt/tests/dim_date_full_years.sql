-- dim_date debe cubrir años completos: del 1-ene-2021 al 31-dic del año actual, sin huecos
select mn, mx, n
from (select min(date) mn, max(date) mx, count(*) n from {{ ref('dim_date') }}) t
where mn <> date '2021-01-01'
   or mx <> make_date(extract(year from current_date)::int, 12, 31)
   or n <> mx - mn + 1
