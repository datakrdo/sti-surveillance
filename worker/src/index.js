import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler } from "agents/mcp/server";
import { makeTools, DEFINITIONS } from "./tools.js";

// Memo por instancia del Worker; la caché de Cloudflare (cacheTtl) evita ir a Pages en cada llamada.
let memo = null;
const loader = (env) => async () => {
  if (memo && Date.now() - memo.at < 600_000) return memo.data;
  const res = await fetch(env.DATA_URL, { cf: { cacheTtl: 600, cacheEverything: true } });
  if (!res.ok) throw new Error(`data ${res.status}`);
  const data = await res.json();
  memo = { at: Date.now(), data };
  return data;
};

function createServer(env) {
  const server = new McpServer({ name: "sti-surveillance-public", version: "1.0.0" });
  server.registerResource("definitions", "sti://definitions",
    { title: "Definitions and limitations", mimeType: "text/plain" },
    async (uri) => ({ contents: [{ uri: uri.href, text: DEFINITIONS }] }));
  for (const t of makeTools(loader(env)))
    server.registerTool(t.name, { description: t.description, inputSchema: t.shape }, (args) => t.run(args));
  return server;
}

export default {
  fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/mcp") return createMcpHandler(() => createServer(env), { route: "/mcp" })(request, env, ctx);
    return new Response("STI surveillance MCP (read-only). Connect your MCP client to /mcp\n", { headers: { "content-type": "text/plain" } });
  },
};
