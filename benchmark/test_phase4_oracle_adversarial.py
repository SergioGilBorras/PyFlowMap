"""Adversarial regressions for the next version of the match oracle.

The first four tests intentionally fail against Phase 3: each graph preserves
the valid route and adds a semantically invalid route, except the final test,
which exposes collisions between separate match statements.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from benchmark.oracles_phase4 import _target_function, _warning_classification, evaluate_semantics
from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project

FIXTURE = Path(__file__).parent / "oracle-audit" / "phase4" / "fixtures" / "adversarial_match.py"


def _analyze(path: Path, entry: str) -> dict:
    with load_project(path.parent) as project:
        return analyze(project, project.entry(entry), max_depth=0).to_dict()


def _match_status(graph: dict, source: Path, entry: str) -> str:
    result = evaluate_semantics({"entry": entry}, source, graph)
    return next(feature["status"] for feature in result["features"]
                if feature["feature"] == "match-case")


def _match_nodes(graph: dict, line: int) -> dict[int, dict]:
    return {
        node["label_metadata"]["match_case_index"]: node
        for node in graph["nodes"]
        if node.get("kind") == "decision"
        and node.get("label_metadata", {}).get("match_case_index") is not None
        and any(location.endswith(f":{line}") for location in node.get("locations", []))
    }


def test_rejected_pattern_cannot_reach_its_own_body_by_an_extra_edge():
    graph = _analyze(FIXTURE, "adversarial_match:classify")
    mutated = copy.deepcopy(graph)
    selector = _match_nodes(mutated, 6)[0]
    body = next(node for node in mutated["nodes"]
                if node.get("label_metadata", {}).get("call_expression") == "consume")
    # Retain the valid pattern-failure -> fallback route and add an impossible
    # failure -> selected body route.
    mutated["edges"].append({"source": selector["id"], "target": body["id"], "label": "No"})
    assert _match_status(mutated, FIXTURE, "adversarial_match:classify") == "FAIL"


def test_false_guard_cannot_reach_its_own_body_by_an_extra_edge():
    graph = _analyze(FIXTURE, "adversarial_match:classify")
    mutated = copy.deepcopy(graph)
    guard = next(node for node in mutated["nodes"]
                 if node.get("label_metadata", {}).get("match_guard_case_index") == 0)
    body = next(node for node in mutated["nodes"]
                if node.get("label_metadata", {}).get("call_expression") == "consume")
    # Keep the correct false -> next case edge as well as an invalid edge.
    mutated["edges"].append({"source": guard["id"], "target": body["id"], "label": "No"})
    assert _match_status(mutated, FIXTURE, "adversarial_match:classify") == "FAIL"


def test_pattern_success_cannot_bypass_required_capture_even_if_valid_path_exists():
    graph = _analyze(FIXTURE, "adversarial_match:classify")
    mutated = copy.deepcopy(graph)
    selector = _match_nodes(mutated, 6)[0]
    guard = next(node for node in mutated["nodes"]
                 if node.get("label_metadata", {}).get("match_guard_case_index") == 0)
    # Preserve the valid selector -> capture -> guard path and add a bypass.
    mutated["edges"].append({"source": selector["id"], "target": guard["id"], "label": "Yes"})
    assert _match_status(mutated, FIXTURE, "adversarial_match:classify") == "FAIL"


def test_two_match_statements_in_one_function_do_not_collide_on_case_index():
    result = evaluate_semantics(
        {"entry": "adversarial_match:two_dispatches"},
        FIXTURE,
        _analyze(FIXTURE, "adversarial_match:two_dispatches"),
    )
    feature = next(feature for feature in result["features"] if feature["feature"] == "match-case")
    assert feature["status"] == "PASS"


def test_nested_and_looped_matches_are_scoped_to_each_execution():
    entry = "adversarial_match:nested_and_repeated"
    result = evaluate_semantics({"entry": entry}, FIXTURE, _analyze(FIXTURE, entry))
    features = [feature for feature in result["features"] if feature["feature"] == "match-case"]
    assert len(features) == 3
    assert [feature["status"] for feature in features] == ["PASS", "PASS", "PASS"]


def test_same_named_functions_resolve_in_the_requested_module():
    fixture_dir = FIXTURE.parent
    for module in ("left_module", "right_module"):
        path = fixture_dir / f"{module}.py"
        entry = f"{module}:handle"
        graph = _analyze(path, entry)
        result = evaluate_semantics({"entry": entry}, path, graph)
        feature = next(item for item in result["features"] if item["feature"] == "match-case")
        assert feature["status"] == "PASS"
    modules = [(path, ast.parse(path.read_text(encoding="utf-8")))
               for path in (fixture_dir / "left_module.py", fixture_dir / "right_module.py")]
    right_worker = _target_function(modules, "right_module:shared_worker")
    assert right_worker is not None
    assert any(isinstance(node, ast.If) and isinstance(node.test, ast.Constant)
               and node.test.value is False for node in right_worker.body)


def test_compound_guard_with_unknown_aggregate_result_remains_review():
    entry = "adversarial_match:compound_guard"
    result = evaluate_semantics({"entry": entry}, FIXTURE, _analyze(FIXTURE, entry))
    feature = next(item for item in result["features"] if item["feature"] == "match-case")
    assert feature["status"] == "REVIEW"


def test_final_pattern_failure_cannot_reach_selected_body():
    entry = "adversarial_match:non_exhaustive"
    graph = _analyze(FIXTURE, entry)
    base = next(item for item in evaluate_semantics({"entry": entry}, FIXTURE, graph)["features"]
                if item["feature"] == "match-case")
    assert base["status"] == "PASS"
    selector = next(node for node in graph["nodes"]
                    if node.get("label_metadata", {}).get("match_case_index") == 0)
    body = next(node for node in graph["nodes"]
                if node.get("label_metadata", {}).get("call_expression") == "selected")
    graph["edges"].append({"source": selector["id"], "target": body["id"], "label": "No"})
    feature = next(item for item in evaluate_semantics({"entry": entry}, FIXTURE, graph)["features"]
                   if item["feature"] == "match-case")
    assert feature["status"] == "FAIL"


def test_data_branches_are_informational_but_loss_warnings_are_reviewed():
    assert _warning_classification("Pattern matching is data-dependent at example.py:4") == (
        "data-dependent-branch", "PASS")
    assert _warning_classification("Call target unresolved at example.py:4") == (
        "dynamic-resolution", "REVIEW")
    assert _warning_classification("Subprocess work summarized at depth boundary") == (
        "expansion-limit", "REVIEW")
    assert _warning_classification("A source activity is not represented") == (
        "activity-not-represented", "REVIEW")
    assert _warning_classification("Reached max depth") == ("expansion-limit", "REVIEW")
