"""Layout checks for both report definitions (ES and EN): grid, canonical sizes, navigation, sync, colors."""
import json, pathlib, itertools
import pytest

ROOT = pathlib.Path(__file__).parent.parent / "data_model"
REPORTS = {"es": "STI_Surveillance_Model.Report", "en": "STI_Surveillance_Model_EN.Report"}
W, H = 1920, 1080
NAV = 7
CARD = (296, 128)
DISEASE_COLORS = {"CHL": "#56B4E9", "GON": "#E69F00", "SYP_PS": "#009E73",
                  "SYP_EARLY": "#F0E442", "SYP_CONG": "#EF7B3A", "HIV": "#CC79A7"}


def load(lang):
    d = ROOT / REPORTS[lang] / "definition" / "pages"
    order = json.loads((d / "pages.json").read_text())["pageOrder"]
    pages = []
    for pid in order:
        vis = [json.loads(f.read_text()) for f in sorted((d / pid / "visuals").glob("*/visual.json"))]
        pages.append((pid, vis))
    return pages


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
        nav = sorted((v for v in vis if v["visual"]["visualType"] == "actionButton"),
                     key=lambda v: v["position"]["x"])
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


def test_bars_use_disease_color_measure(pages):
    n = 0
    for pid, vis in pages:
        for v in vis:
            if v["visual"]["visualType"] == "barChart":
                fill = v["visual"]["objects"]["dataPoint"][0]["properties"]["fill"]
                assert fill["solid"]["color"]["expr"]["Measure"]["Property"] == "Disease Color", (pid, v["name"])
                n += 1
    assert n >= 6


def test_legend_lists_all_diseases(pages):
    for pid, vis in pages:
        if pid == pages[-1][0]:
            continue
        text = json.dumps([v for v in vis if v["visual"]["visualType"] == "textbox"])
        for code, color in DISEASE_COLORS.items():
            assert code in text and color in text, (pid, code)


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
        ga = {v["name"]: v["position"] for v in va}
        gb = {v["name"]: v["position"] for v in vb}
        assert ga == gb, pa


def test_every_visual_has_alt_text(pages):
    for pid, vis in pages:
        for v in vis:
            alt = v["visual"].get("visualContainerObjects", {}).get("general", [{}])[0].get("properties", {}).get("altText")
            assert alt, (pid, v["name"])
