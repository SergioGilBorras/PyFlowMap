"""Benchmark reference gallery uses real self-contained SVG generator outputs."""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "benchmark" / "gallery-reference"


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


def test_reference_gallery_contains_three_real_self_contained_svgs():
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
        if img["src"] == "assets/packages.svg":
            assert all(f">{name}</text>" in content for name in ("Reports", "Orders", "Inventory"))
        assert "<image " not in content and "xlink:href=" not in content
    assert (SITE / "assets/site.css").is_file()


def test_reference_gallery_is_not_consumer_pages_and_explains_limitations():
    readme = (SITE / "README.md").read_text(encoding="utf-8")
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "benchmark reference material" in readme
    assert "UML 2.5.1" in html
    assert "strict" in html and "modern" in html
    assert "--diagram-type package" in html
    assert "Sin inferencia semántica por defecto" in html
