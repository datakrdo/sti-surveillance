{% snapshot snap_nndss_weekly %}
{{ config(target_schema='snapshots', unique_key='snap_key', strategy='check', check_cols=['m1']) }}
select year || '-' || week || '-' || label || '-' || states as snap_key, *
from {{ source('raw', 'nndss_weekly') }}
{% endsnapshot %}
