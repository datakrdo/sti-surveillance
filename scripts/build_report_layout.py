"""Aplica la grilla, la navegación, la cabecera y el pie a los dos informes PBIR (ES y EN).

Idempotente: borra y recrea los visuales que genera (nombres derivados de un hash) y reposiciona los existentes.
Uso: python scripts/build_report_layout.py
"""
import hashlib, json, pathlib

ROOT = pathlib.Path(__file__).parent.parent / "data_model"
REPORTS = {"es": "STI_Surveillance_Model_ES.Report", "en": "STI_Surveillance_Model.Report"}
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"

BG, CARD, LINE = "#0F1720", "#18232F", "#2A3A4A"
INK, MUTED, ACCENT = "#E6EDF3", "#A9B7C6", "#56B4E9"

TEXT = {
    "es": {
        "nav": ["Resumen", "Mapa", "Ranking", "Corredor", "Oregon", "Demografía", "Calidad"],
        "brand": "Vigilancia de ITS", "logo": "ITS", "tag": "EE.UU. · datos públicos",
        "sources": "Fuentes de datos",
        "disclaimer": "Proyecto independiente, sin afiliación con CDC, Oregon Health Authority ni U.S. Census Bureau.",
        "alt_logo": "Logotipo del proyecto Vigilancia de ITS.", "alt_brand": "Nombre del proyecto.",
        "alt_nav": "Botón de navegación a la página {}.",
        "alt_src": "Fuente de datos: {} (abre su sitio web).", "alt_srcs": "Etiqueta de las fuentes de datos.",
        "alt_disc": "Aviso de que el proyecto no tiene afiliación con las fuentes.",
    },
    "en": {
        "nav": ["Overview", "Map", "Ranking", "Corridor", "Oregon", "Demographics", "Quality"],
        "brand": "STI Surveillance", "logo": "STI", "tag": "US · public data",
        "sources": "Data sources",
        "disclaimer": "Independent project, not affiliated with the CDC, Oregon Health Authority or the U.S. Census Bureau.",
        "alt_logo": "STI Surveillance project logo.", "alt_brand": "Project name.",
        "alt_nav": "Navigation button to the {} page.",
        "alt_src": "Data source: {} (opens its website).", "alt_srcs": "Label for the data sources.",
        "alt_disc": "Notice that the project is not affiliated with the sources.",
    },
}
KPI_TITLES = {
    "Cases NNDSS": ("Casos notificados", "Reported cases"),
    "Rate per 100k NNDSS": ("Tasa por 100.000", "Rate per 100,000"),
    "YoY % (MMWR aligned)": ("Variación interanual", "Year-over-year"),
    "States in Outbreak": ("Estados en brote", "States in outbreak"),
    "Reference Week": ("Semana de referencia", "Reference week"),
    "Latest Week With Data": ("Última semana", "Latest week"),
    "% Suppressed Cells": ("Celdas suprimidas", "Suppressed cells"),
    "Share of Statewide Captured": ("Captura por condado", "County capture"),
    "Revisions Status": ("Estado de revisiones", "Revisions status"),
    "Latest Ingest (UTC)": ("Última ingesta (UTC)", "Latest ingest (UTC)"),
}
DISEASE_COLORS = {"CHL": "#56B4E9", "GON": "#E69F00", "SYP_PS": "#009E73", "SYP_EARLY": "#F0E442",
                  "SYP_CONG": "#EF7B3A", "HIV": "#CC79A7"}
DEMO_NOTE = (
    "Bloqueado para el rol restringido: los cortes por edad y raza no están disponibles para Restricted_Epidemiologist ni "
    "Restricted_State_Analyst (seguridad a nivel de objeto). Oregon suprime celdas con menos de 6 casos. "
    "El gráfico de sexo muestra solo Female y Male: Nonbinary y Unknown casi siempre quedan suprimidos.",
    "Blocked for the restricted role: age and race breakdowns are not available to Restricted_Epidemiologist or "
    "Restricted_State_Analyst (object-level security). Oregon suppresses cells with fewer than 6 cases. "
    "The sex chart shows only Female and Male: Nonbinary and Unknown are almost always suppressed.")
