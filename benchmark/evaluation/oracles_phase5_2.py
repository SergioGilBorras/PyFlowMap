"""Phase 5.2 evaluator: distinguish exceptional dispatch from normal flow.

This version keeps prior criteria intact and corrects only the interpretation
of successors from explicit ``raise`` statements. A handler edge is accepted
only when the source raise is inside the corresponding try body and the target
is located at that try's handler or cleanup suite.
"""
from __future__ import annotations

import ast
from collections import defaultdict

from .oracles_phase5 import evaluate_semantics as _evaluate_phase5


def _lines(node: ast.AST) -> set[int]:
    return {item.lineno for item in ast.walk(node) if hasattr(item, "lineno")}


def _locations(node: dict) -> set[int]:
    found = set()
    for location in node.get("locations", []) or []:
        try:
            found.add(int(str(location).rsplit(":", 1)[-1]))
        except ValueError:
            continue
    return found


def _scope_nodes(function: ast.AST):
    for child in ast.iter_child_nodes(function):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield child
        yield from _scope_nodes(child)


def _raise_routes(statement: ast.Raise, parents: dict[ast.AST, ast.AST]
                  ) -> tuple[set[int], dict[int, set[str]]]:
    """Return legal handler/cleanup lines and try-dispatch signatures."""
    allowed: set[int] = set()
    dispatch: dict[int, set[str]] = {}
    child: ast.AST = statement
    parent = parents.get(child)
    while parent is not None:
        if isinstance(parent, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            body_lines = set().union(*(_lines(item) for item in parent.body)) if parent.body else set()
            if statement.lineno in body_lines:
                # Some graph builders locate a shared dispatch node on the
                # try line. Accept that location only when its handler metadata
                # agrees with this lexical try statement.
                dispatch[parent.lineno] = {
                    ast.unparse(handler.type).casefold()
                    for handler in parent.handlers if handler.type is not None
                }
                for handler in parent.handlers:
                    allowed.add(handler.lineno)
                    for item in handler.body:
                        allowed.update(_lines(item))
            for item in parent.finalbody:
                allowed.update(_lines(item))
        child, parent = parent, parents.get(parent)
    return allowed, dispatch


def _exception_successor_allowed(target: dict, allowed_lines: set[int],
                                 dispatch_lines: dict[int, set[str]]) -> bool:
    metadata = target.get("label_metadata", {}) or {}
    label = str(target.get("label", "")).casefold()
    route = metadata.get("exception_route")
    locations = _locations(target)
    handler_meta = metadata.get("exception_handlers") or []
    if isinstance(handler_meta, str):
        handler_meta = [handler_meta]
    handler_names = {str(item).casefold() for item in handler_meta}
    shared_dispatch = any(
        line in locations and expected and handler_names
        and handler_names <= expected
        for line, expected in dispatch_lines.items()
    )
    return bool(
        target.get("kind") == "final"
        or (locations & allowed_lines)
        or shared_dispatch
        or (route == "propagated" and any(
            word in label for word in ("unhandled", "propagate", "propagar", "propagada")
        ))
        or metadata.get("exception_propagation")
        or "propagar excepción" in label
        or "propagate exception" in label
        or metadata.get("context_manager_phase") == "exit"
        or metadata.get("return_after_context_exit")
    )


def _raise_violations(function: ast.AST, graph: dict) -> list[dict]:
    by_id = {node.get("id"): node for node in graph.get("nodes", [])
             if isinstance(node, dict)}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("source") in by_id and edge.get("target") in by_id:
            outgoing[edge["source"]].append(edge)
    parents = {child: parent for parent in ast.walk(function)
               for child in ast.iter_child_nodes(parent)}
    violations = []
    for statement in (node for node in _scope_nodes(function) if isinstance(node, ast.Raise)):
        source_nodes = [node for node in by_id.values()
                        if statement.lineno in _locations(node)
                        and ((node.get("label_metadata", {}) or {}).get("control_transfer") == "raise"
                             or any(word in str(node.get("label", "")).casefold()
                                    for word in ("raise", "lanzar", "throw")))]
        allowed_lines, dispatch_lines = _raise_routes(statement, parents)
        for source in source_nodes:
            for edge in outgoing.get(source["id"], []):
                target = by_id[edge["target"]]
                if not _exception_successor_allowed(target, allowed_lines, dispatch_lines):
                    violations.append({"line": statement.lineno,
                                       "source_node": source["id"],
                                       "successor": target.get("id"),
                                       "successor_label": target.get("label", ""),
                                       "edge_label": edge.get("label", "")})
    return violations


def evaluate_semantics(case: dict, source, graph: dict) -> dict:
    result = _evaluate_phase5(case, source, graph)
    entry_name = case["entry"].split(":", 1)[-1].split(".")[-1]
    if source.is_dir():
        module = case["entry"].split(":", 1)[0]
        source_file = source.joinpath(*module.split(".")).with_suffix(".py")
    else:
        source_file = source
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError):
        return result
    matches = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == entry_name]
    if len(matches) != 1:
        return result
    entry = matches[0]
    violations = _raise_violations(entry, graph)

    # Replace the earlier reachability heuristic: an exceptional edge into a
    # lexically enclosing handler/cleanup is legal, while a direct ordinary
    # edge into unrelated subsequent work remains a semantic failure.
    prior_terminal = [feature for feature in result.get("features", [])
                      if feature.get("feature") == "terminal-successors"]
    result["features"] = [feature for feature in result.get("features", [])
                          if feature.get("feature") not in {"raise-control-flow", "terminal-successors"}]

    raises = [node for node in _scope_nodes(entry) if isinstance(node, ast.Raise)]
    missing = []
    for statement in raises:
        represented = any(statement.lineno in _locations(node)
                          and ((node.get("label_metadata", {}) or {}).get("control_transfer") == "raise"
                               or any(word in str(node.get("label", "")).casefold()
                                      for word in ("raise", "lanzar", "throw")))
                          for node in graph.get("nodes", []))
        if not represented:
            missing.append(statement.lineno)
    if raises:
        result["features"].append({
            "feature": "raise-control-flow",
            "status": "FAIL" if missing or violations else "PASS",
            "message": ("Explicit raise must terminate normal flow; only enclosing exception handlers and cleanup may follow it."
                        if missing or violations else
                        "Raise successors are limited to enclosing exceptional dispatch, cleanup, or propagation."),
            "source_lines": sorted({node.lineno for node in raises}),
            "evidence": {"missing_raise_nodes": missing, "invalid_successors": violations},
        })

    # Keep return-terminal checks from the previous evaluator, but remove its
    # false positive for raise-to-handler edges.
    for feature in prior_terminal:
        bad = feature.get("evidence", {}).get("violations", [])
        # The old check did not carry edge labels; only retain return violations.
        return_lines = {node.lineno for node in _scope_nodes(entry) if isinstance(node, ast.Return)}
        filtered = [item for item in bad if item.get("line") in return_lines]
        if filtered:
            feature["status"] = "FAIL"
            feature["evidence"]["violations"] = filtered
            result["features"].append(feature)

    # except* structure is partly statically checkable, but subgroup splitting
    # and residual-group behavior depend on runtime exception types.
    if hasattr(ast, "TryStar"):
        for feature in result.get("features", []):
            if feature.get("feature") == "exception-groups" and feature.get("status") == "UNSUPPORTED":
                feature["status"] = "REVIEW"
                feature["message"] = ("The raise-before-dispatch ordering is checked; subgroup distribution and "
                                       "residual-group behavior remain runtime-dependent.")

    statuses = [feature.get("status") for feature in result.get("features", [])]
    result["status"] = ("FAIL" if "FAIL" in statuses else "UNSUPPORTED" if "UNSUPPORTED" in statuses
                        else "REVIEW" if "REVIEW" in statuses else "PASS")
    return result
