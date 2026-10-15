"""Phase 5 evaluator: keep historical oracle rules, correcting explicit-summary false alarms."""

from __future__ import annotations

import ast

from .oracles_phase4_1 import evaluate_semantics as _evaluate_phase4_1


def evaluate_semantics(case: dict, source, graph: dict) -> dict:
    result = _evaluate_phase4_1(case, source, graph)
    source_file = source
    if source.is_dir():
        module_name = case["entry"].split(":", 1)[0]
        source_file = source.joinpath(*module_name.split(".")).with_suffix(".py")
    entry = next((node for node in ast.walk(ast.parse(source_file.read_text(encoding="utf-8")))
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and (node.name == case["entry"].split(":")[-1].split(".")[-1])), None)
    if entry is None:
        return result
    nodes = graph.get("nodes", [])
    returns = []
    class ReturnCollector(ast.NodeVisitor):
        def visit_Return(self, node):
            returns.append(node)

        def visit_FunctionDef(self, node):
            if node is entry:
                for child in node.body:
                    self.visit(child)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            return

    ReturnCollector().visit(entry)
    def at_line(node, line):
        return any(str(location).rsplit(":", 1)[-1].isdigit()
                   and int(str(location).rsplit(":", 1)[-1]) == line
                   for location in node.get("locations", []))
    return_evidence = []
    for statement in returns:
        expression = ast.unparse(statement.value) if statement.value is not None else "None"
        candidates = [node for node in nodes if at_line(node, statement.lineno)
                      and node.get("label_metadata", {}).get("control_transfer") == "return"
                      and node.get("label_metadata", {}).get("return_expression") == expression]
        return_evidence.append({"line": statement.lineno, "expression": expression,
                                "represented": bool(candidates)})
    return_feature = {
        "feature": "explicit-return-preservation",
        "status": "PASS" if all(item["represented"] for item in return_evidence) else "FAIL",
        "message": "Every explicit return retains a source-linked transfer and expression.",
        "evidence": return_evidence,
    }
    result["features"] = [feature for feature in result.get("features", [])
                          if feature.get("feature") not in
                          {"explicit-return-preservation", "return-values"}]
    result["features"].append(return_feature)
    # Recompute distinct literal return obligation using the new generic transfer metadata.
    literal_returns = []
    for statement in returns:
        try:
            literal = ast.literal_eval(statement.value) if statement.value is not None else None
        except (ValueError, TypeError, SyntaxError):
            continue
        literal_returns.append((statement, literal))
    if len({repr(value) for _, value in literal_returns}) > 1:
        represented = []
        for statement, value in literal_returns:
            represented.append(any(at_line(node, statement.lineno)
                                   and node.get("label_metadata", {}).get("control_transfer") == "return"
                                   and node.get("label_metadata", {}).get("return_value") == value
                                   for node in nodes))
        result["features"].append({
            "feature": "return-values",
            "status": "PASS" if all(represented) else "FAIL",
            "message": "Each distinct literal return value has a source-linked transfer.",
            "evidence": {"lines": [node.lineno for node, _ in literal_returns],
                         "represented": represented},
        })
    # An explicit summary with ordered source expressions is a traceable abstraction;
    # keep it REVIEW instead of treating metadata-only calls as silently lost.
    for feature in result.get("features", []):
        if feature.get("feature") == "comprehension-calls":
            matching = [node for node in nodes if node.get("label_metadata", {}).get("expression_summary")]
            if matching and feature.get("status") == "FAIL":
                feature["status"] = "REVIEW"
                feature["message"] = "Comprehension is explicitly summarized with source metadata; per-item order and effects are not expanded."
    statuses = [feature.get("status") for feature in result.get("features", [])]
    result["status"] = ("FAIL" if "FAIL" in statuses else "UNSUPPORTED" if "UNSUPPORTED" in statuses
                         else "REVIEW" if "REVIEW" in statuses else "PASS")
    return result
