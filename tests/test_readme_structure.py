"""El README sigue el orden de la convención de portfolio (contexto → resultados → cómo/por qué → Tools/Skills →
operativo → Out of scope → Limitations → License) y EN y ES son espejos."""
import pathlib, re
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ORDER = ["results", "demo", "how", "data", "design", "tools", "skills", "structure", "quick", "tests", "phases",
         "out", "limitations", "license"]
MATCH = [
    ("tools", r"^(tools|herramientas)\b"), ("skills", r"^(skills|habilidades)\b"),
    ("design", r"^(design decisions|decisiones de dise)"), ("how", r"^(how it works|c.mo funciona)"),
    ("data", r"^(data sources|fuentes de datos)"), ("results", r"^(results|resultados)\b"),
    ("demo", r"^(live demo|demo en vivo)"), ("limitations", r"^(limitations|limitaciones)\b"),
    ("structure", r"^(structure|estructura)\b"), ("quick", r"^(quick start|inicio r.pido)"),
    ("tests", r"^tests?\b"), ("phases", r"^(phases|fases)\b"), ("out", r"^(out of scope|fuera de alcance)"),
    ("license", r"^(license|licencia)\b"),
]
LANGLINE = "🇬🇧 [English](README.md) · 🇪🇸 [Español](README_es.md)"


def keys(name):
    fence, out = False, []
    for l in (ROOT / name).read_text().split("\n"):
        if l.startswith("```"): fence = not fence
        if fence or not l.startswith("## "): continue
        c = re.sub(r"[^\w\s']", "", l[3:], flags=re.U).strip().lower()
        k = next((k for k, rx in MATCH if re.search(rx, c)), None)
        assert k, f"sección sin clave canónica en {name}: {l}"
        out.append(k)
    return out


@pytest.mark.parametrize("name", ["README.md", "README_es.md"])
def test_canonical_order(name):
    ks = keys(name)
    assert ks == sorted(ks, key=ORDER.index), f"orden incorrecto en {name}: {ks}"
    assert ks[-1] == "license" and ks[-2] == "limitations"
    assert {"tools", "skills"} <= set(ks)
    assert ks.index("results") < ks.index("tools")      # primero resultados, después la pila
    assert (ROOT / name).read_text().split("\n")[0] == LANGLINE


def test_en_and_es_are_mirrors():
    assert keys("README.md") == keys("README_es.md")
