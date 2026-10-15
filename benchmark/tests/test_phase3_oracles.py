"""Mutation tests for the versioned structural-pattern oracle."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from portable_tempdirs import temporary_directory

from benchmark.evaluation.oracles import evaluate_semantics as legacy_evaluate_semantics
from benchmark.evaluation.oracles_phase3 import evaluate_semantics
from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project

FIXTURES = Path(__file__).parents[1] / "regressions" / "match-guards"


def _analyze(fixture: Path, entry: str):
    with load_project(fixture.parent) as project:
        graph = analyze(project, project.entry(entry), max_depth=0)
        return graph.to_dict()


def _feature(graph, fixture, entry):
    result = evaluate_semantics({"entry": entry}, fixture, graph)
    return next(item for item in result["features"] if item["feature"] == "match-case")


def _edge(graph, source, target, label=None):
    return next(edge for edge in graph["edges"]
                if edge["source"] == source and edge["target"] == target
                and (label is None or edge["label"].casefold() == label.casefold()))


def _selectors(graph):
    return {node["label_metadata"]["match_case_index"]: node
            for node in graph["nodes"]
            if isinstance(node.get("label_metadata", {}).get("match_case_index"), int)
            and node["kind"] == "decision"}


def test_valid_guarded_ordered_match_no_longer_gets_false_fail():
    fixture = FIXTURES / "ordered_dispatch.py"
    graph = _analyze(fixture, "ordered_dispatch:classify")
    legacy = legacy_evaluate_semantics({"entry": "ordered_dispatch:classify"}, fixture, graph)
    old_match = next(item for item in legacy["features"] if item["feature"] == "match-case")
    assert old_match["status"] == "FAIL"
    feature = _feature(graph, fixture, "ordered_dispatch:classify")
    assert feature["status"] == "PASS"
    assert feature["evidence"]["missing"] == []


def test_mutation_inverted_guard_is_detected():
    fixture = FIXTURES / "ordered_dispatch.py"
    graph = _analyze(fixture, "ordered_dispatch:classify")
    selectors = _selectors(graph)
    guard = next(node for node in graph["nodes"]
                 if node.get("label_metadata", {}).get("match_guard_case_index") == 1)
    yes = next(e for e in graph["edges"] if e["source"] == guard["id"]
               and e["label"].casefold() == "yes")
    no = next(e for e in graph["edges"] if e["source"] == guard["id"]
              and e["label"].casefold() == "no")
    yes["label"], no["label"] = no["label"], yes["label"]
    assert selectors
    assert _feature(graph, fixture, "ordered_dispatch:classify")["status"] == "FAIL"


def test_mutation_retrying_an_earlier_case_is_detected():
    fixture = FIXTURES / "ordered_dispatch.py"
    graph = _analyze(fixture, "ordered_dispatch:classify")
    selectors = _selectors(graph)
    failure_edge = next(edge for edge in graph["edges"]
                        if edge["source"] == selectors[1]["id"]
                        and edge["label"].casefold() == "no")
    failure_edge["target"] = selectors[0]["id"]
    assert _feature(graph, fixture, "ordered_dispatch:classify")["status"] == "FAIL"


def test_compound_guard_is_reviewed_instead_of_claimed_as_correct():
    owner = temporary_directory("pyflowmap-compound-guard", parent=tempfile.gettempdir())
    try:
        fixture = Path(owner.path) / "compound.py"
        fixture.write_text(
            "def route(message, primary, secondary):\n"
            "    match message:\n"
            "        case {'payload': payload} if primary(payload) and secondary(payload):\n"
            "            consume(payload)\n"
            "        case _:\n"
            "            skip()\n",
            encoding="utf-8",
        )
        graph = _analyze(fixture, "compound:route")
        feature = _feature(graph, fixture, "compound:route")
        assert feature["status"] == "REVIEW"
        assert feature["evidence"]["uncertain"]
    finally:
        owner.cleanup()


def test_captures_precede_guard_and_mutated_late_binding_is_detected():
    fixture = FIXTURES / "capture_guard.py"
    graph = _analyze(fixture, "capture_guard:route")
    feature = _feature(graph, fixture, "capture_guard:route")
    assert feature["status"] == "PASS"

    mutated = copy.deepcopy(graph)
    capture = next(node for node in mutated["nodes"]
                   if node.get("label_metadata", {}).get("pattern_captures") == ["payload"])
    guard = next(node for node in mutated["nodes"]
                 if node.get("label_metadata", {}).get("match_guard_case_index") == 0)
    # Reverse the normal capture -> guard path to simulate using the name first.
    selector = _selectors(mutated)[0]
    use = next(node for node in mutated["nodes"]
               if node.get("label_metadata", {}).get("call_expression") == "usable")
    before_capture = next(edge for edge in mutated["edges"]
                          if edge["source"] == selector["id"] and edge["target"] == capture["id"])
    capture_to_use = next(edge for edge in mutated["edges"]
                          if edge["source"] == capture["id"] and edge["target"] == use["id"])
    guard_to_body = next(edge for edge in mutated["edges"] if edge["source"] == guard["id"]
                         and edge["label"].casefold() == "yes")
    mutated["edges"].remove(before_capture)
    mutated["edges"].remove(capture_to_use)
    mutated["edges"].remove(guard_to_body)
    mutated["edges"].append({"source": selector["id"], "target": use["id"], "label": "Yes"})
    mutated["edges"].append({"source": guard["id"], "target": capture["id"], "label": "Yes"})
    mutated["edges"].append({"source": capture["id"], "target": guard_to_body["target"], "label": ""})
    assert _feature(mutated, fixture, "capture_guard:route")["status"] == "FAIL"
