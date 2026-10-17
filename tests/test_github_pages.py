"""Offline Pages contract: genuine static examples and valid local references."""

from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

SITE = Path(__file__).resolve().parents[1] / "site"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.internal = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("src", "href"):
            ref = values.get(key)
            if ref and not ref.startswith(("http://", "https://", "#", "mailto:")):
                self.internal.append(ref)


def test_site_links_assets_and_editorial_copy():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    parser = Links()
    parser.feed(html)
    assert all((SITE / ref).exists() for ref in parser.internal), parser.internal
    assert "feat/initial-static-flow-mvp" not in html
    assert "/tree/main/docs" not in html
    assert "sin inventar relaciones" in html
    assert "trazabilidad al código fuente" in html
    assert "Sin inferencia semántica por defecto" in html
    assert "no se publican en PyPI" in html
    assert "carpeta" in html.lower()


def test_three_real_svg_and_folder_is_one_piece():
    for name in ("activity", "classes", "packages"):
        data = (SITE / "assets" / (name + ".svg")).read_text(encoding="utf-8")
        root = ET.fromstring(data)
        assert root.tag.endswith("svg")
        assert "<image" not in data and "xlink:href=" not in data
    svg = (SITE / "assets/packages.svg").read_text(encoding="utf-8")
    assert ">Inventory</text>" in svg
    assert ">Orders</text>" in svg
    assert ">Reports</text>" in svg
    assert "<polygon" in svg
