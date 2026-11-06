"""Deriva los informes en tema claro (*_Light.Report y .pbip) a partir de los oscuros.

Los oscuros son la fuente de verdad: correr antes scripts/build_report_layout.py.
Idempotente: borra y regenera las carpetas *_Light.
Uso: python scripts/build_light_reports.py
"""
import json, pathlib, re, shutil, uuid

ROOT = pathlib.Path(__file__).parent.parent
DATA = ROOT / "data_model"
REPORTS = ["STI_Surveillance_Model", "STI_Surveillance_Model_ES"]
OLD_THEME = "STI_Dark_Accessible8698696877637903.json"
NEW_THEME = "STI_Light_Accessible8698696877637904.json"

# oscuro -> claro (BG pasa a blanco: en los visuales solo es texto sobre acento o sobre el color de la enfermedad)
HEX = {"#0F1720": "#FFFFFF", "#18232F": "#FFFFFF", "#2A3A4A": "#D0D7DE", "#E6EDF3": "#1F2328",
       "#A9B7C6": "#57606A", "#56B4E9": "#0969DA", "#E6E6E6": "#1F2328", "#F0E442": "#7D6E00"}


def convert(text):
    text = re.sub(r"#[0-9A-Fa-f]{6}", lambda m: HEX.get(m.group(0).upper(), m.group(0)), text)
    return text.replace('"Property": "Disease Color"', '"Property": "Disease Color Light"')


def build(name):
    src, dst = DATA / f"{name}.Report", DATA / f"{name}_Light.Report"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    for f in dst.rglob("*.json"):
        if "StaticResources" not in f.parts:
            f.write_text(convert(f.read_text(encoding="utf-8")), encoding="utf-8")
    res = dst / "StaticResources" / "RegisteredResources"
    (res / OLD_THEME).unlink()
    shutil.copy(ROOT / "theme" / "light_accessible.json", res / NEW_THEME)
    rj = dst / "definition" / "report.json"
    rj.write_text(rj.read_text(encoding="utf-8").replace(OLD_THEME, NEW_THEME), encoding="utf-8")
    pf = dst / ".platform"
    p = json.loads(pf.read_text(encoding="utf-8"))
    p["metadata"]["displayName"] = f"{name}_Light"
    p["config"]["logicalId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sti-surveillance/{name}_Light"))  # estable entre corridas
    pf.write_text(json.dumps(p, indent=2), encoding="utf-8")
    pbip = (DATA / f"{name}.pbip").read_text(encoding="utf-8").replace(f"{name}.Report", f"{name}_Light.Report")
    (DATA / f"{name}_Light.pbip").write_text(pbip, encoding="utf-8")


if __name__ == "__main__":
    for n in REPORTS:
        build(n)
    print("ok")