# enfermedades con datos: NNDSS no trae HIV ni SYP_EARLY; Oregon no trae SYP_PS
DISEASES_BY_PAGE = {i: ["CHL", "GON", "SYP_PS", "SYP_CONG"] for i in range(4)}
DISEASES_BY_PAGE.update({4: ["CHL", "GON", "SYP_CONG", "SYP_EARLY", "HIV"], 5: ["CHL", "GON", "SYP_CONG", "SYP_EARLY", "HIV"]})
WEEK_TITLE = ("Semana MMWR (exceso)", "MMWR week (excess)")
DEMO_ALT = {
    "demo:sex": ("Barra 100 % apilada: reparto de casos por sexo en Oregon.", "100% stacked bar: share of cases by sex in Oregon."),
    "demo:age": ("Columnas: casos por grupo de edad en Oregon.", "Columns: cases by age group in Oregon."),
}
SOURCES = [("CDC · NNDSS", 168, "https://data.cdc.gov"), ("Oregon Health Authority", 240, "https://www.oregon.gov/oha"),
           ("U.S. Census Bureau", 200, "https://www.census.gov/programs-surveys/popest.html")]

CARD_W, CARD_H = 296, 128
# banda de filtros
DISEASE_BOX = (32, 80, 896, 96)
YEAR_BOX = (944, 80, 224, 96)
EXTRA_BOX = (1184, 80, 320, 96)


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
        "card:Cases NNDSS": (card_x(0), 192, CARD_W, CARD_H), "card:Rate per 100k NNDSS": (card_x(1), 192, CARD_W, CARD_H),
        "card:YoY % (MMWR aligned)": (card_x(2), 192, CARD_W, CARD_H), "card:States in Outbreak": (card_x(3), 192, CARD_W, CARD_H),
        "card:Reference Week": (card_x(4), 192, CARD_W, CARD_H), "card:Latest Week With Data": (card_x(5), 192, CARD_W, CARD_H),
        "lineChart": (32, 336, 1856, 672)},
    1: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX,
        "filledMap": (32, 192, 1120, 816), "tableEx": (1168, 192, 720, 816)},
    2: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX, "slicer:week": EXTRA_BOX,
        "card:Reference Week": (32, 192, CARD_W, CARD_H),
        "barChart:0": (32, 336, 920, 672), "barChart:1": (968, 336, 920, 672)},
    3: {"slicer:disease": DISEASE_BOX, "slicer:year": YEAR_BOX, "slicer:state": EXTRA_BOX,
        "lineChart": (32, 192, 1856, 712), "textbox": (32, 920, 1856, 88)},
    4: {"slicer:disease": DISEASE_BOX, "slicer:year_or": YEAR_BOX,
        "card:% Suppressed Cells": (32, 192, CARD_W, CARD_H), "card:Share of Statewide Captured": (344, 192, CARD_W, CARD_H),
        "barChart:0": (32, 336, 920, 672), "tableEx": (968, 336, 920, 496), "textbox": (968, 848, 920, 160)},
    5: {"slicer:disease": DISEASE_BOX,
        "demo:sex": (32, 192, 1856, 232), "demo:age": (32, 440, 920, 432), "demo:race": (968, 440, 920, 432),
        "textbox": (32, 888, 1856, 120)},
    6: {"card:Revisions Status": (32, 192, CARD_W, CARD_H), "card:Latest Ingest (UTC)": (344, 192, CARD_W, CARD_H),
        "tableEx": (32, 336, 1856, 672)},
}
SLICER_FIELDS = {"dim_disease.disease_key": "slicer:disease", "dim_mmwr_week.mmwr_year": "slicer:year",
                 "dim_epi_month.mmwr_year": "slicer:year_or", "dim_mmwr_week.mmwr_week": "slicer:week",
                 "dim_geography.state_name": "slicer:state"}
SYNC = {"slicer:disease": "sync_disease", "slicer:year": "sync_year", "slicer:year_or": "sync_year_or"}


