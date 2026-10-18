import { t } from "./i18n.js";
import { casesTotal, ratePer100k, yoy, statesInOutbreak, topStates } from "./metrics.js";

const num = (n, lang, d = 0) => n.toLocaleString(lang, { maximumFractionDigits: d, minimumFractionDigits: d });
const dName = (ix, key, lang) => ix.data.diseases.find((d) => d.key === key)?.[`name_${lang}`] ?? key;
const sName = (ix, code) => ix.data.states.find((s) => s.code === code)?.name ?? code;
const none = (lang) => ({ text: t(lang, "noData"), rows: [] });
const when = (ix) => ({ year: Math.floor(ix.data.latest_week / 100), week: ix.data.latest_week % 100 });

export const QUESTIONS = [
  { id: "latest-week",
    es: "¿Cuántos casos se notificaron en la última semana, por enfermedad?",
    en: "How many cases were reported in the latest week, by disease?",
    answer(ix, lang) {
      const { year, week } = when(ix);
      const rows = ix.data.diseases.map((d) => [dName(ix, d.key, lang), casesTotal(ix, { disease: d.key, year, weekFrom: week, weekTo: week })])
        .filter((r) => r[1] != null).map(([n, c]) => [n, num(c, lang)]);
      if (!rows.length) return none(lang);
      return { text: lang === "es" ? `Semana ${week} de ${year}, todos los estados:` : `Week ${week} of ${year}, all states:`, rows };
    } },
  { id: "top-gon",
    es: "¿Qué cinco estados tienen más casos de gonorrea este año?",
    en: "Which five states have the most gonorrhea cases this year?",
    answer(ix, lang) {
      const { year } = when(ix);
      const rows = topStates(ix, { disease: "GON", year, n: 5 }).map((r) => [sName(ix, r.state), num(r.cases, lang)]);
      if (!rows.length) return none(lang);
      return { text: lang === "es" ? `Gonorrea, casos acumulados en ${year}:` : `Gonorrhea, cumulative cases in ${year}:`, rows };
    } },
  { id: "rate-chl",
    es: "¿Cuál fue la tasa de clamidia por 100 mil en todo el país el año pasado?",
    en: "What was the national chlamydia rate per 100k last year?",
    answer(ix, lang) {
      const year = when(ix).year - 1;
      const r = ratePer100k(ix, { disease: "CHL", year });
      if (r == null) return none(lang);
      return { text: lang === "es" ? `Clamidia ${year}: ${num(r, lang, 1)} casos por 100 mil persona-años (EE. UU.).`
                                   : `Chlamydia ${year}: ${num(r, lang, 1)} cases per 100k person-years (U.S.).`, rows: [] };
    } },
  { id: "yoy-gon",
    es: "¿La gonorrea sube o baja respecto al mismo periodo del año anterior?",
    en: "Is gonorrhea up or down versus the same period last year?",
    answer(ix, lang) {
      const { year, week } = when(ix);
      const r = yoy(ix, { disease: "GON", year, throughWeek: week });
      if (!r) return none(lang);
      const dir = r.pct < 0 ? (lang === "es" ? "baja" : "down") : (lang === "es" ? "sube" : "up");
      return { text: lang === "es"
        ? `Gonorrea hasta la semana ${week}: ${num(r.current, lang)} casos en ${year} frente a ${num(r.previous, lang)} en ${year - 1} (${dir} ${num(Math.abs(r.pct), lang, 1)} %).`
        : `Gonorrhea through week ${week}: ${num(r.current, lang)} cases in ${year} vs ${num(r.previous, lang)} in ${year - 1} (${dir} ${num(Math.abs(r.pct), lang, 1)}%).`, rows: [] };
    } },
  { id: "outbreak",
    es: "¿Cuántos estados superan su percentil 75 de gonorrea en la semana de referencia?",
    en: "How many states exceed their gonorrhea 75th percentile in the reference week?",
    answer(ix, lang) {
      if (!ix.hasData) return none(lang);
      const n = statesInOutbreak(ix, { disease: "GON", weekKey: ix.data.ref_week });
      const wk = ix.data.ref_week % 100, y = Math.floor(ix.data.ref_week / 100);
      return { text: lang === "es" ? `${n} estados superan su P75 histórico de gonorrea en la semana ${wk} de ${y}.`
                                   : `${n} states exceed their historical gonorrhea P75 in week ${wk} of ${y}.`, rows: [] };
    } },
];
