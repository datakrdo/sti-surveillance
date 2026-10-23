import csv, io, os, re
from operator import itemgetter
import requests, psycopg2
from psycopg2.extras import execute_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# reintenta caídas de DNS/conexión y 429/5xx con espera creciente (2, 4, 8, 16, 32 s)
http = requests.Session()
http.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))))

NNDSS = "https://data.cdc.gov/resource/x9gk-5huc.json"
OREGON = "https://data.oregon.gov/resource/rk77-sqhz.json"
CENSUS = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv"
NNDSS_LABELS = ("Chlamydia trachomatis infection", "Gonorrhea", "Syphilis, Primary and secondary", "Syphilis, Congenital")
OREGON_DISEASES = ("Chlamydia", "Gonorrhea", "Early syphilis", "Congenital syphilis", "HIV")
PAGE = 50000


def soql(url, where):
    rows, offset = [], 0
    while True:
        r = http.get(url, params={"$where": where, "$order": ":id", "$limit": PAGE, "$offset": offset}, timeout=120)
        r.raise_for_status()
        page = r.json()
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def num(v):
    return None if v in (None, "", "NA") else float(v)


def clean(v):
    return re.sub(r"\s+", " ", v).strip() if v else v


def day(v):  # Oregon trae '2021:1:03T...' en algunos start
    if not v:
        return None
    y, m, d = re.split(r"[-:]", v.split("T")[0])
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def in_list(col, vals):
    return f"{col} in (" + ",".join("'" + v.replace("'", "''") + "'" for v in vals) + ")"


def norm_nndss(r):
    return (int(r["year"]), int(r["week"]), r["label"], r["states"], r.get("location1"), r.get("location2"),
            num(r.get("m1")), r.get("m1_flag"), num(r.get("m2")), r.get("m2_flag"),
            num(r.get("m3")), r.get("m3_flag"), num(r.get("m4")), r.get("m4_flag"), r.get("sort_order"))


def norm_oregon(r):
    cases = num(r.get("count_masked"))
    return (int(r["mmwr_year"]), int(r["month"]), day(r.get("report_period_start")), day(r.get("report_period_end")),
            r["disease_name"], r["demographic"], clean(r["demographic_level"]), clean(r.get("geo_name")),
            r.get("geo_unit"), r.get("age_group"), r["confirmation_status"],
            None if cases is None else int(cases), r.get("masked") == "1", r.get("count_label"),
            num(r.get("population")), r.get("pop_source"), day(r.get("run_date")))


def norm_census(row):
    return [(row["NAME"], y, int(row[f"POPESTIMATE{y}"]), row["REGION"], row["DIVISION"])
            for y in range(2020, 2026) if row.get(f"POPESTIMATE{y}")]


def dedupe(rows, key):
    return list({key(t): t for t in rows}.values())  # último gana


OREGON_PK = itemgetter(0, 1, 4, 5, 6, 10)


def upsert(cur, table, cols, pk, rows):
    upd = ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in pk) + ",ingested_at=now()"
    execute_values(cur, f"INSERT INTO {table} ({','.join(cols)}) VALUES %s "
                        f"ON CONFLICT ({','.join(pk)}) DO UPDATE SET {upd}", rows, page_size=5000)


def main():
    nndss = [norm_nndss(r) for r in soql(NNDSS, in_list("label", NNDSS_LABELS))]
    oregon = dedupe([norm_oregon(r) for r in soql(OREGON, in_list("disease_name", OREGON_DISEASES))], OREGON_PK)
    census = [t for row in csv.DictReader(io.StringIO(http.get(CENSUS, timeout=120).text)) for t in norm_census(row)]
    assert nndss and oregon and census, "fuente vacía: abortar sin tocar la base"
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        upsert(cur, "raw.nndss_weekly",
               ["year", "week", "label", "states", "location1", "location2", "m1", "m1_flag", "m2", "m2_flag",
                "m3", "m3_flag", "m4", "m4_flag", "sort_order"], ["year", "week", "label", "states"], nndss)
        upsert(cur, "raw.oregon_monthly",
               ["mmwr_year", "month", "report_period_start", "report_period_end", "disease_name", "demographic",
                "demographic_level", "geo_name", "geo_unit", "age_group", "confirmation_status", "cases",
                "is_masked", "count_label", "population", "pop_source", "run_date"],
               ["mmwr_year", "month", "disease_name", "demographic", "demographic_level", "confirmation_status"], oregon)
        upsert(cur, "raw.census_population", ["name", "year", "population", "region", "division"], ["name", "year"], census)
    print(f"nndss={len(nndss)} oregon={len(oregon)} census={len(census)}")


if __name__ == "__main__":
    main()
