import { STRINGS, t } from "./i18n.js";
import { index, casesTotal, ratePer100k, yoy, weeklySeries, corridor, statesInOutbreak, topStates, ratesByState } from "./metrics.js";
import { lineChartSVG, tileMapSVG, esc, xMaxOf } from "./charts.js";
import { QUESTIONS } from "./questions.js";
import { MCP_URL, REPO_URL } from "./config.js";

const $ = (id) => document.getElementById(id);
const TABS = ["Overview", "Map", "Corridor"];
const S = { lang: "es", tab: "Overview", disease: "GON", year: null, state: "CA", q: null };
let ix = null;

try { S.lang = localStorage.getItem("lang") || (navigator.language?.startsWith("en") ? "en" : "es"); } catch { S.lang = "es"; }
const num = (n, d = 0) => (n == null ? "—" : n.toLocaleString(S.lang, { maximumFractionDigits: d, minimumFractionDigits: d }));
const L = (k) => t(S.lang, k);
const dis = () => ix.data.diseases.find((d) => d.key === S.disease);
const stateName = (c) => esc(ix.data.states.find((s) => s.code === c)?.name ?? c);
const dName = (x) => esc(x["name_" + S.lang]);
const size = () => { const w = Math.max(320, Math.min(800, ($("view").clientWidth || 800) - 32)); return { w, h: Math.round(w * (w < 500 ? 0.75 : 0.45)) }; };
const latestYear = () => Math.floor(ix.data.latest_week / 100);

function fillStatic() {
  document.documentElement.lang = S.lang;
  $("title").textContent = L("title"); $("subtitle").textContent = L("subtitle");
  $("lbl-disease").textContent = L("disease"); $("lbl-year").textContent = L("year"); $("lbl-state").textContent = L("state");
  $("lang-group").setAttribute("aria-label", L("langLabel")); $("filters").setAttribute("aria-label", L("filtersLabel"));
  document.querySelector('meta[name="description"]')?.setAttribute("content", L("metaDescription"));
  $("q-title").textContent = L("questionsTitle"); $("q-lead").textContent = L("questionsLead");
  document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === S.lang)));
  $("tabs").innerHTML = TABS.map((k) => `<button type="button" role="tab" id="tab-${k}" data-tab="${k}" aria-selected="${k === S.tab}" aria-controls="view" tabindex="${k === S.tab ? 0 : -1}">${L("tab" + k)}</button>`).join("");
}

function fillFilters() {
  const d = ix.data;
  $("f-disease").innerHTML = d.diseases.map((x) => `<option value="${esc(x.key)}"${x.key === S.disease ? " selected" : ""}>${dName(x)}</option>`).join("");
  const years = [...new Set(d.weeks.map((w) => w.year))].sort((a, b) => b - a);
  $("f-year").innerHTML = years.map((y) => `<option${y === S.year ? " selected" : ""}>${y}</option>`).join("");
  const present = ix.stateCodes(), states = d.states.filter((s) => present.has(s.code));
  $("f-state").innerHTML = states.map((s) => `<option value="${esc(s.code)}"${s.code === S.state ? " selected" : ""}>${esc(s.name)}</option>`).join("");
  $("wrap-state").hidden = S.tab !== "Corridor";
  $("legend").innerHTML = d.diseases.map((x) => `<li><i style="background:${esc(x.color)}"></i>${dName(x)}</li>`).join("");
}

