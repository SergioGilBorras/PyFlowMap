"""Unit tests for source-derived benchmark oracles (no fixture execution)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from portable_tempdirs import temporary_directory

from benchmark.evaluation.oracles import evaluate_semantics
from benchmark.runners.run import inspect_graph


def node(node_id, kind, line=None, label="", metadata=None, symbols=None):
    return {"id": node_id, "kind": kind, "label": label,
            "locations": [f"sample.py:{line}"] if line else [],
            "symbols": symbols or [], "label_metadata": metadata or {}}


def graph(nodes, edges, warnings=None):
    return {"entry": "sample:run", "nodes": nodes,
            "edges": [{"source": a, "target": b, "label": label} for a, b, label in edges],
            "warnings": warnings or []}


class SemanticOracleTests(unittest.TestCase):
    def setUp(self):
        self.owner = temporary_directory("pyflowmap-oracle-tests", parent=tempfile.gettempdir())
        self.root = Path(self.owner.__enter__())
        self.addCleanup(self.owner.__exit__, None, None, None)

    def evaluate(self, text, diagram, entry="sample:run"):
        path = self.root / "sample.py"
        path.write_text(text, encoding="utf-8")
        return evaluate_semantics({"entry": entry}, path, diagram)

    def test_match_keeps_each_guarded_alternative_and_result(self):
        source = ("def run(value):\n"
                  "    match value:\n"
                  "        case 0:\n"
                  "            return 'zero'\n"
                  "        case 1 if value > 0:\n"
                  "            return 'one'\n"
                  "        case _:\n"
                  "            return 'other'\n")
        g = graph([
            node("n1", "initial"), node("n2", "decision", 5),
            node("n3", "result", 4, "zero", {"return_value": "zero"}),
            node("n4", "result", 6, "one", {"return_value": "one"}),
            node("n5", "result", 8, "other", {"return_value": "other"}),
            node("n6", "final"), node("n7", "decision", 2, "select case"),
        ], [("n1", "n7", ""), ("n7", "n3", "case 0"), ("n7", "n2", "case 1"),
            ("n7", "n5", "case _"), ("n2", "n4", "Sí"), ("n2", "n5", "No"),
            ("n3", "n6", ""), ("n4", "n6", ""), ("n5", "n6", "")])
        result = self.evaluate(source, g)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(next(x for x in result["features"] if x["feature"] == "match-case")["evidence"]["alternatives"], 3)

    def test_missing_match_arm_is_fail_not_review(self):
        source = "def run(value):\n    match value:\n        case 0:\n            return 0\n        case _:\n            return 1\n"
        g = graph([node("n1", "initial"), node("n2", "activity", 2, "match summary"),
                   node("n3", "final")], [("n1", "n2", ""), ("n2", "n3", "")])
        result = self.evaluate(source, g)
        self.assertEqual(next(x for x in result["features"] if x["feature"] == "match-case")["status"], "FAIL")

    def test_for_else_requires_exhaustion_route_and_break_bypass(self):
        source = ("def run(items):\n"
                  "    for item in items:\n"
                  "        if item:\n"
                  "            break\n"
                  "    else:\n"
                  "        finish()\n"
                  "    return 0\n")
        g = graph([node("n1", "initial"), node("n2", "decision", 2, "More items?"),
                   node("n3", "activity", 4, "break"), node("n4", "activity", 6, "finish"),
                   node("n5", "result", 7, "0", {"return_value": 0}), node("n6", "final")],
                  [("n1", "n2", ""), ("n2", "n3", "Sí"), ("n2", "n4", "No"),
                   ("n3", "n5", ""), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, g)["features"] if x["feature"] == "for-else")
        self.assertEqual(feature["status"], "PASS")
        broken = graph(g["nodes"], [("n1", "n2", ""), ("n2", "n3", "Sí"),
                                     ("n2", "n4", "No"), ("n3", "n4", ""),
                                     ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, broken)["features"] if x["feature"] == "for-else")
        self.assertEqual(feature["status"], "FAIL")

    def test_distinct_return_literals_need_source_linked_values(self):
        source = "def run(flag):\n    if flag:\n        return 200\n    return 404\n"
        g = graph([node("n1", "initial"), node("n2", "decision", 2),
                   node("n3", "result", 3, "result", {"return_value": 200}),
                   node("n4", "result", 4, "result", {}), node("n5", "final")],
                  [("n1", "n2", ""), ("n2", "n3", "Sí"), ("n2", "n4", "No"),
                   ("n3", "n5", ""), ("n4", "n5", "")])
        feature = next(x for x in self.evaluate(source, g)["features"] if x["feature"] == "return-values")
        self.assertEqual(feature["status"], "FAIL")
        self.assertEqual(len(feature["evidence"]["missing"]), 1)

    def test_raise_cannot_reach_later_normal_activity(self):
        source = "def run(flag):\n    if flag:\n        raise ValueError()\n    finish()\n    return 0\n"
        g = graph([node("n1", "initial"), node("n2", "decision", 2),
                   node("n3", "activity", 3, "Raise ValueError"),
                   node("n4", "activity", 4, "finish"), node("n5", "result", 5, "0"),
                   node("n6", "final")],
                  [("n1", "n2", ""), ("n2", "n3", "Sí"), ("n2", "n4", "No"),
                   ("n3", "n4", ""), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, g)["features"] if x["feature"] == "raise-control-flow")
        self.assertEqual(feature["status"], "FAIL")

    def test_and_short_circuit_polarity_and_call_order(self):
        source = "def run():\n    return first() and second()\n"
        nodes = [node("n1", "initial"),
                 node("n2", "activity", 2, "first", {"significant_call": True, "call_expression": "first", "call_resolution": "resolved"}),
                 node("n3", "decision", 2, "first?"),
                 node("n4", "activity", 2, "second", {"significant_call": True, "call_expression": "second", "call_resolution": "resolved"}),
                 node("n5", "activity", 2, "return result"), node("n6", "final")]
        good = graph(nodes, [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n4", "Sí"),
                             ("n3", "n5", "No"), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, good)["features"] if x["feature"] == "boolean-short-circuit")
        self.assertEqual(feature["status"], "PASS")
        inverted = graph(nodes, [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n4", "No"),
                                 ("n3", "n5", "Sí"), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, inverted)["features"] if x["feature"] == "boolean-short-circuit")
        self.assertEqual(feature["status"], "FAIL")
        reordered = graph([nodes[0], nodes[3], nodes[2], nodes[1], nodes[4], nodes[5]],
                          [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n4", "Sí"),
                           ("n3", "n5", "No"), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, reordered)["features"] if x["feature"] == "boolean-short-circuit")
        self.assertEqual(feature["status"], "FAIL")

    def test_or_short_circuit_uses_false_edge_for_second_operand(self):
        source = "def run():\n    return first() or second()\n"
        nodes = [node("n1", "initial"),
                 node("n2", "activity", 2, "first", {"significant_call": True, "call_expression": "first", "call_resolution": "resolved"}),
                 node("n3", "decision", 2, "first?"),
                 node("n4", "activity", 2, "second", {"significant_call": True, "call_expression": "second", "call_resolution": "resolved"}),
                 node("n5", "activity", 2, "return result"), node("n6", "final")]
        good = graph(nodes, [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n5", "Sí"),
                             ("n3", "n4", "No"), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, good)["features"] if x["feature"] == "boolean-short-circuit")
        self.assertEqual(feature["status"], "PASS")
        inverted = graph(nodes, [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n5", "No"),
                                 ("n3", "n4", "Sí"), ("n4", "n5", ""), ("n5", "n6", "")])
        feature = next(x for x in self.evaluate(source, inverted)["features"] if x["feature"] == "boolean-short-circuit")
        self.assertEqual(feature["status"], "FAIL")

    def test_conditional_expression_side_effect_is_branch_local(self):
        source = "def run(flag):\n    return effect() if flag else 0\n"
        nodes = [node("n1", "initial"), node("n2", "decision", 2, "flag?"),
                 node("n3", "activity", 2, "effect", {"significant_call": True,
                                                           "call_expression": "effect",
                                                           "call_resolution": "resolved"}),
                 node("n4", "result", 2, "0", {"return_value": 0}), node("n5", "final")]
        good = graph(nodes, [("n1", "n2", ""), ("n2", "n3", "Sí"),
                             ("n2", "n4", "No"), ("n3", "n5", ""), ("n4", "n5", "")])
        feature = next(x for x in self.evaluate(source, good)["features"]
                       if x["feature"] == "conditional-expression-effects")
        self.assertEqual(feature["status"], "PASS")
        bad = graph(nodes, [("n1", "n2", ""), ("n2", "n3", "No"),
                            ("n2", "n4", "Sí"), ("n3", "n5", ""), ("n4", "n5", "")])
        feature = next(x for x in self.evaluate(source, bad)["features"]
                       if x["feature"] == "conditional-expression-effects")
        self.assertEqual(feature["status"], "FAIL")

    def test_with_and_async_with_require_exit_and_dynamic_warning(self):
        sync_source = "def run(manager):\n    with manager:\n        work()\n"
        sync_graph = graph([node("n1", "initial"), node("n2", "activity", 2, "Enter context manager"),
                            node("n3", "activity", 2, "Exit context manager"), node("n4", "final")],
                           [("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n4", "")],
                           ["Context manager suppression may be dynamic"])
        feature = next(x for x in self.evaluate(sync_source, sync_graph)["features"] if x["feature"] == "context-manager")
        self.assertEqual(feature["status"], "REVIEW")
        async_source = "async def run(manager):\n    async with manager:\n        await work()\n"
        feature = next(x for x in self.evaluate(async_source, sync_graph)["features"] if x["feature"] == "context-manager")
        self.assertTrue(feature["evidence"]["async"])

    def test_comprehension_metadata_is_not_a_visible_callsite(self):
        source = "def run(values):\n    return [normalize(x) for x in values]\n"
        g = graph([node("n1", "initial"), node("n2", "activity", 2, "Evaluate comprehension",
                                                {"expression_summary": True, "contained_call_expressions": ["normalize"]}),
                   node("n3", "final")], [("n1", "n2", ""), ("n2", "n3", "")])
        feature = next(x for x in self.evaluate(source, g)["features"] if x["feature"] == "comprehension-calls")
        self.assertEqual(feature["status"], "FAIL")
        report = inspect_graph(g, [{"file": "sample.py", "line": 2,
                                    "source": "return [normalize(x) for x in values]"}], 0)
        self.assertEqual(report["critical_direct"], 0)
        self.assertEqual(report["critical_metadata"], 1)

    def test_call_inventory_distinguishes_resolution_and_expansion(self):
        source = ("class Widget:\n"
                  "    def process(self):\n"
                  "        return True\n"
                  "def run(widget):\n"
                  "    def local():\n"
                  "        return True\n"
                  "    widget.process()\n"
                  "    local()\n")
        g = graph([node("n1", "initial"),
                   node("n2", "activity", 7, "process", {"significant_call": True, "call_expression": "widget.process", "call_resolution": "resolved", "resolved_target": "sample:Widget.process"}),
                   node("n3", "activity", 3, "method body", {}, ["sample:Widget.process"]),
                   node("n4", "activity", 8, "local", {"significant_call": True, "call_expression": "local", "call_resolution": "resolved", "resolved_target": "sample:run.local"}),
                   node("n5", "final")], [("n1", "n2", ""), ("n2", "n4", ""), ("n4", "n5", "")])
        calls = self.evaluate(source, g)["calls"]
        process = next(x for x in calls if x["expression"] == "widget.process")
        local = next(x for x in calls if x["expression"] == "local")
        self.assertEqual(process["resolution"], "resolved")
        self.assertTrue(process["body_expanded"])
        self.assertTrue(local["identified"])

    def test_dynamic_target_is_review_not_pass(self):
        source = "def run(handler):\n    return handler.execute()\n"
        g = graph([node("n1", "initial"),
                   node("n2", "activity", 2, "handler.execute",
                        {"significant_call": True, "call_expression": "handler.execute",
                         "call_resolution": "unresolved", "resolved_target": None,
                         "possible_targets": []}),
                   node("n3", "final")], [("n1", "n2", ""), ("n2", "n3", "")])
        result = self.evaluate(source, g)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["calls"][0]["resolution"], "unresolved")

    def test_exception_groups_are_explicitly_unsupported(self):
        source = "def run():\n    try:\n        work()\n    except* ValueError:\n        recover()\n"
        g = graph([node("n1", "initial"), node("n2", "final")], [("n1", "n2", "")])
        result = self.evaluate(source, g)
        self.assertEqual(result["status"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
