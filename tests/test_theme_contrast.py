import json, pathlib

def lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

import pytest

T = pathlib.Path(__file__).parent.parent / "theme"
# nombre -> (fondo de página, tarjeta, extremos del mapa secuencial)
THEMES = {"dark_accessible": ("#0F1720", "#18232F", ("#4F7CA3", "#F0E442")),
          "light_accessible": ("#F5F7FA", "#FFFFFF", ("#4F7CA3", "#7D6E00"))}


@pytest.fixture(params=THEMES)
def th(request):
    bg, card, ends = THEMES[request.param]
    return json.loads((T / f"{request.param}.json").read_text()), (bg, card), ends


def test_text_meets_wcag_aa(th):
    theme, bgs, _ = th
    for key in ("foreground", "hyperlink", "visitedHyperlink"):
        for bg in bgs:
            assert ratio(theme[key], bg) >= 4.5, (key, bg)


def test_data_colors_meet_non_text_contrast(th):
    theme, bgs, _ = th
    assert len(theme["dataColors"]) >= 8
    for c in theme["dataColors"]:
        for bg in bgs:
            assert ratio(c, bg) >= 3.0, (c, bg)


def test_sequential_map_endpoints_visible(th):
    _, bgs, ends = th
    for c in ends:
        assert ratio(c, bgs[0]) >= 3.0, c
