import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { index, casesTotal, ratePer100k, yoy, weeklySeries, corridor, statesInOutbreak, topStates, ratesByState } from "./metrics.js";

const weeks = [];
for (const y of [2023, 2024, 2025]) for (const w of [1, 2, 3]) weeks.push({ key: y * 100 + w, year: y, week: w, start: "" });
const mk = (rows) => index({ weeks, rows, cols: ["w", "d", "s", "cases", "pop"] });

test("nulos no suman y la serie deja hueco, nunca 0", () => {
  const ix = mk([[202401, "CHL", "CA", 10, 1000], [202402, "CHL", "CA", null, 1000], [202403, "CHL", "CA", 5, 1000]]);
  assert.equal(casesTotal(ix, { disease: "CHL", state: "CA", year: 2024 }), 15);
  assert.deepEqual(weeklySeries(ix, { disease: "CHL", state: "CA", year: 2024 }).map((p) => p.cases), [10, null, 5]);
  assert.equal(casesTotal(ix, { disease: "CHL", state: "CA", year: 2023 }), null);
});

test("tasa: población 0 o sin datos da null; con datos usa persona-años", () => {
  assert.equal(ratePer100k(mk([[202401, "CHL", "CA", 10, 0]]), { disease: "CHL", state: "CA", year: 2024 }), null);
  assert.equal(ratePer100k(mk([]), { disease: "CHL", year: 2024 }), null);
  const ix = mk([[202401, "CHL", "CA", 10, 100000], [202402, "CHL", "CA", 10, 100000]]);
  // 20*1e5 / (200000/(365.25/7))
  assert.ok(Math.abs(ratePer100k(ix, { disease: "CHL", state: "CA", year: 2024 }) - (20 * 1e5) / (200000 / (365.25 / 7))) < 1e-9);
});

test("interanual alineado por semana MMWR", () => {
  const ix = mk([[202402, "GON", "CA", 12, 1], [202502, "GON", "CA", 9, 1], [202503, "GON", "CA", 100, 1], [202403, "GON", "CA", 100, 1]]);
  const r = yoy(ix, { disease: "GON", state: "CA", year: 2025, throughWeek: 2 });
  assert.deepEqual([r.current, r.previous], [9, 12]);
  assert.ok(Math.abs(r.pct - -25) < 1e-9);
  assert.equal(yoy(mk([]), { disease: "GON", year: 2025, throughWeek: 2 }), null);
});

test("corredor: percentile_cont de los años previos con dato", () => {
  const ix = mk([[202301, "GON", "CA", 10, 1], [202401, "GON", "CA", 20, 1], [202501, "GON", "CA", 40, 1]]);
  const c = corridor(ix, { disease: "GON", state: "CA", week: 1, year: 2025 });
  assert.deepEqual([c.p25, c.p50, c.p75, c.current], [12.5, 15, 17.5, 40]);
  assert.equal(corridor(ix, { disease: "GON", state: "CA", week: 1, year: 2023 }), null);
});

test("estados en brote, ranking y tasas por estado", () => {
  const ix = mk([
    [202301, "GON", "CA", 10, 100], [202401, "GON", "CA", 20, 100], [202501, "GON", "CA", 99, 100],
    [202301, "GON", "OR", 10, 100], [202401, "GON", "OR", 20, 100], [202501, "GON", "OR", 12, 100]]);
  assert.equal(statesInOutbreak(ix, { disease: "GON", weekKey: 202501 }), 1);
  assert.deepEqual(topStates(ix, { disease: "GON", year: 2025, n: 1 }), [{ state: "CA", cases: 99 }]);
  assert.equal(Object.keys(ratesByState(ix, { disease: "GON", year: 2025 })).length, 2);
});

const dataPath = new URL("../data/nndss.json", import.meta.url);
test("anclas: metrics.js == SQL", { skip: !existsSync(dataPath) }, () => {
  const ix = index(JSON.parse(readFileSync(dataPath)));
  const A = JSON.parse(readFileSync(new URL("../data/anchors.json", import.meta.url)));
  for (const [d, n] of Object.entries(A.A2)) assert.equal(ix.years.reduce((s, y) => s + (casesTotal(ix, { disease: d, year: y }) ?? 0), 0), n);
  assert.equal(weeklySeries(ix, { disease: "GON", state: "CA", year: 2024 }).find((p) => p.week === 52).cases, A.A3);
  assert.ok(Math.abs(ratePer100k(ix, { disease: "CHL", state: "CA", year: 2024 }) - A.A4[0]) < 0.001);
  assert.ok(Math.abs(ratePer100k(ix, { disease: "GON", year: 2025 }) - A.A4[1]) < 0.001);
  assert.equal(casesTotal(ix, { disease: "GON", year: 2026, weekTo: 40 }), A.A5.y26);
  assert.equal(casesTotal(ix, { disease: "GON", year: 2025, weekTo: 40 }), A.A5.ly_mmwr);
  assert.equal(casesTotal(ix, { disease: "GON", year: 2026, weekFrom: 40, weekTo: 40 }), A.A5.w40_26);
  assert.equal(casesTotal(ix, { disease: "GON", year: 2025, weekFrom: 40, weekTo: 40 }), A.A5.w40_25);
  const c = corridor(ix, { disease: "GON", state: "CA", week: 40, year: 2026 });
  for (const k of ["p25", "p50", "p75"]) assert.ok(Math.abs(c[k] - A.A6[k]) < 1e-6);
  assert.equal(statesInOutbreak(ix, { disease: "GON", weekKey: 202640 }), A.A7);
  assert.deepEqual([ix.data.ref_week, ix.data.latest_week], A.A8);
  for (const s of ["CA", "OR"]) assert.equal(casesTotal(ix, { disease: "GON", state: s, year: 2025 }), A.A13[s]);
});

test("rendimiento: statesInOutbreak y ratesByState sobre los datos reales (límite de CPU del Worker)", { skip: !existsSync(dataPath) }, () => {
  const ix = index(JSON.parse(readFileSync(dataPath)));
  const time = (fn) => { const t = performance.now(); fn(); return performance.now() - t; };
  const o = time(() => statesInOutbreak(ix, { disease: "GON", weekKey: 202638 }));
  assert.ok(o < 40, `statesInOutbreak tardó ${o.toFixed(1)} ms`);
  const r = time(() => ratesByState(ix, { disease: "GON", year: 2026 }));
  assert.ok(r < 10, `ratesByState tardó ${r.toFixed(1)} ms`);
});
