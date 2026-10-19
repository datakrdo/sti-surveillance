"""Layout checks for both report definitions (ES and EN): grid, canonical sizes, navigation, sync, colors."""
import json, pathlib, itertools
import pytest

ROOT = pathlib.Path(__file__).parent.parent / "data_model"
REPORTS = {"es": "STI_Surveillance_Model_ES.Report", "en": "STI_Surveillance_Model.Report"}
W, H = 1920, 1080
NAV = 7
CARD = (296, 128)


def load(lang):
    d = ROOT / REPORTS[lang] / "definition" / "pages"
    order = json.loads((d / "pages.json").read_text())["pageOrder"]
    pages = []
    for pid in order:
        vis = [json.loads(f.read_text()) for f in sorted((d / pid / "visuals").glob("*/visual.json"))]
        pages.append((pid, vis))
    return pages


def is_nav(v):
    return v["visual"]["visualType"] == "actionButton" and         v["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["type"]["expr"]["Literal"]["Value"] == "'PageNavigation'"


def lit(obj, *path):
    for p in path:
        obj = obj[p]
    return obj["expr"]["Literal"]["Value"] if "expr" in obj else obj


@pytest.fixture(params=["es", "en"])
def pages(request):
    return load(request.param)


def test_seven_pages(pages):
    assert len(pages) == 7


def test_inside_canvas_on_8px_grid(pages):
    for pid, vis in pages:
        for v in vis:
            p = v["position"]
            for k in ("x", "y", "width", "height"):
                assert p[k] % 8 == 0, (pid, v["name"], k, p[k])
            assert p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["width"] <= W and p["y"] + p["height"] <= H, (pid, v["name"])


def test_no_overlaps(pages):
    for pid, vis in pages:
        for a, b in itertools.combinations(vis, 2):
            pa, pb = a["position"], b["position"]
            sep = (pa["x"] + pa["width"] <= pb["x"] or pb["x"] + pb["width"] <= pa["x"]
                   or pa["y"] + pa["height"] <= pb["y"] or pb["y"] + pb["height"] <= pa["y"])
            assert sep, (pid, a["name"], b["name"])


def test_cards_share_one_size(pages):
    sizes = {(v["position"]["width"], v["position"]["height"])
             for _, vis in pages for v in vis if v["visual"]["visualType"] == "cardVisual"}
    assert sizes == {CARD}


def test_navigation_identical_on_every_page(pages):
    seen = None
    page_ids = [pid for pid, _ in pages]
    for i, (pid, vis) in enumerate(pages):
        nav = sorted((v for v in vis if is_nav(v)), key=lambda v: v["position"]["x"])
        assert len(nav) == NAV, pid
        geo = [(v["position"]["x"], v["position"]["y"], v["position"]["width"], v["position"]["height"]) for v in nav]
        targets = [lit(v["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["navigationSection"])
                   for v in nav]
        assert [t.strip("'") for t in targets] == page_ids, pid
        seen = seen or geo
        assert geo == seen, pid


def test_slicers_synced_by_field(pages):
    expected = {"dim_disease.disease_key": "sync_disease", "dim_mmwr_week.mmwr_year": "sync_year",
                "dim_epi_month.mmwr_year": "sync_year_or"}
    for pid, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] != "slicer":
                continue
            ref = v["visual"]["query"]["queryState"]["Values"]["projections"][0]["queryRef"]
            if ref in expected:
                assert v["visual"]["syncGroup"]["groupName"] == expected[ref], (pid, ref)


def test_same_slicer_same_size(pages):
    by_field = {}
    for _, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] == "slicer":
                ref = v["visual"]["query"]["queryState"]["Values"]["projections"][0]["queryRef"]
                by_field.setdefault(ref, set()).add((v["position"]["x"], v["position"]["y"],
                                                     v["position"]["width"], v["position"]["height"]))
    for ref in ("dim_disease.disease_key", "dim_mmwr_week.mmwr_year"):
        assert len(by_field[ref]) == 1, (ref, by_field[ref])


def test_disease_color_only_on_disease_slicer(pages):
    for pid, vis in pages:
        for v in vis:
            uses = "Disease Color" in json.dumps(v)
            is_disease_slicer = v["visual"]["visualType"] == "slicer" and                 "dim_disease.disease_key" in json.dumps(v["visual"]["query"])
            assert uses == is_disease_slicer, (pid, v["name"])


def test_gridlines(pages):
    for pid, vis in pages:
        for v in vis:
            vt = v["visual"]["visualType"]
            ax = v["visual"].get("objects", {}).get("valueAxis", [{}])[0].get("properties", {})
            if vt in ("barChart", "columnChart", "hundredPercentStackedBarChart"):
                assert lit(ax["gridlineShow"]) == "false", (pid, v["name"])
            if vt == "lineChart":
                assert lit(ax["gridlineStyle"]) == "'dashed'", (pid, v["name"])


def test_filter_band_aligned(pages):
    for pid, vis in pages:
        sl = sorted((v for v in vis if v["visual"]["visualType"] == "slicer"), key=lambda v: v["position"]["x"])
        assert all(v["position"]["y"] == 80 for v in sl), pid
        for a, b in zip(sl, sl[1:]):
            assert a["position"]["x"] + a["position"]["width"] < b["position"]["x"], pid


def test_nav_buttons_show_label(pages):
    labels = None
    for pid, vis in pages:
        nav = sorted((v for v in vis if is_nav(v)), key=lambda v: v["position"]["x"])
        cur = []
        for v in nav:
            text = v["visual"]["objects"]["text"]
            assert lit(text[0]["properties"]["show"]) == "true", (pid, v["name"])
            cur.append(lit(text[1]["properties"]["text"]))
        labels = labels or cur
        assert cur == labels and len(set(cur)) == NAV, pid


def test_font_sizes_at_least_11pt(pages):
    for pid, vis in pages:
        for v in vis:
            for size in _sizes(v):
                assert size >= 11, (pid, v["name"], size)


def _sizes(node):
    if isinstance(node, dict):
        for k, val in node.items():
            if k == "fontSize":
                s = val["expr"]["Literal"]["Value"] if isinstance(val, dict) and "expr" in val else val
                yield float(str(s).strip("'").replace("D", "").replace("pt", ""))
            else:
                yield from _sizes(val)
    elif isinstance(node, list):
        for x in node:
            yield from _sizes(x)


def test_es_and_en_share_geometry():
    es, en = load("es"), load("en")
    for (pa, va), (pb, vb) in zip(es, en):
        assert pa == pb
        box = lambda v: {k: v["position"][k] for k in ("x", "y", "width", "height")}   # z/tabOrder los reescribe Desktop
        ga = {v["name"]: box(v) for v in va}
        gb = {v["name"]: box(v) for v in vb}
        assert ga == gb, pa


def test_every_visual_has_alt_text(pages):
    for pid, vis in pages:
        for v in vis:
            alt = v["visual"].get("visualContainerObjects", {}).get("general", [{}])[0].get("properties", {}).get("altText")
            assert alt, (pid, v["name"])


def test_filter_band_fits_and_content_below(pages):
    for pid, vis in pages:
        for v in vis:
            p, vt = v["position"], v["visual"]["visualType"]
            if vt == "slicer":
                assert p["height"] >= 96 and p["y"] + p["height"] <= 192, (pid, v["name"])
            elif vt in ("cardVisual", "lineChart", "barChart", "filledMap", "tableEx"):
                assert p["y"] >= 192, (pid, v["name"], p["y"])


def test_card_values_centered(pages):
    for pid, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] != "cardVisual":
                continue
            entries = [e for e in v["visual"]["objects"]["value"] if e.get("selector") == {"id": "default"}]
            assert entries and lit(entries[0]["properties"]["horizontalAlignment"]) == "'center'", (pid, v["name"])