def textbox(name, box, paragraphs, alt, bg=None, border=False):
    x, y, w, h = box
    paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "color": c,
                                                       **({"fontWeight": "bold"} if b else {}),
                                                       **({"textDecoration": "underline"} if u else {})},
                            **({"url": u} if u else {})}
                           for t, s, c, b, u in (r if len(r) == 5 else (*r, None) for r in runs)],
              "horizontalTextAlignment": align}
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
                           "text": [{"properties": {"show": lit("true")}},
                                    {"properties": {"text": lit(f"'{label}'"), "fontSize": lit("12D"),
                                                    "bold": lit("true" if active else "false"), "fontColor": color(ink),
                                                    "horizontalAlignment": lit("'Center'")}, "selector": sel}],
                           "fill": [{"properties": {"show": lit("true")}},
                                    {"properties": {"fillColor": color(fill), "transparency": lit("0D")}, "selector": sel}],
                           "outline": [{"properties": {"show": lit("true")}},
                                       {"properties": {"lineColor": color(ACCENT if active else LINE)}, "selector": sel}],
                           "shape": [{"properties": {"roundEdge": lit("8D")}, "selector": sel}]},
                       "drillFilterOtherVisuals": True,
                       "visualContainerObjects": {
                           "general": [{"properties": {"altText": lit(f"'{alt}'")}}],
                           "visualLink": [{"properties": {"show": lit("true"), "type": lit("'PageNavigation'"),
                                                          "navigationSection": lit(f"'{target}'")}}]}}}


def link_button(name, box, label, url, alt):
    """Caja de fuente: misma apariencia que antes, con un enlace web oculto (Ctrl+clic)."""
    b = nav_button(name, box, label, "", False, alt)
    b["visual"]["objects"]["text"][1]["properties"]["fontSize"] = lit("11D")
    b["visual"]["visualContainerObjects"]["visualLink"] = [{"properties": {
        "show": lit("true"), "type": lit("'WebUrl'"), "webUrl": lit(f"'{url}'")}}]
    return b


def generated(pid, idx, lang):
    t = TEXT[lang]
    out = {}
    out["logo"] = textbox(stable_name(pid, "logo"), (32, 16, 56, 40),
                          [([(t["logo"], 16, BG, True)], "center")], t["alt_logo"], bg=ACCENT)
    out["brand"] = textbox(stable_name(pid, "brand"), (96, 8, 224, 56),
                           [([(t["brand"], 16, INK, True)], "left"), ([(t["tag"], 11, MUTED, False)], "left")], t["alt_brand"])
    for i, label in enumerate(t["nav"]):
        out[f"nav{i}"] = nav_button(stable_name(pid, f"nav{i}"), (336 + i * 184, 16, 176, 40), label,
                                    PAGE_IDS[i], i == idx, t["alt_nav"].format(label))
    out["src_label"] = textbox(stable_name(pid, "src_label"), (32, 1032, 160, 32),
                               [([(t["sources"], 11, MUTED, False)], "left")], t["alt_srcs"])
    x = 200
    for i, (label, w, url) in enumerate(SOURCES):
        out[f"src{i}"] = link_button(stable_name(pid, f"src{i}"), (x, 1032, w, 32), label, url, t["alt_src"].format(label))
        x += w + 8
    out["disclaimer"] = textbox(stable_name(pid, "disclaimer"), (x + 16, 1032, 1888 - x - 16, 32),
                                [([(t["disclaimer"], 11, MUTED, False)], "right")], t["alt_disc"])
    return out


def container_style(v, surface=True):
    c = v["visual"].setdefault("visualContainerObjects", {})
    if surface:
        c["background"] = [{"properties": {"show": lit("true"), "color": color(CARD), "transparency": lit("0D")}}]
        b = c.setdefault("border", [{"properties": {}}])[0]["properties"]
        b.update({"show": lit("true"), "color": color(LINE), "radius": lit("8D")})


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
    if vt in ("barChart", "columnChart", "hundredPercentStackedBarChart"):
        refs = [pr["queryRef"] for r in v["visual"]["query"]["queryState"].values() for pr in r["projections"]]
        for key, role in (("dim_demographic.sex", "demo:sex"), ("dim_demographic.age_group", "demo:age"),
                          ("dim_demographic.race_group", "demo:race")):
            if key in refs:
                return role
    if vt == "barChart":
        i = counters.get("bar", 0)
        counters["bar"] = i + 1
        return f"barChart:{i}"
    return vt


