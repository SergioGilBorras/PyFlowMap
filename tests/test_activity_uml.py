"""UML-inspired notation and branching invariants."""

import json
import os
from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.diagrams.activity import analyze
from pyflowmap.mcp_server import generate_activity_diagram
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram

P4 = Path(__file__).parent / "fixtures" / "references" / "p4-planning-agent-v1"
ENTRY = "planning.coordinator:PlanningCoordinator.plan"


def test_pinned_p4_conditional_polality_shared_return_and_uml_markers():
    with load_project(P4) as project:
        graph = analyze(project, project.entry(ENTRY), language="es")
    kinds = [n.kind for n in graph.nodes.values()]
    assert kinds.count("initial") == 1
    assert kinds.count("final") == 1
    assert kinds.count("result") == 1
    assert len([n for n in graph.nodes.values() if n.kind == "decision"]) == 1
    lookup = {n.label: n.id for n in graph.nodes.values()}
    decision = next(n.id for n in graph.nodes.values() if n.kind == "decision"
                    and "NEEDS_CLARIFICATION" in n.label)
    results = lookup["Devolver resultado"]
    assert any(e.source == decision and e.label == "Sí" and e.target == results
               for e in graph.edges)
    assert any(e.source == decision and e.label == "No" and
               graph.nodes[e.target].label == "Investigar reuse" for e in graph.edges)
    assert len([e for e in graph.edges if e.target == results]) == 2
    assert len([e for e in graph.edges if e.source == results]) == 1
    assert graph.nodes[graph.edges[-1].target].kind == "final"


def test_activity_from_pinned_p4_export_and_renderer(tmp_path):
    result = generate_diagram(str(P4), entry=ENTRY, language="es", format="all",
                              renderer="graphviz", output=str(tmp_path))
    assert result["renderer"] == "graphviz"
    for extension in ("mmd", "json", "svg", "png"):
        assert Path(result["files"][extension]).is_file()
    text = Path(result["files"]["mmd"]).read_text(encoding="utf-8")
    assert "(( ))" in text and "((( )))" in text
    assert "NEEDS_CLARIFICATION" in text
    assert "Sí" in text and "No" in text
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert any(n["kind"] == "final" for n in graph["nodes"])


def test_single_entry_cli_and_per_type_mcp(tmp_path, capsys, monkeypatch):
    target = tmp_path / "generated"
    assert main(["analyze", str(P4), "--entry", ENTRY, "--diagram-type", "activity",
                 "--language", "es", "--renderer", "graphviz", "--format", "svg",
                 "--output", str(target)]) == 0
    assert "graphviz" in capsys.readouterr().out
    monkeypatch.setenv("PYFLOWMAP_ALLOWED_ROOTS", os.pathsep.join((str(tmp_path.parent), str(P4.parent))))
    generated = generate_activity_diagram(str(P4), entry_point=ENTRY, language="es",
                                           output_path=str(target), renderer="graphviz")
    assert generated["diagram_type"] == "activity"
    assert "NEEDS_CLARIFICATION" in generated["mermaid"]
    with pytest.raises(ValueError, match="outside allowed"):
        generate_activity_diagram(str(tmp_path.parent.parent), output_path=str(target))


def test_other_diagram_types_rejected_explicitly(tmp_path):
    with pytest.raises(ValueError, match="Unsupported diagram type"):
        generate_diagram(str(P4), entry=ENTRY, diagram_type="sequence",
                         output=str(tmp_path))


def test_return_from_inlined_function_reconnects_to_caller(tmp_path):
    (tmp_path / "run.py").write_text(
        "def load(): pass\n"
        "def process(): pass\n"
        "def finish(): pass\n"
        "def stage(flag):\n"
        "    load()\n"
        "    if flag:\n"
        "        return process()\n"
        "    return load()\n"
        "def main():\n"
        "    stage(True)\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("run:main"), max_nodes=15)
    nodes = {n.id: n.label for n in graph.nodes.values()}
    finishes = [key for key, label in nodes.items() if label == "Finish"]
    assert len(finishes) == 1
    ending = finishes[0]
    # The two explicit returns in stage() converge on the caller continuation.
    assert len([edge for edge in graph.edges if edge.target == ending]) == 2
