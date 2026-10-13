"""Adversarial tests for the Phase 4.1 semantic evaluator."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from benchmark.oracles_phase4_1 import evaluate_semantics
from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project

FIXTURE = Path(__file__).parent / "oracle-audit" / "phase4_1" / "fixtures" / "python_semantics.py"


def _analyze(entry: str) -> dict:
    with load_project(FIXTURE.parent) as project:
        return analyze(project, project.entry(entry), max_depth=0).to_dict()


def _feature(result: dict, name: str) -> dict:
    return next(item for item in result["features"] if item["feature"] == name)


def _evaluate(entry: str, graph: dict | None = None) -> dict:
    return evaluate_semantics({"entry": entry}, FIXTURE, graph or _analyze(entry))


def _line(node: dict, lineno: int) -> bool:
    return any(location.endswith(f":{lineno}") for location in node.get("locations", []))


def test_positive_pattern_path_cannot_gain_an_edge_to_a_later_case_body():
    graph = _analyze("python_semantics:dispatch")
    mutated = copy.deepcopy(graph)
    selector = next(n for n in mutated["nodes"]
                    if n.get("label_metadata", {}).get("match_case_index") == 0)
    later_body = next(n for n in mutated["nodes"]
                      if n.get("label_metadata", {}).get("call_expression") == "reject")
    # Keep the valid pattern-success route and add an impossible selection.
    mutated["edges"].append({"source": selector["id"], "target": later_body["id"], "label": "Sí"})
    assert _feature(_evaluate("python_semantics:dispatch", mutated), "match-case")["status"] == "FAIL"


def test_guard_true_cannot_skip_its_body_for_a_later_case():
    graph = _analyze("python_semantics:dispatch")
    mutated = copy.deepcopy(graph)
    guard = next(n for n in mutated["nodes"]
                 if n.get("label_metadata", {}).get("match_guard_case_index") == 0)
    later_body = next(n for n in mutated["nodes"]
                      if n.get("label_metadata", {}).get("call_expression") == "reject")
    mutated["edges"].append({"source": guard["id"], "target": later_body["id"], "label": "Sí"})
    assert _feature(_evaluate("python_semantics:dispatch", mutated), "match-case")["status"] == "FAIL"


def test_terminal_return_cannot_gain_an_ordinary_successor():
    graph = _analyze("python_semantics:single_return")
    mutated = copy.deepcopy(graph)
    result = next(n for n in mutated["nodes"]
                  if n.get("kind") == "result" and n.get("label_metadata", {}).get("return_value") == 17)
    other = next(n for n in mutated["nodes"]
                 if n.get("kind") == "result" and n.get("label_metadata", {}).get("return_value") == 23)
    mutated["edges"].append({"source": result["id"], "target": other["id"], "label": ""})
    assert _feature(_evaluate("python_semantics:single_return", mutated), "terminal-successors")["status"] == "FAIL"


def test_each_explicit_return_is_checked_even_when_it_is_not_a_distinct_value():
    graph = _analyze("python_semantics:single_return")
    mutated = copy.deepcopy(graph)
    missing = next(n for n in mutated["nodes"]
                   if n.get("kind") == "result" and n.get("label_metadata", {}).get("return_value") == 17)
    mutated["nodes"].remove(missing)
    mutated["edges"] = [e for e in mutated["edges"]
                        if e["source"] != missing["id"] and e["target"] != missing["id"]]
    result = _evaluate("python_semantics:single_return", mutated)
    assert _feature(result, "explicit-return-preservation")["status"] == "FAIL"


def test_python_bytes_set_and_complex_literals_do_not_crash_the_evaluator():
    graph = _analyze("python_semantics:literal_values")
    result = _evaluate("python_semantics:literal_values", graph)
    assert result["status"] in {"PASS", "REVIEW", "FAIL", "UNSUPPORTED"}
    assert _feature(result, "explicit-return-preservation")["evidence"]["explicit_return_count"] == 3


def test_context_manager_with_multiple_exit_routes_remains_uncertain():
    graph = _analyze("python_semantics:use_context")
    feature = _feature(_evaluate("python_semantics:use_context", graph), "context-manager")
    assert feature["status"] == "REVIEW"
    assert feature["evidence"]["entry_count"] >= 1
    assert feature["evidence"]["exit_count"] >= 1
    assert feature["evidence"]["body_nodes"]


def test_context_body_omission_is_rejected():
    graph = _analyze("python_semantics:use_context")
    mutated = copy.deepcopy(graph)
    module = ast.parse(FIXTURE.read_text(encoding="utf-8"))
    function = next(n for n in module.body
                    if isinstance(n, ast.FunctionDef) and n.name == "use_context")
    omitted_line = next(n.lineno for n in ast.walk(function) if isinstance(n, ast.Return))
    removed = [n for n in mutated["nodes"] if _line(n, omitted_line)]
    assert removed
    removed_ids = {n["id"] for n in removed}
    mutated["nodes"] = [n for n in mutated["nodes"] if n["id"] not in removed_ids]
    mutated["edges"] = [e for e in mutated["edges"]
                        if e["source"] not in removed_ids and e["target"] not in removed_ids]
    feature = _feature(_evaluate("python_semantics:use_context", mutated), "context-manager")
    assert feature["status"] == "FAIL"
    assert omitted_line in feature["evidence"]["missing_body_lines"]


def test_async_context_manager_keeps_entry_body_and_exit_visible():
    graph = _analyze("python_semantics:use_async_context")
    feature = _feature(_evaluate("python_semantics:use_async_context", graph), "context-manager")
    assert feature["status"] in {"PASS", "REVIEW"}
    assert feature["evidence"]["async"] is True
    assert feature["evidence"]["entry_count"] >= 1
    assert feature["evidence"]["exit_count"] >= 1


def test_fixture_source_has_the_expected_independent_python_constructs():
    tree = ast.parse(FIXTURE.read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.Match) for n in ast.walk(tree))
    assert any(isinstance(n, ast.With) for n in ast.walk(tree))
    assert any(isinstance(n, ast.AsyncWith) for n in ast.walk(tree))
