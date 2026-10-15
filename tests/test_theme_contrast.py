import json, pathlib

def lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

THEME = json.loads((pathlib.Path(__file__).parent.parent / "theme" / "dark_accessible.json").read_text())
BG, CARD = "#0F1720", "#18232F"

def test_text_meets_wcag_aa():
    for key in ("foreground", "hyperlink", "visitedHyperlink"):
        for bg in (BG, CARD):
            assert ratio(THEME[key], bg) >= 4.5, (key, bg)

def test_data_colors_meet_non_text_contrast():
    assert len(THEME["dataColors"]) >= 8
    for c in THEME["dataColors"]:
        for bg in (BG, CARD):
            assert ratio(c, bg) >= 3.0, (c, bg)

def test_sequential_map_endpoints_visible():
    assert ratio("#4F7CA3", BG) >= 3.0 and ratio("#F0E442", BG) >= 3.0
