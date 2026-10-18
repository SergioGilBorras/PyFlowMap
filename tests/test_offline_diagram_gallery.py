"""No external inference and no co-mingling of UML families."""

import json
from pathlib import Path

from scripts.offline_diagram_gallery import DEMO_ENTRY, DEMO_SOURCE, generate_gallery


def test_three_distinct_families_and_preserved_history(tmp_path, monkeypatch):
    import pyflowmap.semantic.p4_provider as provider

    def forbid_labeler(*args, **kwargs):
        raise AssertionError("Offline preview cannot invoke P4 or Codex")

    monkeypatch.setattr(provider, "P4SemanticLabelProvider", forbid_labeler)
    first = generate_gallery(str(DEMO_SOURCE), DEMO_ENTRY, str(tmp_path))
    root = Path(first["output"])
    assert first["semantic_provider"] == "disabled"
    assert first["types"] == ["activity", "class", "package"]
    assert {p.name for p in root.iterdir()} == {
        "index.html", "README.md", "activity", "classes", "packages", "common"}
    manifest = json.loads((root / "common/manifest.json").read_text(encoding="utf-8"))
    assert manifest["inference"] == "none"
    assert len(manifest["diagrams"]) == 3
    for item in manifest["diagrams"]:
        assert item["files"]["svg"].startswith(item["folder"] + "/")
        assert item["files"]["json"].startswith(item["folder"] + "/")
        for location in item["files"].values():
            assert (root / location).is_file()
        model = json.loads((root / item["files"]["json"]).read_text(encoding="utf-8"))
        if item["type"] == "activity":
            assert all(n["label_source"] == "deterministic" for n in model["nodes"])
            assert item["files"].get("mmd")
        elif item["type"] == "class":
            assert model["generalizations"]
            assert len(model["dependencies"]) == 2
            assert all(link["evidence"] for link in model["dependencies"])
            assert item["files"].get("mmd")
        else:
            assert model["dependencies"] and item["files"].get("dot")
            assert "mmd" not in item["files"]
            assert item["package_style"] == "modern"
            assert model["package_style"] == "modern"
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "common/gallery.css" in html and "<script" not in html
    before = (root / "common/manifest.json").read_bytes()
    second = generate_gallery(str(DEMO_SOURCE), DEMO_ENTRY, str(tmp_path))
    assert first["output"] != second["output"]
    assert (root / "common/manifest.json").read_bytes() == before
