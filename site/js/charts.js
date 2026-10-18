// Gráficos SVG propios (sin librerías ni GeoJSON de terceros). Devuelven markup para insertar con innerHTML.
export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fmt = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + "k" : String(Math.round(n * 10) / 10));

// El eje cubre hasta la semana 53 cuando el año la tiene (MMWR 2025 la tiene).
export const xMaxOf = (seriesList) => Math.max(52, ...seriesList.flat().map((p) => p.x));

// lines: [{label, color, dash?, points:[{x, y|null}]}]; band?: {lo:[{x,y}], hi:[{x,y}]} (gris, para el corredor)
export function lineChartSVG({ title, lines, xMax = 52, band = null, w = 800, h = 360 }) {
  const m = { l: 56, r: 16, t: 16, b: 32 };
  const ys = [...lines.flatMap((l) => l.points.map((p) => p.y)), ...(band ? band.hi.map((p) => p.y) : [])].filter((v) => v != null);
  const yMax = ys.length ? Math.max(...ys) * 1.1 || 1 : 1;
  const X = (x) => (m.l + ((x - 1) / Math.max(xMax - 1, 1)) * (w - m.l - m.r)).toFixed(1);
  const Y = (y) => (h - m.b - (y / yMax) * (h - m.t - m.b)).toFixed(1);
  let out = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>${esc(title)}</title>`;
  for (let i = 0; i <= 4; i++) {
    const v = (yMax * i) / 4;
    out += `<line x1="${m.l}" x2="${w - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#2A3A4A"/><text x="${m.l - 8}" y="${Number(Y(v)) + 4}" text-anchor="end" fill="#9AA7B4" font-size="12">${fmt(v)}</text>`;
  }
  for (const x of [1, 13, 26, 39, 52].filter((v) => v <= xMax))
    out += `<text x="${X(x)}" y="${h - 10}" text-anchor="middle" fill="#9AA7B4" font-size="12">${x}</text>`;
  if (band) {
    const pts = band.lo.map((p, i) => [p, band.hi[i]]).filter(([a, b]) => a.y != null && b.y != null);
    if (pts.length > 1) {
      const d = pts.map(([a, b]) => `${X(a.x)},${Y(a.y)}`).concat(pts.map(([a, b]) => `${X(b.x)},${Y(b.y)}`).reverse()).join(" ");
      out += `<polygon points="${d}" fill="#9AA7B4" fill-opacity="0.25"/>`;
    }
  }
  for (const l of lines) {
    let seg = [];
    const flush = () => {
      if (seg.length > 1) out += `<path d="M${seg.join("L")}" class="line" fill="none" stroke="${esc(l.color)}" stroke-width="2.5"${l.dash ? ` stroke-dasharray="${l.dash}"` : ""}/>`;
      else if (seg.length === 1) out += `<circle cx="${seg[0].split(",")[0]}" cy="${seg[0].split(",")[1]}" r="2.5" fill="${esc(l.color)}"/>`;
      seg = [];
    };
    for (const p of l.points) (p.y == null ? flush() : seg.push(`${X(p.x)},${Y(p.y)}`));
    flush();
  }
  return out + "</svg>";
}

// Baldosas [fila, columna] por estado (mapa de cuadrícula, sin geometría externa).
export const TILES = {
  AK: [0, 0], ME: [0, 11], VT: [1, 10], NH: [1, 11],
  WA: [2, 0], ID: [2, 1], MT: [2, 2], ND: [2, 3], MN: [2, 4], IL: [2, 5], WI: [2, 6], MI: [2, 7], NY: [2, 9], RI: [2, 10], MA: [2, 11],
  OR: [3, 0], NV: [3, 1], WY: [3, 2], SD: [3, 3], IA: [3, 4], IN: [3, 5], OH: [3, 6], PA: [3, 7], NJ: [3, 8], CT: [3, 9],
  CA: [4, 0], UT: [4, 1], CO: [4, 2], NE: [4, 3], MO: [4, 4], KY: [4, 5], WV: [4, 6], VA: [4, 7], MD: [4, 8], DE: [4, 9],
  AZ: [5, 1], NM: [5, 2], KS: [5, 3], AR: [5, 4], TN: [5, 5], NC: [5, 6], SC: [5, 7], DC: [5, 8],
  OK: [6, 3], LA: [6, 4], MS: [6, 5], AL: [6, 6], GA: [6, 7],
  HI: [7, 0], TX: [7, 3], FL: [7, 8],
  PR: [8, 2], VI: [8, 3], GU: [8, 4], AS: [8, 5], MP: [8, 6],
};

const lerp = (a, b, t) => Math.round(a + (b - a) * t).toString(16).padStart(2, "0");
// Rampa secuencial de un solo sentido: azul grisáceo = tasa baja, amarillo = tasa alta (la tasa es magnitud, no identidad).
export const RAMP = ["#4F7CA3", "#F0E442"];
const ramp = (t) => `#${[1, 3, 5].map((i) => lerp(parseInt(RAMP[0].slice(i, i + 2), 16), parseInt(RAMP[1].slice(i, i + 2), 16), t)).join("")}`;

// Leyenda del mapa: barra con la misma rampa, extremos con valores reales y muestra de "sin dato".
export function mapLegendHTML({ min, max, fmt, t }) {
  if (min == null || max == null) return "";
  return `<div class="map-legend" role="group" aria-label="${esc(t("mapLegendTitle"))}">
    <p class="map-legend-title">${esc(t("mapLegendTitle"))}</p>
    <div class="map-legend-bar"><span>${esc(t("mapLegendLow"))}<br><b>${esc(fmt(min))}</b></span>
      <i aria-hidden="true" style="background:linear-gradient(90deg,${RAMP[0]},${RAMP[1]})"></i>
      <span>${esc(t("mapLegendHigh"))}<br><b>${esc(fmt(max))}</b></span></div>
    <p class="map-legend-nodata"><i aria-hidden="true" style="background:#2A3A4A"></i>${esc(t("mapLegendNoData"))}</p>
    <p class="note">${esc(t("mapLegendNote"))}</p></div>`;
}

// values: {CODE: number|null}; label(code, value) -> texto accesible
export function tileMapSVG(values, { title, label }) {
  const S = 44, G = 4, cols = 12, rows = 9;
  const vs = Object.values(values).filter((v) => v != null);
  const max = vs.length ? Math.max(...vs) : 0;
  let out = `<svg viewBox="0 0 ${cols * (S + G)} ${rows * (S + G)}" role="img" aria-label="${esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>${esc(title)}</title>`;
  for (const [code, [r, c]] of Object.entries(TILES)) {
    const v = values[code] ?? null;
    const t = v == null || max <= 0 ? null : v / max;
    const fill = t == null ? "#2A3A4A" : ramp(t);
    const ink = t != null && t > 0.45 ? "#0F1720" : "#E6EDF3";
    out += `<g><title>${esc(label(code, v))}</title><rect x="${c * (S + G)}" y="${r * (S + G)}" width="${S}" height="${S}" rx="6" fill="${fill}"/>` +
           `<text x="${c * (S + G) + S / 2}" y="${r * (S + G) + S / 2 + 4}" text-anchor="middle" font-size="13" font-weight="600" fill="${ink}">${code}</text></g>`;
  }
  return out + "</svg>";
}
