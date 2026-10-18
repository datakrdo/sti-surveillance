import test from "node:test";
import assert from "node:assert/strict";
import { STRINGS, t } from "./i18n.js";
import { QUESTIONS } from "./questions.js";
import { lineChartSVG, tileMapSVG, TILES, esc, xMaxOf, mapLegendHTML, RAMP } from "./charts.js";
import { index } from "./metrics.js";

const weeks = [];
for (const y of [2024, 2025, 2026]) for (const w of [1, 2, 3, 38, 40]) weeks.push({ key: y * 100 + w, year: y, week: w, start: "" });
const diseases = ["CHL", "GON", "SYP_PS", "SYP_CONG"].map((key) => ({ key, name_es: key + "-es", name_en: key + "-en", color: "#56B4E9" }));
const rows = [];
for (const w of weeks) for (const d of diseases) for (const s of ["CA", "OR"])
  rows.push([w.key, d.key, s, w.week === 3 ? null : 10 + w.week, 1000000]);
const mini = { generated_at: "2026-10-18T00:00:00+00:00", ref_week: 202638, latest_week: 202640, diseases,
  states: [{ code: "CA", name: "California" }, { code: "OR", name: "Oregon" }], weeks, rows, cols: ["w", "d", "s", "cases", "pop"] };
const BAD = /NaN|Infinity|undefined|null/;

test("las claves ES y EN de i18n coinciden", () => {
  assert.deepEqual(Object.keys(STRINGS.es).sort(), Object.keys(STRINGS.en).sort());
  assert.equal(t("es", "noData"), STRINGS.es.noData);
  assert.equal(t("en", "no-such-key"), "no-such-key");
});

test("cada pregunta responde en ES y EN sin NaN/undefined", () => {
  assert.equal(QUESTIONS.length, 5);
  for (const q of QUESTIONS) for (const lang of ["es", "en"]) {
    assert.ok(q[lang].length > 10);
    const a = q.answer(index(mini), lang);
    assert.ok(a.text.length > 10, q.id);
    assert.doesNotMatch(a.text + JSON.stringify(a.rows), BAD, `${q.id}/${lang}`);
  }
});

test("sin datos: texto 'sin datos', no excepción", () => {
  const empty = index({ ...mini, rows: [], weeks: [] });
  for (const q of QUESTIONS) for (const lang of ["es", "en"]) {
    const a = q.answer(empty, lang);
    assert.equal(a.text, t(lang, "noData"));
    assert.deepEqual(a.rows, []);
  }
});

test("línea: los nulos cortan el trazo y no generan NaN", () => {
  const svg = lineChartSVG({ title: "x", lines: [{ label: "a", color: "#fff", points: [{ x: 1, y: 5 }, { x: 2, y: 6 }, { x: 3, y: null }, { x: 4, y: 7 }, { x: 5, y: 8 }] }], xMax: 52 });
  assert.doesNotMatch(svg, BAD);
  assert.equal((svg.match(/<path[^>]* class="line"/g) || []).length, 2);
});

test("línea: serie vacía devuelve gráfico válido", () => {
  assert.doesNotMatch(lineChartSVG({ title: "x", lines: [{ label: "a", color: "#fff", points: [] }], xMax: 52 }), BAD);
});

test("mapa de baldosas: posiciones únicas y valores nulos en gris", () => {
  const pos = Object.values(TILES).map(([r, c]) => `${r},${c}`);
  assert.equal(new Set(pos).size, pos.length);
  for (const s of ["CA", "OR", "TX", "DC", "AK", "HI"]) assert.ok(TILES[s], s);
  const svg = tileMapSVG({ CA: 10, OR: null }, { title: "m", label: (s, v) => `${s} ${v ?? "—"}` });
  assert.doesNotMatch(svg, BAD);
  assert.match(svg, /#2A3A4A/);
});

test("defensa en profundidad: colores y etiquetas se escapan en el SVG", () => {
  const evil = '"><script>alert(1)</script>';
  const svg = lineChartSVG({ title: evil, lines: [{ label: evil, color: evil, points: [{ x: 1, y: 1 }, { x: 2, y: 2 }] }], xMax: 52 });
  assert.doesNotMatch(svg, /<script/);
  assert.equal(esc(evil), "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;");
});

test("la semana 53 amplía el eje y queda dentro del área del gráfico", () => {
  assert.equal(xMaxOf([[{ x: 1 }, { x: 52 }]]), 52);
  assert.equal(xMaxOf([[{ x: 1 }], [{ x: 53 }]]), 53);
  const svg = lineChartSVG({ title: "x", xMax: xMaxOf([[{ x: 53 }]]), w: 800, lines: [{ label: "a", color: "#fff", points: [{ x: 52, y: 1 }, { x: 53, y: 2 }] }] });
  const xs = [...svg.matchAll(/[ML](\d+\.?\d*),/g)].map((m) => Number(m[1]));
  assert.ok(Math.max(...xs) <= 800 - 16 + 0.1, String(Math.max(...xs)));
});

test("leyenda del mapa: rampa, extremos reales y 'sin dato'", () => {
  const html = mapLegendHTML({ min: 0, max: 61.7, lang: "es", fmt: (n) => n.toFixed(1), t: (k) => STRINGS.es[k] });
  assert.match(html, new RegExp(RAMP[0]));
  assert.match(html, new RegExp(RAMP[1]));
  assert.match(html, /0\.0/); assert.match(html, /61\.7/);
  assert.match(html, /#2A3A4A/);                       // muestra de "sin dato"
  assert.match(html, new RegExp(STRINGS.es.mapLegendLow)); assert.match(html, new RegExp(STRINGS.es.mapLegendHigh));
  assert.doesNotMatch(html, BAD);
  // sin ningún valor no hay escala que mostrar, pero tampoco error
  assert.doesNotMatch(mapLegendHTML({ min: null, max: null, lang: "en", fmt: String, t: (k) => STRINGS.en[k] }), BAD);
});

test("el mapa usa los extremos de la rampa documentada (#4F7CA3 -> #F0E442)", () => {
  assert.deepEqual(RAMP, ["#4F7CA3", "#F0E442"]);
  assert.match(tileMapSVG({ CA: 10, OR: 20 }, { title: "m", label: String }), /#F0E442/i);
});