def convert_demo(v, role):
    vis = v["visual"]
    qs = vis["query"]["queryState"]
    cat = next(pr for r in qs.values() for pr in r["projections"] if pr["queryRef"].startswith("dim_demographic."))
    y = qs["Y"]
    objs = vis.setdefault("objects", {})
    if role == "demo:sex":
        vis["visualType"] = "hundredPercentStackedBarChart"
        vis["query"]["queryState"] = {"Series": {"projections": [cat]}, "Y": y}
        vis["query"].pop("sortDefinition", None)
        for flt in v.get("filterConfig", {}).get("filters", []):
            if flt["field"].get("Column", {}).get("Property") == "sex":
                flt["type"] = "Categorical"
                flt["filter"] = {"Version": 2, "From": [{"Name": "d", "Entity": "dim_demographic", "Type": 0}], "Where": [{"Condition": {"In": {
                    "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "sex"}}],
                    "Values": [[{"Literal": {"Value": "'Female'"}}], [{"Literal": {"Value": "'Male'"}}]]}}}]}
        objs["legend"] = [{"properties": {"show": lit("true"), "position": lit("'Top'")}}]
        objs["categoryAxis"] = [{"properties": {"show": lit("false"), "innerPadding": lit("0D")}}]
        objs["labels"] = [{"properties": {"show": lit("true"), "fontSize": lit("14D"), "labelPrecision": lit("1D")}}]
    elif role == "demo:age":
        vis["visualType"] = "columnChart"
        vis["query"]["queryState"] = {"Category": {"projections": [cat]}, "Y": y}
        vis["query"]["sortDefinition"] = {"sort": [{"field": {"Column": {
            "Expression": {"SourceRef": {"Entity": "dim_demographic"}}, "Property": "age_group"}}, "direction": "Ascending"}]}


def save(f, v, force=False):
    """Escribe solo si cambia algo real: Desktop reescribe z/tabOrder y el orden de claves."""
    if f.exists() and not force:
        old = json.loads(f.read_text(encoding="utf-8-sig"))

        def strip(d):
            return {**d, "position": {k: x for k, x in d["position"].items() if k not in ("z", "tabOrder")}}
        if strip(old) == strip(v):
            return
    f.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")


