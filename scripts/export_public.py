"""Exporta los agregados públicos de NNDSS (sin Oregon, demografía ni revisiones) para el sitio y el MCP remoto."""
import json, os, pathlib
from contextlib import closing
from datetime import datetime, timezone
import psycopg2

OUT = pathlib.Path(__file__).parent.parent / "site" / "data"
# solo las 4 enfermedades de NNDSS; el color es el fijo del informe (theme/dark_accessible.json)
DISEASES = {"CHL": ("Chlamydia", "#56B4E9"), "GON": ("Gonorrhea", "#E69F00"),
            "SYP_PS": ("Primary & secondary syphilis", "#009E73"), "SYP_CONG": ("Congenital syphilis", "#EF7B3A")}
NAME_ES = {"CHL": "Clamidia", "GON": "Gonorrea", "SYP_PS": "Sífilis primaria y secundaria", "SYP_CONG": "Sífilis congénita"}
M = "analytics_marts."
RATE = ("round(sum(cases_week) filter (where population>0)*100000 / (sum(population) filter "
        "(where population>0 and cases_week is not null)/(365.25/7)), 3)")
JOIN = f"from {M}fct_nndss_weekly f join {M}dim_mmwr_week w using (epi_week_key)"


def num(v):  # numeric de Postgres llega como Decimal; los nulos se conservan
    return None if v is None else int(v) if v == int(v) else float(v)


def build_payload(rows, weeks, diseases, states, ref_week):
    present = {k for k, _ in diseases}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ref_week": ref_week,
        "latest_week": max(r[0] for r in rows),
        "diseases": [{"key": k, "name_es": NAME_ES[k], "name_en": DISEASES[k][0], "color": DISEASES[k][1]}
                     for k in DISEASES if k in present],
        "states": [{"code": c, "name": n} for c, n in states],
        "weeks": [{"key": k, "year": y, "week": w, "start": str(s)} for k, y, w, s in weeks],
        "cols": ["w", "d", "s", "cases", "pop"],
        "rows": [[r[0], r[1], r[2], num(r[3]), num(r[4])] for r in rows if r[1] in DISEASES],
    }


def anchors(cur):
    def one(sql):
        cur.execute(sql)
        return cur.fetchone()
    cur.execute(f"select disease_key, sum(cases_week) from {M}fct_nndss_weekly group by 1 order by 1")
    a2 = {k: int(v) for k, v in cur.fetchall()}
    a5 = one(f"""select sum(cases_week) filter (where w.mmwr_year=2026 and w.mmwr_week<=40),
        sum(cases_week) filter (where w.mmwr_year=2025 and w.mmwr_week<=40),
        sum(cases_week) filter (where w.epi_week_key=202640), sum(cases_week) filter (where w.epi_week_key=202540)
        {JOIN} where f.disease_key='GON'""")
    p25, p50, p75 = one(f"""select percentile_cont(0.25) within group (order by cases_week),
        percentile_cont(0.5) within group (order by cases_week), percentile_cont(0.75) within group (order by cases_week)
        {JOIN} where f.geo_key='CA' and f.disease_key='GON' and w.mmwr_week=40 and w.mmwr_year between 2021 and 2025""")
    a7 = one(f"""with p as (select f.geo_key, percentile_cont(0.75) within group (order by f.cases_week) p75
        {JOIN} where f.disease_key='GON' and w.mmwr_week=40 and w.mmwr_year between 2021 and 2025 group by 1)
        select count(*) filter (where f.cases_week > p.p75) from {M}fct_nndss_weekly f join p using (geo_key)
        where f.disease_key='GON' and f.epi_week_key=202640""")[0]
    cur.execute(f"select f.geo_key, sum(f.cases_week) {JOIN} where f.disease_key='GON' and w.mmwr_year=2025 "
                "and f.geo_key in ('OR','CA') group by 1 order by 1")
    a13 = {k: int(v) for k, v in cur.fetchall()}  # antes de más consultas: reutilizan el cursor
    f = lambda x: None if x is None else float(x)
    return {
        "A2": a2,
        "A3": int(one(f"select cases_week from {M}fct_nndss_weekly where geo_key='CA' and disease_key='GON' and epi_week_key=202452")[0]),
        "A4": [f(one(f"select {RATE} {JOIN} where f.geo_key='CA' and f.disease_key='CHL' and w.mmwr_year=2024")[0]),
               f(one(f"select {RATE} {JOIN} where f.disease_key='GON' and w.mmwr_year=2025")[0])],
        "A5": dict(zip(("y26", "ly_mmwr", "w40_26", "w40_25"), (int(x) for x in a5))),
        "A6": {"p25": f(p25), "p50": f(p50), "p75": f(p75)},
        "A7": int(a7),
        "A8": [int(x) for x in one(f"select (select epi_week_key from {M}dim_mmwr_week where is_reference_week), "
                                    f"(select max(epi_week_key) from {M}fct_nndss_weekly)")],
        "A13": a13,
    }


def main():
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as conn, conn.cursor() as cur:
        cur.execute(f"select epi_week_key, disease_key, geo_key, cases_week, population from {M}fct_nndss_weekly "
                    "order by 1, 2, 3")
        rows = cur.fetchall()
        cur.execute(f"select epi_week_key, mmwr_year, mmwr_week, week_start_date from {M}dim_mmwr_week "
                    "where epi_week_key between 202201 and (select max(epi_week_key) from "
                    f"{M}fct_nndss_weekly) order by 1")
        weeks = cur.fetchall()
        cur.execute(f"select disease_key, disease_name from {M}dim_disease order by 1")
        diseases = cur.fetchall()
        cur.execute(f"select state_code, state_name from {M}dim_geography where geo_level='state' order by 1")
        states = cur.fetchall()
        cur.execute(f"select epi_week_key from {M}dim_mmwr_week where is_reference_week")
        ref = cur.fetchone()[0]
        a = anchors(cur)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nndss.json").write_text(json.dumps(build_payload(rows, weeks, diseases, states, ref),
                                               separators=(",", ":"), ensure_ascii=False, default=str))
    (OUT / "anchors.json").write_text(json.dumps(a, indent=1))


if __name__ == "__main__":
    main()
