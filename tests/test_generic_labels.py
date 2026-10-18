"""Labels must generalize to arbitrary user code, never symbol-specific overrides."""

import ast

from pyflowmap.analysis import FlowBuilder, display_call
from pyflowmap.diagrams.labeling import describe_symbol
from pyflowmap.project import Symbol, load_project


def _symbol(name: str, owner: str, doc: str = "") -> Symbol:
    body = f'"""{doc}"""\n    pass' if doc else 'pass'
    node = ast.parse(f'def {name}(self):\n    {body}\n').body[0]
    return Symbol(f"demo:{owner}.{name}", name, "demo", "demo.py", node, owner)


def test_generically_derived_labels_for_unrelated_projects():
    assert describe_symbol(_symbol("analyze", "GalaxyAnalysisAgent"), "en") == "Analyze galaxy"
    assert describe_symbol(_symbol("analyze", "GalaxyAnalysisAgent"), "es") == "Analizar galaxy"
    assert describe_symbol(_symbol("research", "ForestResearchAgent"), "es") == "Investigar forest"
    assert describe_symbol(_symbol("load", "DataLoader"), "en") == "Load data"
    assert describe_symbol(_symbol("run", "BluePrinter"), "en") == "Run blue printer"
    assert describe_symbol(_symbol("mix", "SolarMixer"), "en") == "Mix solar mixer"


def test_docstring_preferred_and_source_unchanged():
    symbol = _symbol("execute", "AstronautAgent", "Coordinate the lunar survey.")
    assert describe_symbol(symbol, "en") == "Coordinate the lunar survey"
    assert symbol.id == "demo:AstronautAgent.execute"
    call = ast.parse("worker.execute()", mode="eval").body
    assert display_call(call, symbol, "es") == "Coordinate the lunar survey"


def test_no_domain_specific_status_guard_and_polarity(tmp_path):
    (tmp_path / "demo.py").write_text(
        "def reject(): pass\n"
        "def accept(): pass\n"
        "def route(state):\n"
        "    if state == 'NEEDS_CLARIFICATION':\n"
        "        reject()\n"
        "    else:\n"
        "        accept()\n"
    )
    with load_project(tmp_path) as project:
        graph = FlowBuilder(project, language="es").build(project.entry("demo:route"))
    decision = next(n for n in graph.nodes.values() if n.kind == "decision")
    yes = next(e for e in graph.edges if e.source == decision.id and e.label == "Sí")
    no = next(e for e in graph.edges if e.source == decision.id and e.label == "No")
    assert "NEEDS_CLARIFICATION" in decision.label
    assert graph.nodes[yes.target].label == "Reject"
    assert graph.nodes[no.target].label == "Accept"


def test_guard_on_any_other_domain_state(tmp_path):
    (tmp_path / "demo.py").write_text(
        "def success(): pass\n"
        "def stop(): pass\n"
        "def run(state):\n"
        "    if state != 'CLOSED':\n"
        "        success()\n"
        "    else:\n"
        "        stop()\n"
    )
    with load_project(tmp_path) as project:
        graph = FlowBuilder(project, language="es").build(project.entry("demo:run"))
    decision = next(n for n in graph.nodes.values() if n.kind == "decision")
    assert "distinto de 'CLOSED'" in decision.label
    assert any(e.label == "Sí" and graph.nodes[e.target].label == "Success"
               for e in graph.edges if e.source == decision.id)
