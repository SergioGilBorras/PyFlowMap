"""UML 2.5.1 class declaration evidence; activity diagrams remain unchanged."""

import json
from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram
from pyflowmap.uml.classes import analyze_class_diagram, to_dot, to_mermaid


def example(tmp_path):
    pkg = tmp_path / "domain"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base.py").write_text(
        "class Machine:\n"
        "    serial: str\n"
        "    def activate(self, ticks: int) -> bool:\n"
        "        return ticks > 0\n",
        encoding="utf-8",
    )
    (pkg / "device.py").write_text(
        "from .base import Machine as Parent\n"
        "class Sensor(Parent):\n"
        "    MAX = 4\n"
        "    tag: str\n"
        "    def __init__(self, value: int):\n"
        "        self.value: int = value\n"
        "        self.tag = 'registered'\n"
        "    def _read(self) -> int:\n"
        "        return self.value\n"
        "    @staticmethod\n"
        "    def parse(text: str) -> int:\n"
        "        return int(text)\n"
        "class Other:\n"
        "    def execute(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    return pkg


def test_class_uml_model_and_notation(tmp_path):
    example(tmp_path)
    with load_project(tmp_path) as project:
        diagram = analyze_class_diagram(project)
    assert len(diagram.classes) == 3
    edge = diagram.generalizations
    assert len(edge) == 1
    assert edge[0].specific == "domain.device:Sensor"
    assert edge[0].general == "domain.base:Machine"
    sensor = next(c for c in diagram.classes if c.name == "Sensor")
    attrs = {f.name: f for f in sensor.attributes}
    assert attrs["tag"].type == "str"
    assert attrs["value"].type == "int"
    assert attrs["MAX"].static
    operations = {f.name: f for f in sensor.operations}
    assert operations["_read"].visibility == "#"
    assert operations["parse"].static
    assert operations["parse"].parameters == ("text: str",)
    mmd = to_mermaid(diagram)
    dot = to_dot(diagram)
    assert "classDiagram" in mmd
    assert "+parse(text: str): int$" in mmd
    assert "<|--" in mmd
    assert "[dir=back, arrowtail=empty" in dot
    assert "<HR/>" in dot
    assert ">domain::device</FONT>" in dot and ">Sensor</B></FONT>" in dot
    assert diagram.to_dict()["uml_version"] == "2.5.1"


def test_class_export_and_cli_are_additive(tmp_path, capsys):
    example(tmp_path)
    out = tmp_path / "diagram"
    code = main(["analyze", str(tmp_path), "--diagram-type", "class", "--format", "all",
                 "--renderer", "graphviz", "--output", str(out)])
    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["diagram_type"] == "class"
    assert result["classes"] == 3
    assert result["generalizations"] == 1
    assert all(Path(p).is_file() for p in result["files"].values())
    exported = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert len(exported["generalizations"]) == 1
    assert Path(result["files"]["svg"]).stat().st_size > 100
    assert Path(result["files"]["png"]).stat().st_size > 100


def test_class_diagram_requires_no_entry_and_declines_unknown_inferences(tmp_path):
    pkg = example(tmp_path)
    with pytest.raises(ValueError, match="omit --entry"):
        generate_diagram(str(pkg), diagram_type="class", entry="domain.base:Machine")
    with pytest.raises(ValueError, match="deterministic"):
        generate_diagram(str(pkg), diagram_type="class", semantic_provider="codex")
    with pytest.raises(ValueError, match="Class diagrams do not support"):
        generate_diagram(str(pkg), diagram_type="class", view="overview")
    with pytest.raises(ValueError, match="Unsupported diagram type"):
        generate_diagram(str(pkg), diagram_type="sequence")
    with pytest.raises(ValueError, match="limit"):
        generate_diagram(str(pkg), diagram_type="class", max_classes=2)


def test_ambiguous_external_bases_not_synthesized(tmp_path):
    pkg = example(tmp_path)
    (pkg / "missing.py").write_text("class Gadget(unknown_factory()):\n    pass\n")
    with load_project(tmp_path) as project:
        diagram = analyze_class_diagram(project)
    assert len(diagram.generalizations) == 1
    assert any("Unmodeled external" in warning for warning in diagram.warnings)


def test_scope_and_no_class(tmp_path):
    example(tmp_path)
    with load_project(tmp_path) as project:
        diagram = analyze_class_diagram(project, "domain/base.py")
        assert len(diagram.classes) == 1
        assert not diagram.generalizations
    with (pytest.raises(ValueError, match="No class declarations"),
          load_project(tmp_path) as project):
        analyze_class_diagram(project, "domain/__init__.py")


def test_evidence_based_class_dependencies_and_isolation(tmp_path):
    root = tmp_path / "sample"
    root.mkdir()
    (root / "types.py").write_text("class Entity:\n    pass\n", encoding="utf-8")
    (root / "service.py").write_text(
        "from types import Entity as Record\n"
        "class Service:\n"
        "    def run(self, value: Record) -> list[Record]:\n"
        "        return [value]\n"
        "class Unrelated:\n    pass\n", encoding="utf-8",
    )
    with load_project(root) as project:
        diagram = analyze_class_diagram(project)
    assert len(diagram.dependencies) == 1
    dep = diagram.dependencies[0]
    assert dep.client == "service:Service"
    assert dep.supplier == "types:Entity"
    assert dep.evidence == ("service.py:3",)
    assert "Unrelated" not in (dep.client, dep.supplier)
    assert "..>" in to_mermaid(diagram)
    assert "style=dashed, arrowhead=vee" in to_dot(diagram)


def test_showcase_classes_are_connected_only_by_supported_relations():
    source = Path(__file__).resolve().parents[1] / "examples/uml_showcase"
    with load_project(source) as project:
        diagram = analyze_class_diagram(project)
    assert len(diagram.classes) == 4
    assert len(diagram.generalizations) == 1
    assert {(d.client, d.supplier) for d in diagram.dependencies} == {
        ("orders.service:OrderService", "inventory.models:PhysicalItem"),
        ("reports.dashboard:Dashboard", "inventory.models:PhysicalItem"),
    }
    assert all(d.evidence for d in diagram.dependencies)
