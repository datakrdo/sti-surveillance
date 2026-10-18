"""Cada imagen que referencian los README debe existir (nada de imágenes rotas en el portfolio)."""
import pathlib, re
import pytest

ROOT = pathlib.Path(__file__).parent.parent
READMES = ["README.md", "README_es.md"]


@pytest.mark.parametrize("name", READMES)
def test_images_exist(name):
    text = (ROOT / name).read_text()
    refs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text) + re.findall(r'<img[^>]+src="([^"]+)"', text)
    local = [r for r in refs if not r.startswith(("http://", "https://"))]
    missing = [r for r in local if not (ROOT / r).is_file()]
    assert not missing, f"imágenes inexistentes en {name}: {missing}"


def test_both_readmes_show_the_cover_gif():
    for name in READMES:
        assert "docs/img/cover" in (ROOT / name).read_text(), name


def test_phases_checklist_has_no_screenshot_item():
    for name in READMES:
        assert not re.search(r"(?i)- \[[ x]\] .*(screenshots|capturas)", (ROOT / name).read_text()), name
