// Cálculos compartidos por el sitio y el MCP remoto. Mismas definiciones que el modelo Power BI y sql/qa_anchors.sql.
// Entrada: el objeto de site/data/nndss.json. Los nulos (código 'U') nunca se tratan como 0.

export function index(data) {
  const wk = new Map(data.weeks.map((w) => [w.key, w]));
  const years = [...new Set(data.weeks.map((w) => w.year))].sort((a, b) => a - b);
  // Todo es perezoso: index() casi no cuesta (el Worker lo paga con cada recarga del JSON) y cada enfermedad
  // se prepara solo cuando se consulta. Cubetas por (estado, año) y por año evitan recorrer las 55k filas.
  let raw = null;
  const diseases = new Map();
  const disease = (d) => {
    if (diseases.has(d)) return diseases.get(d);
    raw ??= Object.groupBy(data.rows, (r) => r[1]);
    const rows = (raw[d] ?? []).map(([w, , s, cases, pop]) => ({ w, s, cases, pop, year: wk.get(w)?.year, week: wk.get(w)?.week }));
    const bySY = new Map(), byY = new Map(), states = new Set(), weekKeys = new Set();
    const push = (m, k, r) => (m.get(k) ?? m.set(k, []).get(k)).push(r);
    for (const r of rows) { push(bySY, `${r.s}|${r.year}`, r); push(byY, r.year, r); states.add(r.s); weekKeys.add(r.w); }
    const D = { rows, bySY, byY, states, weekKeys };
    diseases.set(d, D);
    return D;
  };
  return { data, years, disease, hasData: data.rows.length > 0,
           stateCodes: () => new Set(data.rows.map((r) => r[2])) };
}

const pick = (ix, { disease, state, year, weekFrom = 1, weekTo = 53 }) => {
  const D = ix.disease(disease);
  return (state ? D.bySY.get(`${state}|${year}`) : D.byY.get(year))?.filter((r) => r.week >= weekFrom && r.week <= weekTo) ?? [];
};

const sumCases = (rs) => {
  const v = rs.filter((r) => r.cases != null);
  return v.length ? v.reduce((a, r) => a + r.cases, 0) : null;
};

export const casesTotal = (ix, f) => sumCases(pick(ix, f));

export function ratePer100k(ix, f) {
  const rs = pick(ix, f).filter((r) => r.pop > 0);
  const den = rs.filter((r) => r.cases != null).reduce((a, r) => a + r.pop, 0) / (365.25 / 7);
  const num = sumCases(rs);
  return num == null || den <= 0 ? null : (num * 100000) / den;
}

export function yoy(ix, { disease, state, year, throughWeek }) {
  const current = casesTotal(ix, { disease, state, year, weekTo: throughWeek });
  const previous = casesTotal(ix, { disease, state, year: year - 1, weekTo: throughWeek });
  return current == null || !previous ? null : { current, previous, pct: ((current - previous) / previous) * 100 };
}

export function weeklySeries(ix, f) {
  const keys = ix.disease(f.disease).weekKeys;
  return ix.data.weeks.filter((w) => w.year === f.year && keys.has(w.key))
    .map((w) => ({ week: w.week, cases: sumCases(pick(ix, { ...f, weekFrom: w.week, weekTo: w.week })) }));
}

const pct = (sorted, p) => {  // percentile_cont (interpolación lineal)
  const h = (sorted.length - 1) * p, lo = Math.floor(h);
  return sorted[lo] + (h - lo) * ((sorted[Math.min(lo + 1, sorted.length - 1)] ?? sorted[lo]) - sorted[lo]);
};

function history(ix, { disease, state, week, year }) {
  return ix.years.filter((y) => y < year)
    .map((y) => sumCases(pick(ix, { disease, state, year: y, weekFrom: week, weekTo: week })))
    .filter((v) => v != null).sort((a, b) => a - b);
}

export function corridor(ix, f) {
  const h = history(ix, f);
  if (!h.length) return null;
  return { p25: pct(h, 0.25), p50: pct(h, 0.5), p75: pct(h, 0.75),
           current: sumCases(pick(ix, { ...f, weekFrom: f.week, weekTo: f.week })) };
}

export function statesInOutbreak(ix, { disease, weekKey }) {
  const year = Math.floor(weekKey / 100), week = weekKey % 100;
  const states = [...ix.disease(disease).states];
  return states.filter((s) => {
    const c = corridor(ix, { disease, state: s, week, year });
    return c && c.current != null && c.current > c.p75;
  }).length;
}

export function topStates(ix, { disease, year, weekKey, n }) {
  const by = new Map();
  const y = weekKey ? Math.floor(weekKey / 100) : year;
  for (const r of ix.disease(disease).byY.get(y) ?? []) {
    if ((weekKey && r.w !== weekKey) || r.cases == null) continue;
    by.set(r.s, (by.get(r.s) ?? 0) + r.cases);
  }
  return [...by].map(([state, cases]) => ({ state, cases })).sort((a, b) => b.cases - a.cases).slice(0, n);
}

export function ratesByState(ix, { disease, year }) {
  const out = {};
  for (const s of ix.disease(disease).states) out[s] = ratePer100k(ix, { disease, state: s, year });
  return out;
}
