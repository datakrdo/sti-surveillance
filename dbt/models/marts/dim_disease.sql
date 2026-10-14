select distinct
    disease_key, disease_name, disease_group, pathogen_type, transmission_mode,
    (comparable_across_sources::text = 'true') as comparable_across_sources
from {{ ref('disease_map') }}
