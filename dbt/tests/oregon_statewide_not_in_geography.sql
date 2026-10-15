-- el total estatal vive en el corte 'Statewide'; en 'Geography' solo puede haber condados
select f.fact_id
from {{ ref('fct_oregon_monthly') }} f
join {{ ref('dim_demographic') }} d using (demographic_key)
where d.demographic_type = 'Geography' and f.geo_key = 'OR'