const kpi = (label, value, note = "") => `<div class="kpi"><small>${label}</small><strong>${value}</strong><em>${note}</em></div>`;
const table = (head, rows) => `<table><thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;

function overview() {
  const f = { disease: S.disease, year: S.year };
  const isLatest = S.year === latestYear();
  const through = isLatest ? ix.data.latest_week % 100 : 53;
  const y = yoy(ix, { ...f, throughWeek: through });
  const cur = weeklySeries(ix, f), prev = weeklySeries(ix, { disease: S.disease, year: S.year - 1 });
  const svg = lineChartSVG({ ...size(), title: `${L("weeklyCases")} — ${dName(dis())} ${S.year}`, xMax: xMaxOf([cur.map((p) => ({ x: p.week })), prev.map((p) => ({ x: p.week }))]), lines: [
    { label: L("previousYear"), color: "#9AA7B4", dash: "5 4", points: prev.map((p) => ({ x: p.week, y: p.cases })) },
    { label: String(S.year), color: dis().color, points: cur.map((p) => ({ x: p.week, y: p.cases })) }] });
  const wk = ix.data.ref_week % 100;
  return `<div class="cards">
    ${kpi(L("cardCases"), num(casesTotal(ix, f)), S.year)}
    ${kpi(L("cardRate"), num(ratePer100k(ix, f), 1), S.year)}
    ${kpi(L("cardYoy"), y ? (y.pct > 0 ? "+" : "") + num(y.pct, 1) + " %" : "—", isLatest ? `${L("throughWeek")} ${through}` : "")}
    ${kpi(L("cardOutbreak"), isLatest ? num(statesInOutbreak(ix, { disease: S.disease, weekKey: ix.data.ref_week })) : "—", `${L("cardOutbreakNote")} ${wk}`)}
  </div>
  <section class="chart"><h2>${L("weeklyCases")}</h2>${svg}
    <p class="key"><span><i style="border-color:${esc(dis().color)}"></i>${S.year}</span><span><i style="border-color:#9AA7B4;border-top-style:dashed"></i>${L("previousYear")}</span></p></section>`;
}

function mapView() {
  const f = { disease: S.disease, year: S.year };
  const rates = ratesByState(ix, f);
  const svg = tileMapSVG(rates, { title: `${L("rateByState")} — ${dName(dis())} ${S.year}`,
    label: (c, v) => `${stateName(c)}: ${v == null ? "—" : num(v, 1)}` });
  const top = topStates(ix, { ...f, n: 10 });
  const all = Object.entries(rates).filter(([, v]) => v != null).sort((a, b) => b[1] - a[1]);
  return `<div class="split"><section class="chart"><h2>${L("rateByState")}</h2>${svg}</section>
    <section><h2>${L("top10")}</h2>${table([L("state"), L("cases")], top.map((r) => [stateName(r.state), num(r.cases)]))}</section></div>
    <details><summary>${L("mapTable")}</summary>${table([L("state"), L("cardRate")], all.map(([c, v]) => [stateName(c), num(v, 1)]))}</details>`;
}

function corridorView() {
  const base = { disease: S.disease, state: S.state, year: S.year };
  const weeks = weeklySeries(ix, base).map((p) => p.week);
  const cs0 = weeks.map((w) => corridor(ix, { ...base, week: w }));
  if (!weeks.length || cs0.every((c) => !c || c.current == null && c.p50 == null)) return `<section class="chart"><h2>${L("corridorTitle")} · ${stateName(S.state)}</h2><p>${L("noData")}</p></section>`;
  const cs = weeks.map((w, i) => ({ w, c: cs0[i] }));
  const pts = (k) => cs.map(({ w, c }) => ({ x: w, y: c ? c[k] : null }));
  const svg = lineChartSVG({ ...size(), title: `${L("corridorTitle")} — ${stateName(S.state)} ${S.year}`, xMax: xMaxOf([weeks.map((x) => ({ x }))]),
    band: { lo: pts("p25"), hi: pts("p75") }, lines: [
      { label: L("median"), color: "#9AA7B4", dash: "5 4", points: pts("p50") },
      { label: String(S.year), color: dis().color, points: cs.map(({ w, c }) => ({ x: w, y: c ? c.current : null })) }] });
  return `<section class="chart"><h2>${L("corridorTitle")} · ${stateName(S.state)}</h2>${svg}
    <p class="key"><span><i style="border-color:${esc(dis().color)}"></i>${S.year}</span><span><i style="border-color:#9AA7B4;border-top-style:dashed"></i>${L("median")}</span><span>${L("band")}</span></p>
    <p class="note">${L("corridorNote")} ${L("corridorGap")}</p></section>`;
}

function renderView() {
  $("view").innerHTML = { Overview: overview, Map: mapView, Corridor: corridorView }[S.tab]();
}

function renderPanel() {
  $("qlist").innerHTML = QUESTIONS.map((q, i) => `<li><button type="button" data-q="${i}" aria-pressed="${S.q === i}">${q[S.lang]}</button></li>`).join("");
  if (S.q == null) $("answer").innerHTML = `<span class="muted">${L("answer")}…</span>`;
  else {
    const a = QUESTIONS[S.q].answer(ix, S.lang);
    $("answer").innerHTML = `<p>${esc(a.text)}</p>${a.rows.length ? table(["", L("cases")], a.rows) : ""}`;
  }
  $("connect").innerHTML = `<h3>${L("connectTitle")}</h3><p class="muted">${L("connectLead")}</p>` +
    (MCP_URL ? `<p>${L("connectUrl")}:</p><code>${esc(MCP_URL)}</code>` : `<p><strong>${L("connectSoon")}</strong></p>`) +
    `<p class="note">${L("connectNote")}</p>`;
}

function renderFoot() {
  $("foot").innerHTML = `<strong>${L("sources")}:</strong><span class="badge">${L("sourceCdc")}</span><span class="badge">${L("sourceCensus")}</span>
    <span>${L("disclaimer")}</span><span>${L("provisional")}</span><span>${L("dataAsOf")} ${ix.data.generated_at.slice(0, 10)}</span>
    <a href="${esc(REPO_URL)}">${L("repo")}</a><a href="${esc(REPO_URL)}/tree/main/data_model">${L("pbip")}</a><span>${L("notIncluded")}</span>`;
}

// render() reconstruye pestañas, filtros y preguntas con innerHTML: se restaura el foco para no romper teclado ni lector de pantalla.
function focusKey(el) {
  if (!el || el === document.body) return null;
  for (const k of ["tab", "q", "lang"]) if (el.dataset?.[k] != null) return `[data-${k}="${el.dataset[k]}"]`;
  return el.id ? `#${el.id}` : null;
}
function render() {
  const key = focusKey(document.activeElement);
  fillStatic(); fillFilters(); renderView(); renderPanel(); renderFoot();
  if (key) document.querySelector(key)?.focus();
}

