"""Cross-renderer typography and source-traceability regressions."""

import json
import shutil
from pathlib import Path

import pytest

from pyflowmap.diagrams.activity_labels import ellipsize, source_caption
from pyflowmap.dot import to_dot
from pyflowmap.mermaid import to_mermaid
from pyflowmap.models import FlowGraph
from pyflowmap.render import render
from pyflowmap.service import generate_diagram

P4 = Path(__file__).parent / "fixtures" / "references" / "p4-planning-agent-v1"
ENTRY = "planning.coordinator:PlanningCoordinator.plan"


def test_source_caption_is_limited_but_original_symbols_are_not_changed():
    graph = FlowGraph(entry="very.long.module:Example.run")
    symbol = "very.long.module:ExtravagantlyLongWorkerClassName.performComplicatedOperation"
    node_id = graph.add("Generate results", symbol=symbol, location="example.py:12")
    node = graph.nodes[node_id]
    caption = source_caption(node, limit=24)
    assert caption.startswith("(") and caption.endswith("…)")
    assert len(caption) <= 26  # parentheses on top of the caption length budget
    assert node.symbols == [symbol]
    assert graph.to_dict()["nodes"][0]["symbols"] == [symbol]
    assert ellipsize("short", 10) == "short"


def test_activity_escapes_source_html_for_both_renderers():
    graph = FlowGraph(entry="m:f")
    graph.add("Analyze <x>", symbol='m:Class.method<&"')
    mermaid = to_mermaid(graph)
    dot = to_dot(graph)
    assert "Analyze &lt;x&gt;" in mermaid
    assert "Class.method&lt;&amp;&quot;" in mermaid
    assert "<small>(" in mermaid
    assert '<FONT POINT-SIZE="10" COLOR="#64748b">' in dot
    assert 'labelfontsize=14' in dot or 'fontsize=14' in dot


def test_p4_diagram_two_lines_and_larger_branch_typography(tmp_path):
    result = generate_diagram(str(P4), entry=ENTRY, language="es", format="mmd",
                              output=str(tmp_path))
    text = Path(result["files"]["mmd"]).read_text(encoding="utf-8")
    assert 'Analizar requirement<br/><small>(RequirementAnalysisAgent.analyze)</small>' in text
    assert 'Investigar reuse<br/><small>(ReuseResearchAgent.research)</small>' in text
    assert '"fontSize": "18px"' in text
    assert "-->|Sí|" in text and "-->|No|" in text
    assert text.count('n7["Devolver resultado"]') == 1
    assert text.count('((( )))') == 1
    doc = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    requirements = next(n for n in doc["nodes"] if n["label"] == "Analizar requirement")
    assert requirements["symbols"] == ["planning.requirement_agent:RequirementAnalysisAgent.analyze"]


@pytest.mark.skipif(not shutil.which("dot"), reason="Graphviz unavailable")
def test_graphviz_svg_contains_separate_font_sizes(tmp_path):
    result = generate_diagram(str(P4), entry=ENTRY, language="es", format="svg",
                              renderer="graphviz", output=str(tmp_path))
    svg = Path(result["files"]["svg"]).read_text(encoding="utf-8")
    assert "RequirementAnalysisAgent.analyze" in svg
    assert "font-size=\"10.00\"" in svg
    assert "font-size=\"14.00\"" in svg
    assert "NEEDS_CLARIFICATION" in svg


@pytest.mark.skipif(not shutil.which("dot"), reason="Graphviz unavailable")
def test_graphviz_round_trips_spanish_utf8_labels(tmp_path):
    graph = FlowGraph(entry="modulo:ejecutar")
    graph.add("¿Qué acción realizará? Acción número 1", symbol="módulo:Función.española")
    mmd = tmp_path / "unicode.mmd"
    mmd.write_text("flowchart TD\n A[Unicode]\n", encoding="utf-8")

    svg_path, backend = render(mmd, tmp_path / "unicode.svg", graph, renderer="graphviz")
    svg = svg_path.read_text(encoding="utf-8")
    assert backend == "graphviz"
    assert "¿Qué acción realizará? Acción número 1" in svg
    assert "Función.española" in svg
