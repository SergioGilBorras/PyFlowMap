import json
from pathlib import Path

from pyflowmap.models import FlowGraph
from pyflowmap.overview import function_overview
from pyflowmap.service import generate_diagram


def test_process_outline_follows_call_boundaries_and_keeps_source_traceability():
    graph = FlowGraph(entry="app:main")
    start = graph.add("", "initial")
    decision = graph.add("ready?", "decision", "app:main", "app.py:4")
    first_call = graph.add("Prepare input", "activity", "app:main", "app.py:5")
    graph.nodes[first_call].label_metadata = {
        "significant_call": True,
        "caller_symbol": "app:main",
        "resolved_target": "app:worker.run",
        "call_resolution": "resolved",
    }
    sub_call = graph.add("Run worker\nPossible internal calls: Process input (20); Save result (24)",
                         "activity", "app:worker.run", "app.py:8")
    graph.nodes[sub_call].label_metadata = {
        "significant_call": True,
        "caller_symbol": "app:worker.run",
        "resolved_target": "app:worker.run_node",
        "subprocess_calls": [{
            "expression": "self.agent.process",
            "location": "app.py:20",
            "targets": ["app:agent.process"],
            "label": "Process input",
            "resolution": "possible",
        }],
    }
    hidden_decision = graph.add("internal condition?", "decision", "app:worker.run", "app.py:12")
    end = graph.add("", "final")
    graph.connect(start, decision)
    graph.connect(decision, first_call, "Yes")
    graph.connect(decision, end, "No")
    graph.connect(first_call, sub_call)
    graph.connect(sub_call, hidden_decision)
    graph.connect(hidden_decision, end, "Yes")
    graph.connect(hidden_decision, end, "No")

    overview = function_overview(graph)

    assert [node.label for node in overview.nodes.values()
            if node.kind == "activity"] == [
                "Prepare input",
                "Run worker\nCalls found in source:\nProcess input (20)\nSave result (24)",
            ]
    assert overview.entry == graph.entry
    assert all(not edge.label for edge in overview.edges if edge.label in {"Yes", "No"})
    run = next(node for node in overview.nodes.values() if node.label.startswith("Run worker"))
    assert run.label_metadata["overview_source_nodes"] == [sub_call]
    final = next(node for node in overview.nodes.values() if node.kind == "final")
    omitted = final.label_metadata["overview_source_node_ids"]
    assert {decision, hidden_decision} <= set(omitted)
    assert all(isinstance(item, str) for item in omitted)
    assert "overview_source_graph_reference" in final.label_metadata
    assert "overview_omitted_nodes" not in final.label_metadata
    assert any("not a UML activity diagram" in warning for warning in overview.warnings)


def test_process_outline_does_not_claim_an_activity_when_no_call_path_exists():
    graph = FlowGraph(entry="app:main")
    graph.add("", "initial")
    graph.add("condition", "decision", "app:main", "app.py:10")
    graph.add("", "final")

    overview = function_overview(graph)

    assert not any(node.kind == "decision" for node in overview.nodes.values())
    assert any("not a UML activity diagram" in warning for warning in overview.warnings)


def test_overview_service_identifies_the_non_activity_view(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def main():\n    worker()\n", encoding="utf-8")

    result = generate_diagram(str(source), entry="app:main", view="overview",
                              output=str(tmp_path / "out"))

    assert result["diagram_type"] == "process-summary"


def test_overview_serializes_references_without_embedding_source_graph(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def main():\n    worker()\ndef worker():\n    save()\ndef save(): pass\n",
                      encoding="utf-8")
    result = generate_diagram(str(source), entry="app:main", view="overview",
                              output=str(tmp_path / "out"))
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    final = next(node for node in graph["nodes"] if node["kind"] == "final")
    assert len(final["label_metadata"]["overview_source_node_ids"]) > 0
    assert "overview_omitted_nodes" not in final["label_metadata"]
    assert Path(result["files"]["json"]).stat().st_size < 20_000
