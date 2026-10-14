-- Rol de solo lectura para el servidor MCP. Los GRANT/REVOKE sobre analytics_marts
-- viven en dbt_project.yml (on-run-end) porque dbt recrea las tablas en cada build.
-- psql -v pw="'...'" -f sql/mcp_reader_role.sql
CREATE ROLE mcp_reader LOGIN PASSWORD :pw;
ALTER ROLE mcp_reader SET default_transaction_read_only = on;
ALTER ROLE mcp_reader SET statement_timeout = '10s';
