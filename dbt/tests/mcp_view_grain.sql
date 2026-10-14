-- falla si la vista del MCP repite un mes×enfermedad×condado×status (riesgo de doble conteo)
select epi_month_key, disease_key, county_name, confirmation_status, count(*)
from {{ ref('mcp_oregon_county_monthly') }}
group by 1, 2, 3, 4 having count(*) > 1
