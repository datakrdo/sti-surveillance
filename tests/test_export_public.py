import json
from scripts.export_public import build_payload

DISEASES = [("CHL", "Chlamydia"), ("GON", "Gonorrea"), ("HIV", "VIH"), ("SYP_EARLY", "Sífilis temprana"),
            ("SYP_PS", "Sífilis primaria y secundaria"), ("SYP_CONG", "Sífilis congénita")]
WEEKS = [(202401, 2024, 1, "2023-12-31"), (202402, 2024, 2, "2024-01-07")]
STATES = [("CA", "California"), ("OR", "Oregon")]
ROWS = [(202401, "CHL", "CA", 123, 39000000), (202402, "GON", "OR", None, 4200000)]


def payload():
    return build_payload(ROWS, WEEKS, DISEASES, STATES, 202401)


def test_payload_shape_and_no_restricted_fields():
    p = payload()
    assert set(p) == {"generated_at", "ref_week", "latest_week", "diseases", "states", "weeks", "cols", "rows"}
    assert p["cols"] == ["w", "d", "s", "cases", "pop"]
    assert p["rows"][1][3] is None and p["rows"][0] == [202401, "CHL", "CA", 123, 39000000]
    assert p["latest_week"] == 202402 and p["ref_week"] == 202401
    text = json.dumps(p).lower()
    for bad in ("race", "age_group", "revision", "or|"):
        assert bad not in text


def test_only_nndss_diseases():
    p = payload()
    assert [d["key"] for d in p["diseases"]] == ["CHL", "GON", "SYP_PS", "SYP_CONG"]
    assert {d["key"]: d["color"] for d in p["diseases"]} == {
        "CHL": "#56B4E9", "GON": "#E69F00", "SYP_PS": "#009E73", "SYP_CONG": "#EF7B3A"}
    assert p["diseases"][0]["name_en"] == "Chlamydia" and p["diseases"][0]["name_es"] == "Clamidia"
    assert [d["name_es"] for d in p["diseases"]] == ["Clamidia", "Gonorrea", "Sífilis primaria y secundaria", "Sífilis congénita"]


def test_decimals_become_json_numbers():
    from decimal import Decimal
    p = build_payload([(202401, "CHL", "CA", Decimal("123.0"), Decimal("39000000"))], WEEKS, DISEASES, STATES, 202401)
    assert json.loads(json.dumps(p, default=str))["rows"][0] == [202401, "CHL", "CA", 123, 39000000]
    assert all(isinstance(v, int) for v in p["rows"][0][3:])
