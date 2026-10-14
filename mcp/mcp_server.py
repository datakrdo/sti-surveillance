import json, os, re
import psycopg2
from mcp.server import MCPServer

mcp = MCPServer("Healthcare-STI-Epidemiology-Platform")
DB = os.environ["MCP_DATABASE_URL"]  # rol 'mcp_reader': solo SELECT sobre marts, sin columnas OLS
TMDL_ROOT = "data_model/STI_Surveillance_Model.SemanticModel/definition"


@mcp.resource("powerbi://metadata/schema")
def get_powerbi_schema() -> str:
    """Expone el TMDL del PBIP para que la IA entienda el modelo."""
    return "\n\n".join(open(os.path.join(d, f)).read()
                       for d, _, fs in os.walk(TMDL_ROOT) for f in fs if f.endswith(".tmdl"))


@mcp.tool()
def query_epidemiology_data(sql_query: str) -> str:
    """Consulta SQL de solo lectura sobre analytics_marts, con guardrails.

    Oregon: usar la vista analytics_marts.mcp_oregon_county_monthly (solo condados, un corte: los SUM son aditivos;
    cases es NULL cuando is_masked=true, es decir menos de 6 casos). NNDSS: analytics_marts.fct_nndss_weekly.
    """
    q = sql_query.lower()
    # Guardrail 1 (defensa en profundidad; la protección real es el rol read-only)
    if re.search(r"\b(drop|delete|insert|update|truncate|alter|grant|create)\b", q):
        return "ERROR: base de datos de solo lectura."
    # Guardrail 2: emula la OLS
    if re.search(r"\b(race_group|race_method|age_group|mart_revisions)\b", q):
        return "ERROR [OLS-HIPAA]: acceso denegado a objeto restringido."
    try:
        with psycopg2.connect(DB, options="-c default_transaction_read_only=on -c statement_timeout=10000") as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM ({sql_query.rstrip(';')}) t LIMIT 500")
            cols = [d[0] for d in cur.description]
            return json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], default=str, indent=2)
    except Exception as e:
        return f"Error SQL: {e}"


if __name__ == "__main__":
    mcp.run()
