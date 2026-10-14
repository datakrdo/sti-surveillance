select distinct
    md5(demographic_type || '|' || demographic_level) as demographic_key,
    demographic_type, demographic_level,
    case when demographic_type = 'Sex' then demographic_level end as sex,
    case when demographic_type = 'Age Group' then demographic_level end as age_group,
    case when demographic_type like 'Race%' then demographic_level end as race_group,
    case demographic_type
        when 'Race (alone or in combination)' then 'alone_or_combo'
        when 'Race (primary/least common race)' then 'primary' end as race_method
from {{ ref('stg_oregon_monthly') }}
