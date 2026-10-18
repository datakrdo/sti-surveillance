"""Aplica la grilla, la navegación, la cabecera, el pie y el color por enfermedad a los dos informes PBIR (ES y EN).

Idempotente: borra y recrea los visuales que genera (nombres derivados de un hash) y reposiciona los existentes.
Uso: python scripts/build_report_layout.py
"""
import hashlib, json, pathlib

ROOT = pathlib.Path(__file__).parent.parent / "data_model"
REPORTS = {"es": "STI_Surveillance_Model.Report", "en": "STI_Surveillance_Model_EN.Report"}
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"

BG, CARD, LINE = "#0F1720", "#18232F", "#2A3A4A"
INK, MUTED, ACCENT = "#E6EDF3", "#A9B7C6", "#56B4E9"
DISEASES = [("CHL", "#56B4E9"), ("GON", "#E69F00"), ("SYP_PS", "#009E73"),
            ("SYP_EARLY", "#F0E442"), ("SYP_CONG", "#EF7B3A"), ("HIV", "#CC79A7")]

TEXT = {
    "es": {
        "nav": ["Resumen", "Mapa", "Ranking", "Corredor", "Oregon", "Demografía", "Calidad"],
        "brand": "Vigilancia de ITS", "tag": "EE.UU. · datos públicos",
        "legend": "Color fijo por enfermedad", "sources": "Fuentes de datos",
        "disclaimer": "Proyecto independiente, sin afiliación con CDC, Oregon Health Authority ni U.S. Census Bureau.",
        "alt_logo": "Logotipo del proyecto Vigilancia de ITS.", "alt_brand": "Nombre del proyecto.",
        "alt_nav": "Botón de navegación a la página {}.", "alt_legend": "Leyenda de colores fijos por enfermedad.",
        "alt_src": "Fuente de datos: {}.", "alt_srcs": "Etiqueta de las fuentes de datos.",
        "alt_disc": "Aviso de que el proyecto no tiene afiliación con las fuentes.",
    },
    "en": {
        "nav": ["Overview", "Map", "Ranking", "Corridor", "Oregon", "Demographics", "Quality"],
        "brand": "STI Surveillance", "tag": "US · public data",
        "legend": "Fixed color per disease", "sources": "Data sources",
        "disclaimer": "Independent project, not affiliated with the CDC, Oregon Health Authority or the U.S. Census Bureau.",
        "alt_logo": "STI Surveillance project logo.", "alt_brand": "Project name.",
        "alt_nav": "Navigation button to the {} page.", "alt_legend": "Legend of fixed colors per disease.",
        "alt_src": "Data source: {}.", "alt_srcs": "Label for the data sources.",
        "alt_disc": "Notice that the project is not affiliated with the sources.",
    },
}
SOURCES = [("CDC · NNDSS", 168), ("Oregon Health Authority", 240), ("U.S. Census Bureau", 200)]

CARD_W, CARD_H = 296, 128
# banda de filtros
DISEASE_BOX = (32, 80, 640, 64)
YEAR_BOX = (688, 80, 224, 64)
EXTRA_BOX = (928, 80, 224, 64)
LEGEND_BOX = (1184, 80, 704, 64)


def card_x(i):
    return 32 + i * (CARD_W + 16)


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def color(c):
    return {"solid": {"color": lit(f"'{c}'")}}


def stable_name(pid, role):
    return hashlib.sha1(f"{pid}:{role}".encode()).hexdigest()[:20]


# Disposición por página: rol -> (x, y, w, h). Roles de tarjeta = nombre de la medida.
LAYOUT = {
    0: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX,
        "card:Cases NNDSS": (card_x(0), 152, CARD_W, CARD_H), "card:Rate per 100k NNDSS": (card_x(1), 152, CARD_W, CARD_H),
        "card:YoY % (MMWR aligned)": (card_x(2), 152, CARD_W, CARD_H), "card:States in Outbreak": (card_x(3), 152, CARD_W, CARD_H),
        "card:Reference Week": (card_x(4), 152, CARD_W, CARD_H), "card:Latest Week With Data": (card_x(5), 152, CARD_W, CARD_H),
        "lineChart": (32, 296, 1856, 712)},
    1: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX,
        "filledMap": (32, 152, 1120, 856), "tableEx": (1168, 152, 720, 856)},
    2: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX, "slicer:week": EXTRA_BOX,
        "card:Reference Week": (32, 152, CARD_W, CARD_H),
        "barChart:0": (32, 296, 920, 712), "barChart:1": (968, 296, 920, 712)},
    3: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX, "slicer:state": EXTRA_BOX,
        "lineChart": (32, 152, 1856, 752), "textbox": (32, 920, 1856, 88)},
    4: {"slicer:disease": DISEASE_BOX, "slicer:year_or": YEAR_BOX,
        "card:% Suppressed Cells": (32, 152, CARD_W, CARD_H), "card:Share of Statewide Captured": (344, 152, CARD_W, CARD_H),
        "barChart:0": (32, 296, 920, 712), "tableEx": (968, 296, 920, 536), "textbox": (968, 848, 920, 160)},
    5: {"slicer:disease": DISEASE_BOX,
        "barChart:0": (32, 152, 608, 704), "barChart:1": (656, 152, 608, 704), "barChart:2": (1280, 152, 608, 704),
        "textbox": (32, 872, 1856, 136)},
    6: {"card:Revisions Status": (32, 152, CARD_W, CARD_H), "card:Latest Ingest (UTC)": (344, 152, CARD_W, CARD_H),
        "tableEx": (32, 296, 1856, 712)},
}
# páginas con leyenda de colores (todas menos Calidad)
WITH_LEGEND = range(0, 6)
SLICER_FIELDS = {"dim_disease.disease_key": "slicer:disease", "dim_mmwr_week.mmwr_year": "slicer:year",
                 "dim_epi_month.mmwr_year": "slicer:year_or", "dim_mmwr_week.mmwr_week": "slicer:week",
                 "dim_geography.state_name": "slicer:state"}