def build(lang):
    global PAGE_IDS
    pages_dir = ROOT / REPORTS[lang] / "definition" / "pages"
    PAGE_IDS = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8-sig"))["pageOrder"]
    for idx, pid in enumerate(PAGE_IDS):
        vdir = pages_dir / pid / "visuals"
        gen = generated(pid, idx, lang)
        old_legend = stable_name(pid, "legend")           # leyenda de colores retirada
        if (vdir / old_legend).exists():
            for f in (vdir / old_legend).iterdir():
                f.unlink()
            (vdir / old_legend).rmdir()
        prev = {}
        for f in vdir.glob("*/visual.json"):          # idempotente: quitar lo generado antes
            j = json.loads(f.read_text(encoding="utf-8-sig"))
            if j["name"] in {g["name"] for g in gen.values()}:
                prev[f] = j
                f.unlink()
                f.parent.rmdir()
        existing = []
        for f in sorted(vdir.glob("*/visual.json"), key=lambda p: (json.loads(p.read_text(encoding="utf-8-sig"))["position"]["x"], p.name)):
            existing.append((f, json.loads(f.read_text(encoding="utf-8-sig"))))
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
                    v["filterConfig"] = {"filters": [{
                        "name": stable_name(pid, "disease_filter"),
                        "field": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_disease"}}, "Property": "disease_key"}},
                        "type": "Categorical",
                        "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_disease", "Type": 0}], "Where": [{"Condition": {"In": {
                            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "disease_key"}}],
                            "Values": [[{"Literal": {"Value": f"'{d}'"}}] for d in DISEASES_BY_PAGE[idx]]}}}]},
                        "howCreated": "User"}]}
                    items = v["visual"]["objects"].setdefault("items", [])
                    items[:] = [x for x in items if x.get("selector") != {"id": "selected"}]
                    items.append({"properties": {
                        "background": {"solid": {"color": {"expr": {"Measure": {
                            "Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "Disease Color"}}}}},
                        "fontColor": color(BG)}, "selector": {"id": "selected"}})
                    v["visual"]["objects"].setdefault("selection", [{"properties": {}}])[0]["properties"][
                        "selectAllCheckboxEnabled"] = lit("false")
                    v["visual"]["objects"].setdefault("general", [{"properties": {}}])[0]["properties"]["orientation"] = lit("1D")
                container_style(v, surface=False)
            elif vt != "textbox":
                container_style(v)
            if vt in ("barChart", "columnChart", "hundredPercentStackedBarChart") or role in DEMO_ALT:
                ax = v["visual"].setdefault("objects", {}).setdefault("valueAxis", [{"properties": {}}])
                ax[0]["properties"]["gridlineShow"] = lit("false")
            if vt == "lineChart":
                ax = v["visual"].setdefault("objects", {}).setdefault("valueAxis", [{"properties": {}}])
                ax[0]["properties"]["gridlineStyle"] = lit("'dashed'")
            if role == "slicer:week":
                v["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"] = lit(
                    "'" + WEEK_TITLE[0 if lang == "es" else 1] + "'")
            if vt == "textbox" and idx == 5 and role == "textbox":
                run = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]
                run["value"] = DEMO_NOTE[0 if lang == "es" else 1]
            if role in DEMO_ALT:
                convert_demo(v, role)
                v["visual"]["visualContainerObjects"]["general"][0]["properties"]["altText"] = lit(
                    "'" + DEMO_ALT[role][0 if lang == "es" else 1] + "'")
            if vt == "cardVisual":
                m = v["visual"]["query"]["queryState"]["Data"]["projections"][0]["field"]["Measure"]["Property"]
                c = v["visual"].setdefault("visualContainerObjects", {})
                c.setdefault("title", [{"properties": {}}])[0]["properties"].update(
                    {"show": lit("true"), "text": lit("'" + KPI_TITLES[m][0 if lang == "es" else 1] + "'")})
                c.setdefault("subTitle", [{"properties": {}}])[0]["properties"]["show"] = lit("false")
                vals = v["visual"].setdefault("objects", {}).setdefault("value", [])
                vals[:] = [x for x in vals if x.get("selector") != {"id": "default"}]
                vals.append({"properties": {"horizontalAlignment": lit("'center'")}, "selector": {"id": "default"}})
            if vt == "barChart":
                v["visual"].get("objects", {}).pop("dataPoint", None)
            save(f, v)
        missing = set(LAYOUT[idx]) - used
        assert not missing, (lang, idx, missing)
        # nuevos visuales
        fresh = set()
        for role, g in gen.items():
            d = vdir / g["name"]
            d.mkdir(exist_ok=True)
            f = d / "visual.json"
            if f in prev:                              # conservar lo que Desktop guardó si no hay cambio real
                strip = lambda x: {**x, "position": {k: y for k, y in x["position"].items() if k not in ("z", "tabOrder")}}
                if strip(prev[f]) == strip(g):
                    g = prev[f]
            else:
                fresh.add(f)
            save(f, g, force=True)
        # z y tabOrder: cabecera, filtros, contenido (por lectura), pie
        allv = []
        for f in vdir.glob("*/visual.json"):
            allv.append((f, json.loads(f.read_text(encoding="utf-8-sig"))))

        def key(fv):
            v = fv[1]
            y, x = v["position"]["y"], v["position"]["x"]
            band = 0 if y < 80 else 1 if y < 192 else 3 if y >= 1024 else 2
            return (band, y, x)
        for i, (f, v) in enumerate(sorted(allv, key=key)):
            v["position"]["z"] = i + 1
            v["position"]["tabOrder"] = i
            save(f, v, force=f in fresh)


if __name__ == "__main__":
    for lang in REPORTS:
        build(lang)
    print("ok")
