"""UML 2.5.1 packages: explicit namespace boundaries and local imports."""

import json
from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram
from pyflowmap.uml.packages import analyze_package_diagram, to_dot


def project(tmp_path):
    root = tmp_path / "sample"
    for dirname in ("myapp", "myapp/feature", "other"):
        folder = root / dirname
        folder.mkdir(parents=True)
        (folder / "__init__.py").write_text("", encoding="utf-8")
    (root / "myapp/base.py").write_text(
        "class Base:\n    pass\n", encoding="utf-8",
    )
    (root / "myapp/feature/api.py").write_text(
        "from .. import base\n"
        "def run():\n    return base.Base()\n",
        encoding="utf-8",
    )
    (root / "other/client.py").write_text(
        "from myapp.feature import api\n"
        "import json\n"
        "def main():\n    return api.run()\n",
        encoding="utf-8",
    )
    return root


def test_package_model_has_correct_clients_suppliers_and_nesting(tmp_path):
    root = project(tmp_path)
    with load_project(root) as index:
        diagram = analyze_package_diagram(index)
    assert [item.id for item in diagram.packages] == ["myapp", "myapp.feature", "other"]
    nested = {item.id: item.parent for item in diagram.packages}
    assert nested["myapp.feature"] == "myapp"
    assert nested["myapp"] is None
    assert {(edge.client, edge.supplier) for edge in diagram.dependencies} == {
        ("myapp.feature", "myapp"), ("other", "myapp.feature"),
    }
    assert all(edge.evidence for edge in diagram.dependencies)
    dot = to_dot(diagram, style="strict")
    assert "shape=plain" in dot
    assert 'SIDES="LTR"' in dot
    assert "style=dashed, arrowhead=vee" in dot
    assert ">Myapp::Feature</B></FONT>" in dot
    assert "arrowhead=empty" not in dot
    assert diagram.to_dict()["uml_version"] == "2.5.1"


def test_package_cli_exports_uml_dot_and_images(tmp_path, capsys):
    root = project(tmp_path)
    assert main(["analyze", str(root), "--diagram-type", "package", "--format", "all",
                 "--renderer", "graphviz", "--output", str(tmp_path / "out")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["diagram_type"] == "package"
    assert result["packages"] == 3
    assert result["dependencies"] == 2
    assert set(result["files"]) == {"dot", "json", "svg", "png"}
    assert all(Path(path).is_file() for path in result["files"].values())
    payload = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert len(payload["dependencies"]) == 2


def test_package_rejects_mermaid_and_nonstatic_options(tmp_path):
    root = project(tmp_path)
    with pytest.raises(ValueError, match="Mermaid cannot express"):
        generate_diagram(str(root), diagram_type="package", format="mmd")
    with pytest.raises(ValueError, match="Mermaid does not offer"):
        generate_diagram(str(root), diagram_type="package", format="all", renderer="mermaid")
    with pytest.raises(ValueError, match="omit --entry"):
        generate_diagram(str(root), diagram_type="package", entry="other.client:main")
    with pytest.raises(ValueError, match="deterministic"):
        generate_diagram(str(root), diagram_type="package", semantic_provider="codex")
    with pytest.raises(ValueError, match="only available"):
        generate_diagram(str(root), diagram_type="activity", format="dot")
    with pytest.raises(ValueError, match="limit"):
        generate_diagram(str(root), diagram_type="package", format="all", max_packages=2)


def test_package_scope_and_flat_project_do_not_invent_namespaces(tmp_path):
    root = project(tmp_path)
    with load_project(root) as index:
        diagram = analyze_package_diagram(index, "myapp/feature")
        assert [p.id for p in diagram.packages] == ["myapp.feature"]
        assert diagram.dependencies == []
    single = tmp_path / "single.py"
    single.write_text("def main():\n    return 1\n", encoding="utf-8")
    with load_project(single) as index, pytest.raises(ValueError, match="No declared Python packages"):
        analyze_package_diagram(index)


def test_package_svg_has_left_tab_not_folder_notch(tmp_path):
    root = project(tmp_path)
    with load_project(root) as index:
        diagram = analyze_package_diagram(index)
    dot = to_dot(diagram, direction="LR", style="strict")
    assert 'SIDES="LTR"' in dot
    assert 'WIDTH="88" HEIGHT="18"' in dot
    assert 'arrowhead=vee' in dot and 'style=dashed' in dot
    assert 'rankdir=LR' in dot
    assert 'shape=folder' not in dot