SYNC = {"slicer:disease": "sync_disease", "slicer:year": "sync_year", "slicer:year_or": "sync_year_or"}


def textbox(name, box, paragraphs, alt, bg=None, border=False):
    x, y, w, h = box
    paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "color": c,
                                                       **({"fontWeight": "bold"} if b else {})}}
                           for t, s, c, b in runs], "horizontalTextAlignment": align}
             for runs, align in paragraphs]
    container = {"general": [{"properties": {"altText": lit(f"'{alt}'")}}],
                 "background": [{"properties": {"show": lit("true" if bg else "false"),
                                                **({"color": color(bg)} if bg else {})}}]}
    if border:
        container["border"] = [{"properties": {"show": lit("true"), "color": color(LINE), "radius": lit("8D")}}]
    return {"$schema": SCHEMA, "name": name, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
            "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                       "drillFilterOtherVisuals": True, "visualContainerObjects": container}}


def nav_button(name, box, label, target, active, alt):
    x, y, w, h = box
    sel = {"id": "default"}
    fill, ink = (ACCENT, BG) if active else (CARD, INK)
    return {"$schema": SCHEMA, "name": name, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
            "visual": {"visualType": "actionButton",
                       "objects": {
                           "icon": [{"properties": {"shapeType": lit("'blank'")}, "selector": sel}],
                           "text": [{"properties": {"show": lit("true"), "text": lit(f"'{label}'"), "fontSize": lit("12D"),
                                                    "bold": lit("true" if active else "false"), "fontColor": color(ink),
                                                    "horizontalAlignment": lit("'Center'")}, "selector": sel}],
                           "fill": [{"properties": {"show": lit("true"), "fillColor": color(fill), "transparency": lit("0D")},
                                     "selector": sel}],
                           "outline": [{"properties": {"show": lit("true"), "lineColor": color(ACCENT if active else LINE)},
                                        "selector": sel}],
                           "shape": [{"properties": {"roundEdge": lit("8D")}, "selector": sel}]},
                       "drillFilterOtherVisuals": True,
                       "visualContainerObjects": {
                           "general": [{"properties": {"altText": lit(f"'{alt}'")}}],
                           "visualLink": [{"properties": {"show": lit("true"), "type": lit("'PageNavigation'"),
                                                          "navigationSection": lit(f"'{target}'")}}]}}}


def generated(pid, idx, lang):
    t = TEXT[lang]
    out = {}
    out["logo"] = textbox(stable_name(pid, "logo"), (32, 16, 56, 40),
                          [([("STI", 16, BG, True)], "center")], t["alt_logo"], bg=ACCENT)
    out["brand"] = textbox(stable_name(pid, "brand"), (96, 8, 224, 56),
                           [([(t["brand"], 16, INK, True)], "left"), ([(t["tag"], 11, MUTED, False)], "left")], t["alt_brand"])
    for i, label in enumerate(t["nav"]):
        out[f"nav{i}"] = nav_button(stable_name(pid, f"nav{i}"), (336 + i * 184, 16, 176, 40), label,
                                    PAGE_IDS[i], i == idx, t["alt_nav"].format(label))
    if idx in WITH_LEGEND:
        runs = []
        for code, c in DISEASES:
            runs += [("■ ", 14, c, False), (f"{code}    ", 12, INK, False)]
        out["legend"] = textbox(stable_name(pid, "legend"), LEGEND_BOX,
                                [([(t["legend"], 11, MUTED, False)], "left"), (runs, "left")], t["alt_legend"])
    out["src_label"] = textbox(stable_name(pid, "src_label"), (32, 1032, 160, 32),
                               [([(t["sources"], 11, MUTED, False)], "left")], t["alt_srcs"])
    x = 200
    for i, (label, w) in enumerate(SOURCES):
        out[f"src{i}"] = textbox(stable_name(pid, f"src{i}"), (x, 1032, w, 32), [([(label, 11, INK, False)], "center")],
                                 t["alt_src"].format(label), bg=CARD, border=True)
        x += w + 8
    out["disclaimer"] = textbox(stable_name(pid, "disclaimer"), (x + 16, 1032, 1888 - x - 16, 32),
                                [([(t["disclaimer"], 11, MUTED, False)], "right")], t["alt_disc"])
    return out


def container_style(v, surface=True):
    c = v["visual"].setdefault("visualContainerObjects", {})
    if surface:
        c["background"] = [{"properties": {"show": lit("true"), "color": color(CARD), "transparency": lit("0D")}}]
        c["border"] = [{"properties": {"show": lit("true"), "color": color(LINE), "radius": lit("8D")}}]


def disease_color_fill():
    return {"properties": {"fill": {"solid": {"color": {"expr": {"Measure": {
        "Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "Disease Color"}}}}}}}


def set_mode(v, mode):
    objs = v["visual"].setdefault("objects", {})
    data = objs.setdefault("data", [{"properties": {}}])
    data[0]["properties"]["mode"] = lit(f"'{mode}'")


def role_of(v, counters):
    vt = v["visual"]["visualType"]
    if vt == "slicer":
        return SLICER_FIELDS[v["visual"]["query"]["queryState"]["Values"]["projections"][0]["queryRef"]]
    if vt == "cardVisual":
        return "card:" + v["visual"]["query"]["queryState"]["Data"]["projections"][0]["field"]["Measure"]["Property"]
    if vt == "barChart":
        i = counters.get("bar", 0)
        counters["bar"] = i + 1
        return f"barChart:{i}"
    return vt


def build(lang):
    global PAGE_IDS
    pages_dir = ROOT / REPORTS[lang] / "definition" / "pages"
    PAGE_IDS = json.loads((pages_dir / "pages.json").read_text())["pageOrder"]
    for idx, pid in enumerate(PAGE_IDS):
        vdir = pages_dir / pid / "visuals"
        gen = generated(pid, idx, lang)
        for f in vdir.glob("*/visual.json"):          # idempotente: quitar lo generado antes
            if json.loads(f.read_text())["name"] in {g["name"] for g in gen.values()}:
                f.unlink()
                f.parent.rmdir()
        existing = []
        for f in sorted(vdir.glob("*/visual.json"), key=lambda p: (json.loads(p.read_text())["position"]["x"], p.name)):
            existing.append((f, json.loads(f.read_text())))
        existing.sort(key=lambda fv: (fv[1]["position"]["x"], fv[1]["position"]["y"]))
        counters = {}
        used = set()
        for f, v in existing:
            role = role_of(v, counters)
            box = LAYOUT[idx].get(role)
            assert box, (lang, idx, role)
            used.add(role)
            p = v["position"]
            p["x"], p["y"], p["width"], p["height"] = box
            vt = v["visual"]["visualType"]
            if vt == "slicer":
                v["visual"]["syncGroup"] = ({"groupName": SYNC[role], "fieldChanges": True, "filterChanges": True}
                                            if role in SYNC else v["visual"].get("syncGroup"))
                if v["visual"]["syncGroup"] is None:
                    del v["visual"]["syncGroup"]
                set_mode(v, "Basic" if role == "slicer:disease" else "Dropdown")
                if role == "slicer:disease":
                    v["visual"]["objects"].setdefault("general", [{"properties": {}}])[0]["properties"]["orientation"] = lit("1D")
                container_style(v, surface=False)
            elif vt != "textbox":
                container_style(v)
            if vt == "barChart":
                v["visual"]["objects"]["dataPoint"] = [disease_color_fill()]
            f.write_text(json.dumps(v, indent=2, ensure_ascii=False))
        missing = set(LAYOUT[idx]) - used
        assert not missing, (lang, idx, missing)
        # nuevos visuales
        for role, g in gen.items():
            d = vdir / g["name"]
            d.mkdir(exist_ok=True)
            (d / "visual.json").write_text(json.dumps(g, indent=2, ensure_ascii=False))
        # z y tabOrder: cabecera, filtros, contenido (por lectura), pie
        allv = []
        for f in vdir.glob("*/visual.json"):
            allv.append((f, json.loads(f.read_text())))

        def key(fv):
            v = fv[1]
            y, x = v["position"]["y"], v["position"]["x"]
            band = 0 if y < 80 else 1 if y < 152 else 3 if y >= 1024 else 2
            return (band, y, x)
        for i, (f, v) in enumerate(sorted(allv, key=key)):
            v["position"]["z"] = i + 1
            v["position"]["tabOrder"] = i
            f.write_text(json.dumps(v, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    for lang in REPORTS:
        build(lang)
    print("ok")
