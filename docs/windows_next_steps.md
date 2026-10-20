# Windows: lo que falta

Todo lo demás (rediseño, accesibilidad, 7.E, GIF del README) está hecho. Queda probar el MCP de Microsoft contra el modelo publicado en el tenant. Fuente: Microsoft Learn, *Register Power BI MCP servers for MCP clients* y *Power BI Consumption MCP server setup* (el servicio está en vista previa; si un menú cambió, manda la documentación).

## MCP de Power BI contra el modelo publicado

1. **Admin portal de Power BI** → *Tenant settings* → habilitar **Users can use the Power BI Model Context Protocol server endpoint (preview)**.
2. **Entra admin center** (entra.microsoft.com) → *App registrations* → *New registration*: nombre `Power BI MCP - Claude`, *Single tenant*, sin Redirect URI. Copiar el **Application (client) ID**.
3. En esa app: *Authentication* → *Add Redirect URI* → **Mobile and desktop applications** → `https://claude.ai/api/mcp/auth_callback` → *Configure*. *Allow public client flows* = No.
4. *API permissions* → *Add a permission* → **Power BI Service** → *Delegated*: `Dataset.Read.All`, `Workspace.Read.All`, `MLModel.Execute.All` → *Grant admin consent* si el tenant lo exige.
5. Cada cuenta de prueba necesita permiso **Build** sobre el modelo semántico publicado (*Manage permissions*).
6. En Claude (Desktop o claude.ai): *Settings → Connectors → Add custom connector*: nombre `Power BI`, URL `https://api.fabric.microsoft.com/v1/mcp/powerbi`, **OAuth Client ID** = el del paso 2. Iniciar sesión con la cuenta de prueba y aceptar los permisos.
7. Despertar Neon antes de preguntar (la primera consulta tarda). Preguntas, en este orden:
   - «What tables are in semantic model [ID del modelo]?» (el ID está en la URL del modelo en el servicio).
   - Casos de gonorrea en California, semana 2024-W52 → debe dar **499** (ancla A3).
   - Tasa anualizada de clamidia en California 2024 → **259,434** por 100 mil (A4).
8. **Seguridad:** repetir con una cuenta `State_Analyst` (debe ver solo su estado) y con una `Restricted_State_Analyst` (pedir `race_group` o `mart_revisions` → debe fallar o no aparecer). Anotar si el MCP respeta RLS/OLS igual que el informe.
9. Anotar: licencia/capacidad del workspace, qué falló y el mensaje exacto. Volver a Linux con el resultado.

Después: ningún secreto en el repo (el client ID no es secreto, pero no lo subas). Commit y push desde Windows solo si cambias algo.
