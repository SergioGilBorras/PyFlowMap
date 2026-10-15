"""Package styling changes no project-local package semantics, only visual nodes."""

import json
from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram
from pyflowmap.uml.packages import analyze_package_diagram, to_dot

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "examples" / "uml_showcase"


def test_package_styles_share_exact_dependency_edges():
    with load_project(SHOWCASE) as index:
        model = analyze_package_diagram(index)
    modern = to_dot(model, "LR")
    strict = to_dot(model, "LR", style="strict")
    assert "shape=folder" in modern
    assert 'orientation=90' in modern
    assert 'label="reports"' in modern
    assert 'label="orders"' in modern
    assert 'label="inventory"' in modern
    assert 'WIDTH="39" HEIGHT="26"' not in modern
    assert 'shape=box' not in modern
    assert 'SIDES="LTR"' in strict
    assert 'shape=plain' in strict
    assert 'style=dashed' in modern and 'style=dashed' in strict
    assert 'rankdir=LR' in modern and 'rankdir=LR' in strict
    assert 'http://' not in modern and 'https://' not in modern
    with pytest.raises(ValueError, match="package style"):
        to_dot(model, style="unknown")


def test_styles_generate_self_contained_vector_svg_and_equivalent_json(tmp_path):
    models = {}
    for style in ("modern", "strict"):
        result = generate_diagram(
            str(SHOWCASE), diagram_type="package", format="all",
            renderer="graphviz", direction="LR", package_style=style,
            output=str(tmp_path / style),
        )
        assert result["semantic_provider"] == "disabled"
        assert result["package_style"] == style
        assert set(result["files"]) == {"dot", "json", "svg", "png"}
        models[style] = json.loads(
            Path(result["files"]["json"]).read_text(encoding="utf-8")
        )
        assert models[style]["package_style"] == style
        for filename in result["files"].values():
            assert Path(filename).is_file() and Path(filename).stat().st_size
        if style == "modern":
            svg = Path(result["files"]["svg"]).read_text(encoding="utf-8")
            assert "<svg " in svg
            assert "<image " not in svg and "xlink:href=" not in svg
            assert "<polygon" in svg or "<path" in svg
            assert "<text" in svg
            assert ">reports</text>" in svg
    for payload in models.values():
        payload.pop("package_style")
    assert models["modern"] == models["strict"]


def test_package_cli_default_and_explicit_style(tmp_path, capsys):
    for style in (None, "modern", "strict"):
        argv = ["analyze", str(SHOWCASE), "--diagram-type", "package",
                "--format", "all", "--renderer", "graphviz",
                "--output", str(tmp_path / (style or "default"))]
        if style:
            argv += ["--package-style", style]
        assert main(argv) == 0
        answer = json.loads(capsys.readouterr().out)
        assert answer["package_style"] == (style or "modern")
    assert main(["analyze", str(SHOWCASE), "--diagram-type", "activity",
                 "--entry", "reports.dashboard:main",
                 "--package-style", "strict"]) == 2
    assert "only to package" in capsys.readouterr().err


def test_package_dot_only_needs_no_labeler(tmp_path):
    result = generate_diagram(
        str(SHOWCASE), diagram_type="package", package_style="modern",
        format="dot", output=str(tmp_path / "only_dot"),
    )
    assert result["semantic_provider"] == "disabled"
    assert result["renderer"] is None
    assert set(result["files"]) == {"dot", "json"}
