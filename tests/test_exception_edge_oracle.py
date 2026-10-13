from __future__ import annotations

import copy

from benchmark.oracles_phase5_2 import evaluate_semantics
from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def _graph(tmp_path, source: str):
    module = tmp_path / "edge_case.py"
    module.write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("edge_case:run"), max_depth=0).to_dict()
    return module, graph


def _raise_node(graph):
    return next(node for node in graph["nodes"]
                if (node.get("label_metadata", {}) or {}).get("control_transfer") == "raise")


def test_valid_raise_to_finally_cleanup_is_pass(tmp_path):
    source, graph = _graph(tmp_path, """def run():
    try:
        raise marker
    finally:
        cleaned = True
    return cleaned
""")

    result = evaluate_semantics({"entry": "edge_case:run"}, source, graph)

    assert result["status"] == "PASS"


def test_raise_cannot_also_take_a_normal_edge_past_cleanup(tmp_path):
    source, graph = _graph(tmp_path, """def run():
    try:
        raise marker
    finally:
        cleaned = True
    finish()
    return cleaned

def finish():
    return None
""")
    mutated = copy.deepcopy(graph)
    throw = _raise_node(mutated)
    finish = next(node for node in mutated["nodes"]
                  if (node.get("label_metadata", {}) or {}).get("call_expression") == "finish")
    mutated["edges"].append({"source": throw["id"], "target": finish["id"], "label": ""})

    result = evaluate_semantics({"entry": "edge_case:run"}, source, mutated)

    assert result["status"] == "FAIL"
    feature = next(item for item in result["features"]
                   if item["feature"] == "raise-control-flow")
    assert feature["evidence"]["invalid_successors"]
