"""Independent per-family visual and structural validation, no Codex."""
import json
from pathlib import Path

import pytest

from scripts.validate_diagram_families import (
    BANK,
    build_index,
    load_cases,
    run_bank,
    validate_classes,
    validate_packages,
)


def test_manifest_covers_each_family():
    cases = load_cases()
    assert len(cases) == 21
    assert {family: sum(c["family"] == family for c in cases)
            for family in ("activity", "class", "package")} == {
                "activity": 7, "class": 7, "package": 7,
            }
    for case in cases:
        source = (BANK / case["source"]).resolve()
        assert source.is_relative_to((BANK / "fixtures").resolve())
        assert list(source.rglob("*.py"))

def test_complete_offline_visual_gallery(tmp_path, monkeypatch):
    import pyflowmap.semantic.p4_provider as provider

    def fail_provider(*args, **kwargs):
        raise AssertionError("No external labeling is permitted")

    monkeypatch.setattr(provider, "P4SemanticLabelProvider", fail_provider)
    result = run_bank(tmp_path)
    assert result["status"] == "PASS"
    assert (result["cases"], result["renders"]) == (21, 28)
    root = Path(result["output"])
    report = json.loads((root / "common/report.json").read_text(encoding="utf-8"))
    assert report["inference"] == "disabled"
    assert report["source_execution"] is False
    assert report["by_family"] == {"activity": 7, "class": 7, "package": 14}
    for row in report["rows"]:
        for local in row["outputs"].values():
            assert (root / local).is_file()
    html = (root / "index.html").read_text(encoding="utf-8")
    assert html.count('<article class="card">') == 28
    assert html.count('<img loading="lazy"') == 28
    assert all(f'id="{name}"' in html for name in ("activity", "class", "package"))
    assert "https://" not in html and "<script" not in html
    second = run_bank(tmp_path)
    assert second["output"] != result["output"]
    assert (root / "index.html").read_text(encoding="utf-8") == html

def test_html_empty_index():
    assert "<article" not in build_index([])

def test_oracle_rejects_invented_relationships():
    cls = next(c for c in load_cases() if c["family"] == "class"
               and c["id"] == "independent")
    fake = {
        "diagram_type": "class", "uml_version": "2.5.1",
        "classes": [{"id": "model:Left"}, {"id": "model:Right"}],
        "generalizations": [{"specific": "model:Left", "general": "model:Right",
                            "location": "model.py:1"}],
        "dependencies": [],
    }
    with pytest.raises(AssertionError):
        validate_classes(fake, cls["expect"])
    pkg = next(c for c in load_cases() if c["family"] == "package"
               and c["id"] == "independent")
    invented = {
        "diagram_type": "package", "uml_version": "2.5.1",
        "packages": [{"id": "alpha"}, {"id": "beta"}],
        "dependencies": [{"client": "alpha", "supplier": "beta", "evidence": ["fake"]}],
    }
    with pytest.raises(AssertionError):
        validate_packages(invented, pkg["expect"])
