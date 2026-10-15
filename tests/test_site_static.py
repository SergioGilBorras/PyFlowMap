"""The Pages draft is fully local and uses real SVG generator outputs."""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class _Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "img":
            self.images.append(data)
        if tag == "link" and "href" in data:
            self.links.append(data["href"])
        if tag == "script":
            self.scripts.append(data)


def test_pages_site_contains_three_real_self_contained_svgs():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    resources = _Resources()
    resources.feed(html)
    assert 'lang="es"' in html
    assert "<main " in html and "</main>" in html
    assert not resources.scripts
    assert resources.links == ["assets/site.css"]
    assert {img["src"] for img in resources.images} == {
        "assets/activity.svg", "assets/classes.svg", "assets/packages.svg",
    }
    for img in resources.images:
        assert img.get("alt")
        content = (SITE / img["src"]).read_text(encoding="utf-8")
        assert "<svg " in content and "</svg>" in content
        assert "<image " not in content and "xlink:href=" not in content
    assert (SITE / "assets/site.css").is_file()


def test_pages_not_published_and_semantic_limitations_explained():
    readme = (SITE / "README.md").read_text(encoding="utf-8")
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "Sin desplegar" in readme
    assert "UML 2.5.1" in html
    assert "strict" in html and "modern" in html
    assert "--diagram-type package" in html
    assert "Sin inferencia semántica por defecto" in html
