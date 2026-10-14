-- falla si un slice Geography tiene más de una fila por mes×enfermedad×geo×status
select f.epi_month_key, f.disease_key, f.geo_key, f.confirmation_status, count(*)
from {{ ref('fct_oregon_monthly') }} f
join {{ ref('dim_demographic') }} d using (demographic_key)
where d.demographic_type = 'Geography'
group by 1, 2, 3, 4 having count(*) > 1