def test_sources_hidden_link(pages):
    for pid, vis in pages:
        links = [v for v in vis if v["visual"]["visualType"] == "actionButton" and not is_nav(v)]
        assert len(links) == 3, pid
        for v in links:
            lk = v["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
            assert lit(lk["type"]) == "'WebUrl'" and lit(lk["webUrl"]).startswith("'https://"), (pid, v["name"])
        for v in vis:
            if v["visual"]["visualType"] == "textbox":
                for pr in v["visual"]["objects"]["general"][0]["properties"]["paragraphs"]:
                    assert all("url" not in r and "textDecoration" not in r["textStyle"] for r in pr["textRuns"]), pid


def test_kpi_titles_short_without_subtitle(pages):
    for pid, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] == "cardVisual":
                c = v["visual"]["visualContainerObjects"]
                assert len(lit(c["title"][0]["properties"]["text"])) <= 26, (pid, v["name"])
                assert lit(c["subTitle"][0]["properties"]["show"]) == "false", (pid, v["name"])


def test_disease_slicer_open(pages):
    for pid, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] == "slicer" and                     v["visual"]["query"]["queryState"]["Values"]["projections"][0]["queryRef"] == "dim_disease.disease_key":
                o = v["visual"]["objects"]
                assert v["position"]["width"] >= 880 and lit(o["data"][0]["properties"]["mode"]) == "'Basic'", pid
                assert lit(o["general"][0]["properties"]["orientation"]) == "1D", pid
                assert lit(o["selection"][0]["properties"]["selectAllCheckboxEnabled"]) == "false", pid


