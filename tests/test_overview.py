from pyflowmap.models import FlowGraph
from pyflowmap.overview import function_overview


def test_function_overview_keeps_observed_boundaries_and_source_traceability():
    graph = FlowGraph(entry="app:run")
    start = graph.add("", "initial")
    branch = graph.add("condition", "decision", "app:run", "app.py:10")
    worker_1 = graph.add("prepare", "activity", "app:worker", "app.py:20")
    worker_2 = graph.add("finish", "activity", "app:worker", "app.py:21")
    fallback = graph.add("fallback", "activity", "app:fallback", "app.py:30")
    result = graph.add("return", "result", "app:run", "app.py:40")
    end = graph.add("", "final")
    graph.connect(start, branch)
    graph.connect(branch, worker_1, "Yes")
    graph.connect(branch, fallback, "No")
    graph.connect(worker_1, worker_2)
    graph.connect(worker_2, result)
    graph.connect(fallback, result)
    graph.connect(result, end)

    overview = function_overview(graph)

    assert overview.entry == graph.entry
    assert len(overview.nodes) == 6
    assert not any(node.kind == "decision" for node in overview.nodes.values())
    assert {(edge.label, overview.nodes[edge.source].kind,
             overview.nodes[edge.target].kind)
            for edge in overview.edges if edge.label} == {
                ("Yes", "activity", "activity"), ("No", "activity", "activity")
            }
    worker = next(node for node in overview.nodes.values()
                  if node.symbols == ["app:worker"])
    assert worker.locations == ["app.py:20", "app.py:21"]
    assert worker.label_metadata["overview_source_nodes"] == [worker_1, worker_2]
    assert any("detailed diagram" in warning for warning in overview.warnings)