let tour = null;
const stopTour = () => { if (tour) { clearInterval(tour); tour = null; } };
["click", "change", "keydown"].forEach((ev) => document.addEventListener(ev, stopTour, true));
document.addEventListener("keydown", (e) => {  // flechas entre pestañas (patrón WAI-ARIA)
  const tab = e.target.closest?.("[role=tab]"); if (!tab || !["ArrowLeft", "ArrowRight"].includes(e.key)) return;
  const i = TABS.indexOf(tab.dataset.tab), next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
  S.tab = next; render(); document.getElementById("tab-" + next)?.focus();
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b || !ix) return;
  if (b.dataset.lang) { S.lang = b.dataset.lang; try { localStorage.setItem("lang", S.lang); } catch {} }
  else if (b.dataset.tab) S.tab = b.dataset.tab;
  else if (b.dataset.q) S.q = Number(b.dataset.q);
  else return;
  render();
});
document.addEventListener("change", (e) => {
  if (!ix) return;
  if (e.target.id === "f-disease") S.disease = e.target.value;
  else if (e.target.id === "f-year") S.year = Number(e.target.value);
  else if (e.target.id === "f-state") S.state = e.target.value;
  else return;
  render();
});

async function boot() {
  $("status").textContent = L("loading");
  try {
    const res = await fetch("data/nndss.json"); if (!res.ok) throw new Error(res.status);
    ix = index(await res.json());
  } catch { $("status").textContent = L("loadError"); return; }
  const q = new URLSearchParams(location.search);
  const tab = TABS.find((k) => k.toLowerCase() === q.get("tab")); if (tab) S.tab = tab;
  if (["es", "en"].includes(q.get("lang"))) S.lang = q.get("lang");
  S.year = latestYear();
  if (!ix.data.diseases.some((d) => d.key === S.disease)) S.disease = ix.data.diseases[0].key;
  render();
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderView, 150); });
  if (q.has("tour") && !matchMedia("(prefers-reduced-motion: reduce)").matches)
    tour = setInterval(() => { S.tab = TABS[(TABS.indexOf(S.tab) + 1) % TABS.length]; render(); }, 6000);
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
