import test from "node:test";
import assert from "node:assert/strict";
import { makeTools, DEFINITIONS, ixOf } from "../src/tools.js";
import { index, casesTotal, ratePer100k, topStates } from "../../site/js/metrics.js";

const weeks = [];
for (const y of [2023, 2024, 2025]) for (const w of [1, 2, 3]) weeks.push({ key: y * 100 + w, year: y, week: w, start: "" });
const diseases = ["CHL", "GON", "SYP_PS", "SYP_CONG"].map((key) => ({ key, name_es: key, name_en: key, color: "#fff" }));
const rows = [];
for (const w of weeks) for (const s of ["CA", "OR"]) rows.push([w.key, "GON", s, s === "CA" ? 10 + w.week : 3, 1000000]);
const data = { generated_at: "2026-10-18T00:00:00+00:00", ref_week: 202503, latest_week: 202503, diseases,
  states: [{ code: "CA", name: "California" }, { code: "OR", name: "Oregon" }], weeks, rows, cols: ["w", "d", "s", "cases", "pop"] };

const tools = Object.fromEntries(makeTools(async () => data).map((t) => [t.name, t]));
const call = async (name, args) => {
  const r = await tools[name].run(args);
  return { ...r, body: JSON.parse(r.content[0].text.replace(/^[^{[]*/, "") || "null") };
};

test("las 6 herramientas existen y son de solo lectura", () => {
  assert.deepEqual(Object.keys(tools).sort(), ["get_cases", "get_corridor", "get_rate_per_100k", "get_yoy", "list_dimensions", "top_states"]);
  assert.match(DEFINITIONS, /U/);
});

test("get_cases y get_rate_per_100k dan lo mismo que metrics.js", async () => {
  const ix = index(data);
  assert.equal((await call("get_cases", { disease: "GON", state: "CA", year: 2025 })).body.cases, casesTotal(ix, { disease: "GON", state: "CA", year: 2025 }));
  assert.equal((await call("get_rate_per_100k", { disease: "GON", year: 2025 })).body.rate_per_100k, ratePer100k(ix, { disease: "GON", year: 2025 }));
  assert.deepEqual((await call("top_states", { disease: "GON", year: 2025, n: 1 })).body.states, topStates(ix, { disease: "GON", year: 2025, n: 1 }));
});

test("list_dimensions describe enfermedades, estados y semanas", async () => {
  const b = (await call("list_dimensions", {})).body;
  assert.equal(b.diseases.length, 4);
  assert.equal(b.latest_week, 202503);
});

for (const [name, args] of [
  ["get_cases", { disease: "HIV", year: 2025 }],
  ["get_cases", { disease: "GON", state: "ZZ", year: 2025 }],
  ["get_cases", { disease: "GON", year: 1999 }],
  ["top_states", { disease: "GON", year: 2025, n: 1000 }],
  ["get_corridor", { disease: "GON", state: "CA", week: 99, year: 2025 }],
  ["get_yoy", { disease: "GON", year: 2025 }],
]) test(`parámetros inválidos → isError claro: ${name} ${JSON.stringify(args)}`, async () => {
  const r = await tools[name].run(args);
  assert.equal(r.isError, true);
  assert.ok(r.content[0].text.length > 10);
});

test("si los datos no cargan, isError y sin excepción", async () => {
  const broken = Object.fromEntries(makeTools(async () => { throw new Error("pages caído"); }).map((t) => [t.name, t]));
  const r = await broken.get_cases.run({ disease: "GON", year: 2025 });
  assert.equal(r.isError, true);
  assert.match(r.content[0].text, /could not be loaded/i);
});

test("el índice se construye una sola vez por objeto de datos (CPU del plan gratis)", () => {
  assert.equal(ixOf(data), ixOf(data));
  assert.notEqual(ixOf(data), ixOf({ ...data }));
});
