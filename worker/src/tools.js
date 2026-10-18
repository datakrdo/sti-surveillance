import { z } from "zod";
import { index, casesTotal, ratePer100k, yoy, corridor, topStates } from "../../site/js/metrics.js";

const DISEASES = ["CHL", "GON", "SYP_PS", "SYP_CONG"];
const disease = z.enum(DISEASES).describe("CHL chlamydia, GON gonorrhea, SYP_PS primary & secondary syphilis, SYP_CONG congenital syphilis");
const state = z.string().regex(/^[A-Z]{2}$/).describe("Two-letter state code, e.g. CA");
const year = z.number().int().min(2022).max(2030);
const week = z.number().int().min(1).max(53);

export const DEFINITIONS = `Public NNDSS weekly STI notifications (CDC) with Census population. Read-only aggregates; no free SQL.
- cases: sum of weekly cases. A missing value (NNDSS code 'U') is unknown, never 0, and is ignored in sums.
- rate_per_100k: cases x 100000 / person-years, where person-years = sum of weekly state populations / (365.25/7), using weeks with population > 0 and a known case count.
- yoy: compares the same MMWR weeks of the previous year.
- corridor: P25/P50/P75 (linear percentiles) of the same MMWR week across earlier years with data.
- Source: CDC NNDSS (data.cdc.gov) and U.S. Census Bureau. Independent project, not affiliated with these entities.
- Not included: the Oregon Health Authority dataset (county and demographic cuts), demographics (sex, age, race) and revision history. Oregon's state-level rows here come from CDC NNDSS.`;

// El índice cuesta 4-10 ms de CPU: se calcula una vez por objeto de datos y no en cada llamada (límite de 10 ms del plan gratis).
const ixCache = new WeakMap();
export const ixOf = (data) => ixCache.get(data) ?? (ixCache.set(data, index(data)), ixCache.get(data));

const text = (obj) => ({ content: [{ type: "text", text: typeof obj === "string" ? obj : JSON.stringify(obj) }] });
const fail = (msg) => ({ isError: true, content: [{ type: "text", text: msg }] });

// loadData(): Promise<objeto de nndss.json>. Se inyecta para poder probar sin red.
export function makeTools(loadData) {
  const def = (name, description, shape, fn) => ({
    name, description, shape,
    async run(args) {
      const parsed = z.object(shape).strict().safeParse(args ?? {});
      if (!parsed.success)
        return fail("Invalid arguments: " + parsed.error.issues.map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("; "));
      let ix;
      try { ix = ixOf(await loadData()); } catch { return fail("The public data could not be loaded right now. Try again later."); }
      const a = parsed.data;
      if (a.state && !ix.data.states.some((s) => s.code === a.state)) return fail(`Unknown state "${a.state}". Use list_dimensions for valid codes.`);
      return fn(ix, a);
    },
  });
  return [
    def("list_dimensions", "Lists diseases, states, week range and data date. Call this first.", {}, (ix) => text({
      diseases: ix.data.diseases.map(({ key, name_en, name_es }) => ({ key, name_en, name_es })),
      states: ix.data.states, first_week: ix.data.weeks[0]?.key, latest_week: ix.data.latest_week,
      reference_week: ix.data.ref_week, data_generated_at: ix.data.generated_at, definitions: DEFINITIONS })),
    def("get_cases", "Total reported cases for a disease, optionally by state and week range, in one MMWR year.",
      { disease, state: state.optional(), year, week_from: week.optional(), week_to: week.optional() },
      (ix, a) => text({ ...a, cases: casesTotal(ix, { disease: a.disease, state: a.state, year: a.year, weekFrom: a.week_from, weekTo: a.week_to }) })),
    def("get_rate_per_100k", "Annualized rate per 100,000 person-years for a disease, optionally by state, in one MMWR year.",
      { disease, state: state.optional(), year },
      (ix, a) => text({ ...a, rate_per_100k: ratePer100k(ix, { disease: a.disease, state: a.state, year: a.year }) })),
    def("get_yoy", "Cases through a given week versus the same weeks of the previous year.",
      { disease, state: state.optional(), year, through_week: week },
      (ix, a) => text({ ...a, result: yoy(ix, { disease: a.disease, state: a.state, year: a.year, throughWeek: a.through_week }) })),
    def("get_corridor", "Endemic corridor (P25/P50/P75 of earlier years) and the selected year's value for one state and week.",
      { disease, state, week, year },
      (ix, a) => text({ ...a, corridor: corridor(ix, { disease: a.disease, state: a.state, week: a.week, year: a.year }) })),
    def("top_states", "States with the most cases in a year or in one week (week_key = YYYYWW). Up to 10.",
      { disease, year: year.optional(), week_key: z.number().int().min(202201).max(203053).optional(), n: z.number().int().min(1).max(10) },
      (ix, a) => a.year == null && a.week_key == null ? fail("Provide year or week_key.")
        : text({ ...a, states: topStates(ix, { disease: a.disease, year: a.year, weekKey: a.week_key, n: a.n }) })),
  ];
}
