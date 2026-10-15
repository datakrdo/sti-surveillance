-- Rol de solo lectura para Power BI. Los GRANT sobre analytics_marts / dim_access los reaplica
-- un hook on-run-end de dbt (cada build recrea las tablas y borraría los permisos).
-- psql -v pw="'...'" -f sql/pbi_reader_role.sql
CREATE ROLE pbi_reader LOGIN PASSWORD :pw;
ALTER ROLE pbi_reader SET default_transaction_read_only = on;
ALTER ROLE pbi_reader SET statement_timeout = '60s';
