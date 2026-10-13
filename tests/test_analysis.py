from pathlib import Path

from pyflowmap.analysis import FlowBuilder, simplify
from pyflowmap.mermaid import to_mermaid
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_pipeline_activity_and_decision(tmp_path):
    result = generate_diagram(str(FIXTURE), entry="pipeline:main", max_nodes=8,
                              output=str(tmp_path))
    assert "Clean" in result["mermaid"]
    assert "Load data" in result["mermaid"]
    assert "Validate?" in result["mermaid"]
    assert "Predict" in result["mermaid"]
    assert "worker" not in result["mermaid"]
    assert (tmp_path / "pipeline_main.mmd").exists()
    assert (tmp_path / "pipeline_main.json").exists()


def test_optional_branch_merge():
    with load_project(FIXTURE) as project:
        graph = FlowBuilder(project).build(project.entry("branching:task"))
    decisions = [n for n in graph.nodes.values() if n.kind == "decision"]
    assert len(decisions) == 1
    decision = decisions[0]
    assert any(e.source == decision.id and e.label == "No" for e in graph.edges)
    assert any(e.source == decision.id and e.label == "Yes" for e in graph.edges)
    assert "Save" in to_mermaid(graph)


def test_loop_has_back_edge():
    with load_project(FIXTURE) as project:
        graph = FlowBuilder(project).build(project.entry("loops:run"))
    loop = next(n for n in graph.nodes.values() if n.kind == "decision")
    assert any(e.target == loop.id and e.label == "Next" for e in graph.edges)
    assert any(e.source == loop.id and e.label == "No" for e in graph.edges)


def test_topology_preserving_simplification():
    with load_project(FIXTURE) as project:
        graph = FlowBuilder(project).build(project.entry("pipeline:main"))
    before = sum(n.kind == "decision" for n in graph.nodes.values())
    simplify(graph, max_nodes=2)
    assert sum(n.kind == "decision" for n in graph.nodes.values()) == before
    assert all(e.source in graph.nodes and e.target in graph.nodes for e in graph.edges)
    assert any("budget" in warning for warning in graph.warnings)


def test_cross_module_symbol_resolution():
    with load_project(FIXTURE) as project:
        graph = FlowBuilder(project).build(project.entry("cross_module:orchestrate"))
    symbols = [s for n in graph.nodes.values() for s in n.symbols]
    assert "worker:fetch" in symbols
    assert "worker:persist" in symbols


def test_mermaid_escapes_special_chars():
    from pyflowmap.models import FlowGraph
    graph = FlowGraph(entry="demo:main")
    graph.add('Load "name" < 4 & done')
    result = to_mermaid(graph)
    assert '&quot;' in result
    assert '&lt;' in result
    assert '&amp;' in result


def test_direct_constructor_method_resolution():
    with load_project(FIXTURE) as project:
        graph = FlowBuilder(project).build(project.entry("pipeline:main"))
    assert any("pipeline:Repository.save" in node.symbols for node in graph.nodes.values())


def test_try_finally_runs_before_explicit_return(tmp_path):
    (tmp_path / "tryflow.py").write_text(
        "def operate():\n    pass\n"
        "def cleanup():\n    pass\n"
        "def main():\n"
        "    try:\n        return operate()\n"
        "    finally:\n        cleanup()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = FlowBuilder(project, language="es").build(project.entry("tryflow:main"))
    cleanup = next(n for n in graph.nodes.values() if n.locations == ["tryflow.py:9"])
    result = next(n for n in graph.nodes.values() if n.kind == "result")
    assert any(e.source == cleanup.id and e.target == result.id for e in graph.edges)


def test_try_handlers_dispatch_only_from_exceptional_body_exits(tmp_path):
    (tmp_path / "handlers.py").write_text(
        "def first():\n    pass\n"
        "def second():\n    pass\n"
        "def main():\n"
        "    try:\n        raise ValueError()\n"
        "    except ValueError:\n        first()\n"
        "    except TypeError:\n        second()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = FlowBuilder(project, language="es").build(project.entry("handlers:main"))
    decisions = [node for node in graph.nodes.values() if node.kind == "decision"]
    dispatch = next(node for node in decisions
                    if node.label_metadata.get("exception_dispatch") == "runtime-dependent")
    labels = {edge.label for edge in graph.edges if edge.source == dispatch.id}
    assert {"ValueError", "TypeError", "Sin coincidencia"} <= labels
    raise_nodes = {node.id for node in graph.nodes.values()
                   if node.label_metadata.get("control_transfer") == "raise"}
    assert raise_nodes
    assert any(edge.source in raise_nodes and edge.target == dispatch.id
               for edge in graph.edges)
    assert any(node.label == "Capturar ValueError"
               and node.locations == ["handlers.py:8"] for node in graph.nodes.values())
    assert any("handler dispatch is approximated" in warning for warning in graph.warnings)
