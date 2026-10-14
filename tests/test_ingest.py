from scripts.ingest import norm_nndss, norm_oregon, norm_census, day


def test_oregon_masked_is_null_not_zero():
    r = {"mmwr_year": "2026", "month": "8", "report_period_start": "2026-08-02T00:00:00.000",
         "report_period_end": "2026-08-29T00:00:00.000", "disease_name": "Gonorrhea",
         "demographic": "Sex", "demographic_level": "Nonbinary", "geo_name": "Oregon",
         "geo_unit": "state", "age_group": "total", "confirmation_status": "confirmed and presumptive",
         "count_masked": "NA", "count_label": "<6", "masked": "1", "population": "NA",
         "pop_source": "NA", "run_date": "2026-10-14T00:00:00.000"}
    t = norm_oregon(r)
    assert t[11] is None and t[12] is True and t[14] is None


def test_oregon_malformed_date():
    assert day("2021:1:03T00:00:00.000") == "2021-01-03"
    assert day("2026-08-29T00:00:00.000") == "2026-08-29"


def test_oregon_collapses_whitespace():
    r = {"mmwr_year": "2026", "month": "1", "disease_name": "Chlamydia", "demographic": "Geography",
         "demographic_level": "Multnomah  County", "geo_name": "Multnomah", "geo_unit": "county",
         "confirmation_status": "confirmed", "count_masked": "294", "masked": "0", "population": "801546"}
    t = norm_oregon(r)
    assert t[6] == "Multnomah County" and t[11] == 294 and t[12] is False


def test_nndss_missing_counts_are_null():
    r = {"year": "2026", "week": "40", "label": "Gonorrhea", "states": "CALIFORNIA",
         "location1": "CALIFORNIA", "m1_flag": "-", "m2": "1453", "sort_order": "x"}
    t = norm_nndss(r)
    assert t[:4] == (2026, 40, "Gonorrhea", "CALIFORNIA") and t[6] is None and t[8] == 1453.0


def test_census_unpivots_years():
    row = {"NAME": "Oregon", "REGION": "4", "DIVISION": "9",
           **{f"POPESTIMATE{y}": str(4_200_000 + y) for y in range(2020, 2026)}}
    out = norm_census(row)
    assert len(out) == 6 and out[0] == ("Oregon", 2020, 4_202_020, "4", "9")


def test_oregon_whitespace_variants_collapse_to_one_pk():
    from scripts.ingest import dedupe, OREGON_PK
    base = {"mmwr_year": "2026", "month": "1", "disease_name": "Chlamydia", "demographic": "Geography",
            "geo_name": "Multnomah", "geo_unit": "county", "confirmation_status": "confirmed",
            "count_masked": "294", "masked": "0", "population": "1"}
    rows = [norm_oregon({**base, "demographic_level": "Multnomah  County"}),
            norm_oregon({**base, "demographic_level": "Multnomah County"})]
    assert len(dedupe(rows, OREGON_PK)) == 1


def test_http_session_retries_connection_errors_and_5xx():
    from scripts.ingest import http
    retry = http.get_adapter("https://data.oregon.gov").max_retries
    assert retry.total >= 5 and retry.backoff_factor > 0
    assert {429, 500, 502, 503, 504} <= set(retry.status_forcelist)