def test_demographics_chart_types(pages):
    pid, vis = pages[5]
    kinds = {}
    for v in vis:
        refs = [pr["queryRef"] for r in v["visual"].get("query", {}).get("queryState", {}).values() for pr in r["projections"]]
        for k in ("sex", "age_group", "race_group"):
            if f"dim_demographic.{k}" in refs:
                kinds[k] = v["visual"]["visualType"]
    assert kinds == {"sex": "hundredPercentStackedBarChart", "age_group": "columnChart", "race_group": "barChart"}


def test_sex_labels_one_decimal(pages):
    pid, vis = pages[5]
    sex = [v for v in vis if v["visual"]["visualType"] == "hundredPercentStackedBarChart"]
    assert len(sex) == 1
    assert lit(sex[0]["visual"]["objects"]["labels"][0]["properties"]["labelPrecision"]) == "1D"


def test_sex_chart_only_female_male_with_note(pages):
    pid, vis = pages[5]
    sex = next(v for v in vis if v["visual"]["visualType"] == "hundredPercentStackedBarChart")
    f = next(f for f in sex["filterConfig"]["filters"] if f["field"]["Column"]["Property"] == "sex")
    vals = [x[0]["Literal"]["Value"] for x in f["filter"]["Where"][0]["Condition"]["In"]["Values"]]
    assert vals == ["'Female'", "'Male'"]
    assert any("Nonbinary" in r["value"] for v in vis if v["visual"]["visualType"] == "textbox"
               for p in v["visual"]["objects"]["general"][0]["properties"]["paragraphs"] for r in p["textRuns"])


def test_disease_slicer_lists_only_diseases_with_data(pages):
    for i, (pid, vis) in enumerate(pages):
        for v in vis:
            if v["visual"]["visualType"] == "slicer" and "dim_disease.disease_key" in json.dumps(v["visual"]["query"]):
                vals = [x[0]["Literal"]["Value"].strip("'") for x in
                        v["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"]["In"]["Values"]]
                if i < 4:   # NNDSS
                    assert vals == ["CHL", "GON", "SYP_PS", "SYP_CONG"], pid
                elif i < 6:  # Oregon
                    assert "SYP_PS" not in vals and {"HIV", "SYP_EARLY"} <= set(vals), pid


def test_oregon_county_labels_without_suffix(pages):
    pid, vis = pages[4]
    for v in vis:
        if v["visual"]["visualType"] in ("barChart", "tableEx"):
            refs = [pr["queryRef"] for r in v["visual"]["query"]["queryState"].values() for pr in r["projections"]]
            assert "dim_geography.county_label" in refs and "dim_geography.county_name" not in refs, v["name"]
