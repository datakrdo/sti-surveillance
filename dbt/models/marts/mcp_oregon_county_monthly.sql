-- Vista para el MCP: un solo corte (Geography) y solo condados, así cualquier SUM es aditivo.
-- No expone sexo/edad/raza ni el total estatal (sumarlo con los condados duplicaría).
{{ config(materialized='view') }}
select f.epi_month_key, m.mmwr_year, m.month, d.disease_key, d.disease_name,
       g.county_name, f.confirmation_status, f.cases, f.is_masked, f.population
from {{ ref('fct_oregon_monthly') }} f
join {{ ref('dim_demographic') }} x on x.demographic_key = f.demographic_key and x.demographic_type = 'Geography'
join {{ ref('dim_geography') }} g on g.geo_key = f.geo_key and g.geo_level = 'county'
join {{ ref('dim_epi_month') }} m on m.epi_month_key = f.epi_month_key
join {{ ref('dim_disease') }} d on d.disease_key = f.disease_key
