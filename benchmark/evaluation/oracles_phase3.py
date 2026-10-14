"""Independent, source-derived semantic checks for the transversal benchmark.

These checks inspect Python AST rules and graph evidence. They never feed
benchmark expectations into PyFlowMap and never execute fixture code.
"""
from __future__ import annotations

import ast
import builtins
import re
from collections import defaultdict, deque
from pathlib import Path

ORACLE_VERSION = "phase3-match-guard-v1"


def _line_numbers(node: ast.AST) -> set[int]:
    return {n.lineno for n in ast.walk(node) if hasattr(n, "lineno")}


def _locations(node: dict) -> set[int]:
    result = set()
    for location in node.get("locations", []) or []:
        match = re.search(r":(\d+)$", str(location))
        if match:
            result.add(int(match.group(1)))
    return result


def _direct_scope(node: ast.AST):
    """Walk a function body without descending into nested definitions."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield child
        yield from _direct_scope(child)


def _breaks_for_loop(loop: ast.AST) -> list[ast.Break]:
    """Find breaks belonging to this loop, excluding nested scopes/loops."""
    breaks = []
    pending = list(getattr(loop, "body", []))
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Break):
            breaks.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                               ast.For, ast.AsyncFor, ast.While, ast.Lambda)):
            continue
        else:
            pending.extend(ast.iter_child_nodes(node))
    return breaks


def _entry(source: Path, entry: str) -> tuple[ast.AST | None, list[tuple[Path, ast.Module]]]:
    modules = []
    files = sorted(source.rglob("*.py")) if source.is_dir() else [source]
    for path in files:
        try:
            modules.append((path, ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))))
        except (OSError, SyntaxError):
            continue
    qual = entry.split(":", 1)[-1]
    wanted = qual.split(".")[-1]
    for _, module in modules:
        for node in ast.walk(module):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == wanted
                    and (len(qual.split(".")) == 1 or any(
                    isinstance(parent, ast.ClassDef)
                    and parent.name == qual.split(".")[-2]
                    and node in parent.body
                    for parent in ast.walk(module)
                    ))):
                    return node, modules
    return None, modules


def _feature(name: str, status: str, message: str, lines=(), evidence=None) -> dict:
    return {"feature": name, "status": status, "message": message,
            "source_lines": sorted(set(lines)), "evidence": evidence or {}}


def _decision_label(label: str) -> str | None:
    text = label.strip().casefold()
    if text in {"sí", "si", "yes", "true", "verdadero"}:
        return "yes"
    if text in {"no", "false", "falso"}:
        return "no"
    return None


def _pattern_capture_names(pattern: ast.pattern) -> set[str]:
    """Return names bound by a structural pattern without executing it."""
    names: set[str] = set()
    for item in ast.walk(pattern):
        if isinstance(item, (ast.MatchAs, ast.MatchStar)) and item.name:
            names.add(item.name)
        elif isinstance(item, ast.MatchMapping) and item.rest:
            names.add(item.rest)
    return names


def _reachable(seed: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen, queue = set(), deque([seed])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(adjacency.get(current, set()) - seen)
    return seen


def _metadata_strings(value) -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"contained_call_expressions", "possible_targets"} and isinstance(item, list):
                found.extend(map(str, item))
            elif key == "subprocess_calls" and isinstance(item, list):
                found.extend(str(x.get("expression", "")) for x in item if isinstance(x, dict))
            else:
                found.extend(_metadata_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_metadata_strings(item))
    return [x for x in found if x]


def evaluate_semantics(case: dict, source: Path, graph: dict) -> dict:
    """Return PASS/FAIL/REVIEW/UNSUPPORTED from source-derived obligations."""
    entry, modules = _entry(source, case["entry"])
    if entry is None:
        return {"status": "REVIEW", "features": [_feature(
            "entry-resolution", "REVIEW", "Could not identify the requested entry function in source.")]}

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("source") in by_id and edge.get("target") in by_id:
            outgoing[edge["source"]].append(edge)
            adjacency[edge["source"]].add(edge["target"])

    scoped = list(_direct_scope(entry))
    parents = {child: parent for parent in ast.walk(entry) for child in ast.iter_child_nodes(parent)}
    features: list[dict] = []

    if hasattr(ast, "TryStar"):
        for group_try in (n for n in scoped if isinstance(n, ast.TryStar)):
            features.append(_feature("exception-groups", "UNSUPPORTED",
                                     "Exception-group dispatch (except*) has no independent semantic oracle yet.",
                                     [group_try.lineno]))

    # Structural matching: identify pattern selectors and guard expressions by
    # explicit case metadata. A guard is not another case selector.
    for match_node in (n for n in scoped if isinstance(n, ast.Match)):
        missing_cases = []
        uncertain_cases = []
        selectors = {
            node.get("label_metadata", {}).get("match_case_index"): node
            for node in nodes
            if node.get("kind") == "decision"
            and isinstance(node.get("label_metadata", {}).get("match_case_index"), int)
        }
        body_nodes: list[list[dict]] = []
        for case_index, match_case in enumerate(match_node.cases):
            body_lines = set().union(*(_line_numbers(statement) for statement in match_case.body))
            selector = selectors.get(case_index)
            represented_nodes = [node for node in nodes
                                 if _locations(node) & body_lines
                                 and node.get("kind") not in {"initial", "final", "decision"}
                                 and "pattern_capture_case_index" not in node.get("label_metadata", {})]
            body_nodes.append(represented_nodes)
            if selector is None or not represented_nodes:
                missing_cases.append({"case_index": case_index,
                                      "selector_present": selector is not None,
                                      "body_represented": bool(represented_nodes)})

        def edge_targets(node_id: str, polarity: str | None = None) -> list[str]:
            return [edge["target"] for edge in outgoing.get(node_id, [])
                    if polarity is None or _decision_label(edge.get("label", "")) == polarity]

        for case_index, match_case in enumerate(match_node.cases):
            selector = selectors.get(case_index)
            if selector is None:
                continue
            own_body_ids = {node.get("id") for node in body_nodes[case_index]}
            yes_targets = edge_targets(selector["id"], "yes")
            no_targets = edge_targets(selector["id"], "no")
            next_selector = selectors.get(case_index + 1)
            irrefutable = bool(selector.get("label_metadata", {}).get("pattern_irrefutable"))
            if not yes_targets or not any(
                target in _reachable(seed, adjacency) for seed in yes_targets for target in own_body_ids
            ):
                missing_cases.append({"case_index": case_index,
                                      "selection_yes": "pattern success does not reach its own body"})
            if irrefutable:
                if no_targets:
                    missing_cases.append({"case_index": case_index,
                                          "selection_no": "irrefutable pattern has a failure route"})
            elif (case_index + 1 < len(match_node.cases)
                  and (not next_selector or next_selector.get("id") not in no_targets)):
                missing_cases.append({"case_index": case_index,
                                      "selection_no": "pattern failure must continue to the immediately following case"})

            if match_case.guard is None:
                continue
            guard_nodes = [node for node in nodes
                           if node.get("kind") == "decision"
                           and node.get("label_metadata", {}).get("match_guard_case_index") == case_index]
            if not guard_nodes:
                missing_cases.append({"case_index": case_index, "guard": "guard decision is not source-linked"})
                continue
            # Python evaluates a successful pattern's captures before its guard.
            captures = _pattern_capture_names(match_case.pattern)
            capture_nodes = [node for node in nodes
                             if node.get("label_metadata", {}).get("pattern_capture_case_index") == case_index
                             and set(node.get("label_metadata", {}).get("pattern_captures", [])) >= set(captures)]
            if captures and (not capture_nodes or not any(
                guard["id"] in _reachable(capture["id"], adjacency)
                for capture in capture_nodes for guard in guard_nodes
            )):
                missing_cases.append({"case_index": case_index,
                                      "capture_order": "pattern captures must be bound before guard evaluation"})
            # Guard truth enters this case body; guard false skips it and moves
            # forward to the next case (or leaves the match on the final arm).
            compound_guard = any(isinstance(item, ast.BoolOp) for item in ast.walk(match_case.guard))
            if compound_guard:
                # The current graph metadata identifies each short-circuit
                # decision, but does not identify which edges are internal to
                # the Boolean expression versus its final false outcome.
                # Avoid a false PASS/FAIL until that distinction is explicit.
                uncertain_cases.append({"case_index": case_index,
                                        "guard": "compound short-circuit outcome needs path-level review"})
                continue
            for guard in guard_nodes:
                yes = edge_targets(guard["id"], "yes")
                no = edge_targets(guard["id"], "no")
                if not yes or not any(
                    body_id in _reachable(seed, adjacency)
                    for seed in yes for body_id in own_body_ids
                ):
                    missing_cases.append({"case_index": case_index,
                                          "guard_yes": "true guard outcome does not reach its case body"})
                if (case_index + 1 < len(match_node.cases)
                        and (not next_selector or next_selector.get("id") not in no)):
                    missing_cases.append({"case_index": case_index,
                                          "guard_no": "false guard outcome must continue to the next case"})
            # A case may only flow forward to later cases. This direct-edge
            # check catches accidental retry of an earlier pattern without
            # confusing a surrounding loop's legitimate next iteration.
            for source_node in [selector, *guard_nodes]:
                for edge in outgoing.get(source_node["id"], []):
                    target_index = by_id.get(edge.get("target"), {}).get("label_metadata", {}).get("match_case_index")
                    if isinstance(target_index, int) and target_index < case_index:
                        missing_cases.append({"case_index": case_index,
                                              "backtrack": f"edge returns to earlier case {target_index}"})

        match_status = "FAIL" if missing_cases else "REVIEW" if uncertain_cases else "PASS"
        features.append(_feature(
            "match-case", match_status,
            "Pattern alternatives, guard polarity, capture order and forward selection must follow Python semantics." if missing_cases
            else "Compound guard path needs manual review." if uncertain_cases
            else "Pattern alternatives, guards and capture order follow Python's ordered selection.",
            [match_node.lineno], {"alternatives": len(match_node.cases), "missing": missing_cases,
                                  "uncertain": uncertain_cases}))

    # A for-else body runs only after normal iterator exhaustion, never after break.
    for loop in (n for n in scoped if isinstance(n, (ast.For, ast.AsyncFor)) and n.orelse):
        else_lines = set().union(*(_line_numbers(statement) for statement in loop.orelse))
        represented = [n for n in nodes if _locations(n) & else_lines]
        loop_decisions = [n for n in nodes if n.get("kind") == "decision" and loop.lineno in _locations(n)]
        break_nodes_ast = _breaks_for_loop(loop)
        has_break = bool(break_nodes_ast)
        break_lines = {n.lineno for n in break_nodes_ast}
        break_nodes = [n for n in nodes if _locations(n) & break_lines]
        separated = False
        for decision in loop_decisions:
            branch_targets = { _decision_label(e.get("label", "")): e["target"]
                               for e in outgoing.get(decision.get("id"), [])
                               if _decision_label(e.get("label", "")) }
            if "no" in branch_targets and any(
                target in _reachable(branch_targets["no"], adjacency)
                for target in (n.get("id") for n in represented)
            ) and (not has_break or all(
                not any(target in _reachable(break_node["id"], adjacency)
                        for target in (n.get("id") for n in represented))
                for break_node in break_nodes
            )) and (not has_break or bool(break_nodes)):
                separated = True
        status = "PASS" if represented and separated and (not has_break or len(loop_decisions) >= 1) else "FAIL"
        features.append(_feature(
            "for-else", status,
            "Normal exhaustion must enter else; break must bypass else." if status == "FAIL"
            else "The else body is source-linked from the normal-exhaustion route.",
            [loop.lineno, *else_lines], {"has_break": has_break,
                                         "else_lines_missing_from_graph": sorted(else_lines - set().union(*(_locations(n) for n in represented))) if represented else sorted(else_lines),
                                         "else_reachable_on_exhaustion": separated,
                                         "break_source_lines": sorted(break_lines),
                                         "break_nodes_present": bool(break_nodes)}))

    # Distinct literal return values are independently checkable and must remain distinct.
    returns = [n for n in scoped if isinstance(n, ast.Return) and n.value is not None]
    literal_returns = []
    for node in returns:
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        literal_returns.append((node, value))
    distinct = {json_key(value) for _, value in literal_returns}
    if len(distinct) > 1:
        missing = []
        for statement, value in literal_returns:
            match = any(
                node.get("kind") == "result" and statement.lineno in _locations(node)
                and node.get("label_metadata", {}).get("return_value", object()) == value
                for node in nodes
            )
            if not match:
                missing.append({"line": statement.lineno, "value": repr(value)})
        features.append(_feature(
            "return-values", "FAIL" if missing else "PASS",
            "Each distinct literal return value needs its own source-linked result." if missing
            else "Distinct literal return values have source-linked results.",
            [n.lineno for n, _ in literal_returns], {"distinct_values": len(distinct), "missing": missing}))

    # A raise must terminate its normal branch; finally statements are allowed on its path.
    raises = [n for n in scoped if isinstance(n, ast.Raise)]
    for raise_node in raises:
        cleanup_lines: set[int] = set()
        parent = parents.get(raise_node)
        while parent is not None:
            if isinstance(parent, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                for statement in parent.finalbody:
                    cleanup_lines.update(_line_numbers(statement))
            parent = parents.get(parent)
        candidates = [n for n in nodes if raise_node.lineno in _locations(n)]
        throw_nodes = [n for n in candidates if any(token in str(n.get("label", "")).casefold()
                                                    for token in ("raise", "lanzar", "throw"))]
        if not throw_nodes:
            features.append(_feature("raise-control-flow", "FAIL",
                                     "The raise has no explicit source-linked termination activity.",
                                     [raise_node.lineno]))
            continue
        leaks = []
        for throw in throw_nodes:
            reachable = _reachable(throw["id"], adjacency)
            for node_id in reachable:
                target = by_id[node_id]
                later_lines = _locations(target) - {raise_node.lineno} - cleanup_lines
                if later_lines and target.get("kind") not in {"final"}:
                    leaks.extend(sorted(later_lines))
        status = "FAIL" if leaks else "PASS"
        features.append(_feature("raise-control-flow", status,
                                 "A raised branch must not continue into later normal statements." if leaks
                                 else "Raise is represented as terminating the normal branch.",
                                 [raise_node.lineno], {"leaked_source_lines": sorted(set(leaks))}))

    # Boolean operators must retain source order and conditional evaluation.
    bool_nodes = [n for n in scoped if isinstance(n, ast.BoolOp)]
    for bool_node in bool_nodes:
        calls = [n for n in ast.walk(bool_node) if isinstance(n, ast.Call)]
        call_names = [ast.unparse(call.func) for call in calls]
        line = bool_node.lineno
        direct_calls = [n for n in nodes if n.get("label_metadata", {}).get("significant_call")
                        and line in _locations(n)]
        direct_names = [str(n.get("label_metadata", {}).get("call_expression", ""))
                        for n in direct_calls]
        decisions = [n for n in nodes if n.get("kind") == "decision" and line in _locations(n)]
        order_ok = all(name in direct_names for name in call_names) and [
            direct_names.index(name) for name in call_names if name in direct_names
        ] == sorted(direct_names.index(name) for name in call_names if name in direct_names)
        conditional_ok = len(decisions) >= 1
        # For short-circuit operands that contain calls, check the required polarity.
        for index in range(len(bool_node.values) - 1):
            left_calls = [n for n in ast.walk(bool_node.values[index]) if isinstance(n, ast.Call)]
            right_calls = [n for n in ast.walk(bool_node.values[index + 1]) if isinstance(n, ast.Call)]
            if not right_calls:
                if index == 0 and len(decisions) > 1:
                    decision = decisions[0]
                    next_decision = decisions[1]
                    targets = {_decision_label(e.get("label", "")): e["target"]
                               for e in outgoing.get(decision["id"], [])
                               if _decision_label(e.get("label", ""))}
                    expected = "yes" if isinstance(bool_node.op, ast.And) else "no"
                    unexpected = "no" if expected == "yes" else "yes"
                    if (expected not in targets or unexpected not in targets
                            or next_decision["id"] not in _reachable(targets[expected], adjacency)
                            or next_decision["id"] in _reachable(targets[unexpected], adjacency)):
                        conditional_ok = False
                continue
            right_name = ast.unparse(right_calls[0].func)
            right_graph = next((n for n in direct_calls if n.get("label_metadata", {}).get("call_expression") == right_name), None)
            if left_calls:
                left_name = ast.unparse(left_calls[0].func)
                left_graph = next((n for n in direct_calls if n.get("label_metadata", {}).get("call_expression") == left_name), None)
                decision = next((n for n in decisions if n["id"] in _reachable(left_graph["id"], adjacency)), None) if left_graph else None
            else:
                decision = decisions[index] if index < len(decisions) else None
            if not right_graph or not decision:
                conditional_ok = False
                continue
            targets = {_decision_label(e.get("label", "")): e["target"] for e in outgoing.get(decision["id"], [])
                       if _decision_label(e.get("label", ""))}
            expected = "yes" if isinstance(bool_node.op, ast.And) else "no"
            unexpected = "no" if expected == "yes" else "yes"
            if expected not in targets or unexpected not in targets or right_graph["id"] not in _reachable(targets[expected], adjacency) or right_graph["id"] in _reachable(targets[unexpected], adjacency):
                conditional_ok = False
        ok = order_ok and conditional_ok
        features.append(_feature("boolean-short-circuit", "PASS" if ok else "FAIL",
                                 "Boolean operands must be ordered and short-circuit paths must preserve Python polarity." if not ok
                                 else "Call order and observable short-circuit route match Python evaluation order.",
                                 [line], {"operator": "and" if isinstance(bool_node.op, ast.And) else "or",
                                          "source_call_order": call_names, "graph_call_order": direct_names,
                                          "decisions_on_line": len(decisions)}))

    # Conditional expressions may call a side-effecting operation on only one branch.
    for conditional in (n for n in scoped if isinstance(n, ast.IfExp)):
        body_calls = [n for n in ast.walk(conditional.body) if isinstance(n, ast.Call)]
        else_calls = [n for n in ast.walk(conditional.orelse) if isinstance(n, ast.Call)]
        if not body_calls and not else_calls:
            continue
        line = conditional.lineno
        decisions = [n for n in nodes if n.get("kind") == "decision" and line in _locations(n)]
        direct_calls = [n for n in nodes if n.get("label_metadata", {}).get("significant_call")
                        and line in _locations(n)]
        polarity_ok = bool(decisions)
        if decisions:
            decision = decisions[0]
            targets = {_decision_label(e.get("label", "")): e["target"] for e in outgoing.get(decision["id"], [])
                       if _decision_label(e.get("label", ""))}
            for branch, expected in ((body_calls, "yes"), (else_calls, "no")):
                if not branch:
                    continue
                call_name = ast.unparse(branch[0].func)
                call_node = next((n for n in direct_calls
                                  if n.get("label_metadata", {}).get("call_expression") == call_name), None)
                opposite = "no" if expected == "yes" else "yes"
                if (not call_node or expected not in targets or opposite not in targets
                        or call_node["id"] not in _reachable(targets[expected], adjacency)
                        or call_node["id"] in _reachable(targets[opposite], adjacency)):
                    polarity_ok = False
        features.append(_feature("conditional-expression-effects", "PASS" if polarity_ok else "FAIL",
                                 "Calls in conditional expressions must execute only on their selected branch." if not polarity_ok
                                 else "Side-effecting call is restricted to its conditional branch.",
                                 [line], {"body_calls": [ast.unparse(n.func) for n in body_calls],
                                          "else_calls": [ast.unparse(n.func) for n in else_calls]}))

    # Calls nested in comprehensions are not visible merely because a summary has the same line.
    for comp in (n for n in scoped if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))):
        contained = [n for n in ast.walk(comp) if isinstance(n, ast.Call)]
        hidden, missing = [], []
        for call in contained:
            expression = ast.unparse(call.func)
            visible = any(node.get("label_metadata", {}).get("significant_call")
                          and call.lineno in _locations(node)
                          and node.get("label_metadata", {}).get("call_expression") == expression
                          for node in nodes)
            if visible:
                continue
            metadata_only = any(expression in _metadata_strings(node.get("label_metadata", {}))
                                for node in nodes)
            (hidden if metadata_only else missing).append(expression)
        if contained:
            ok = not hidden and not missing
            features.append(_feature("comprehension-calls", "PASS" if ok else "FAIL",
                                     "Calls inside comprehensions must be visible activities; metadata-only occurrences do not count." if not ok
                                     else "Comprehension calls have visible call activities.",
                                     [comp.lineno], {"metadata_only": hidden, "missing": missing,
                                                     "source_calls": [ast.unparse(n.func) for n in contained]}))

    # Context managers need visible entry/body/exit. Unknown __exit__ behavior requires REVIEW.
    with_nodes = [n for n in scoped if isinstance(n, (ast.With, ast.AsyncWith))]
    for with_node in with_nodes:
        line = with_node.lineno
        located = [str(n.get("label", "")).casefold() for n in nodes if line in _locations(n)]
        entry_seen = any(("entrar" in label or "enter" in label or "entrada" in label)
                         and ("contexto" in label or "context" in label) for label in located)
        exit_seen = any(("salir" in label or "exit" in label or "salida" in label)
                        and ("contexto" in label or "context" in label) for label in located)
        context_expr = with_node.items[0].context_expr
        cls_name = context_expr.func.id if isinstance(context_expr, ast.Call) and isinstance(context_expr.func, ast.Name) else None
        exit_method = None
        exit_name = "__aexit__" if isinstance(with_node, ast.AsyncWith) else "__exit__"
        for _, module in modules:
            for cls in (n for n in module.body if isinstance(n, ast.ClassDef) and n.name == cls_name):
                exit_method = next((n for n in cls.body
                                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                    and n.name == exit_name), None)
        known_non_suppressing = bool(exit_method and any(
            isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) and n.value.value is False
            for n in ast.walk(exit_method)
        ))
        warning = any(any(word in str(w).casefold() for word in ("context manager", "context manager", "__exit__", "suppression"))
                       for w in graph.get("warnings", []))
        if not entry_seen or not exit_seen:
            status = "FAIL"
        elif not known_non_suppressing and not warning:
            status = "REVIEW"
        elif graph.get("warnings"):
            status = "REVIEW" if warning else "PASS"
        else:
            status = "PASS"
        features.append(_feature("context-manager", status,
                                 "Context manager entry and exit must be shown; dynamic suppression must remain a review item." if status != "PASS"
                                 else "Context manager entry/exit are shown and suppression behavior is known.",
                                 [line], {"async": isinstance(with_node, ast.AsyncWith), "entry_visible": entry_seen,
                                          "exit_visible": exit_seen, "statically_non_suppressing": known_non_suppressing,
                                          "suppression_warning": warning}))

    # Every statically identifiable call site is classified separately from expansion.
    # Include nested definitions here: nested call sites are relevant to the
    # visibility/resolution/expansion inventory even though their flow is not
    # merged into the enclosing function's direct control-flow obligations.
    calls = [n for n in ast.walk(entry) if isinstance(n, ast.Call)]
    call_classifications = []
    for call in calls:
        line, expr = call.lineno, ast.unparse(call.func)
        candidates = [n for n in nodes if line in _locations(n)
                      and n.get("label_metadata", {}).get("call_expression") == expr]
        metadata_only = any(expr in _metadata_strings(n.get("label_metadata", {})) for n in nodes)
        if not candidates:
            resolution = "metadata-only" if metadata_only else "unresolved"
            target = None
            expanded = False
        else:
            meta = candidates[0].get("label_metadata", {})
            resolution = meta.get("call_resolution", "identified")
            target = meta.get("resolved_target") or (meta.get("possible_targets") or [None])[0]
            target_function = _target_function(modules, target) if target else None
            target_lines = set().union(*(_line_numbers(statement) for statement in target_function.body)) if target_function else set()
            expanded = bool(target and target != case["entry"] and any(
                target in (node.get("symbols") or []) and bool(_locations(node) & target_lines)
                for node in nodes
            ))
        call_classifications.append({"line": line, "expression": expr,
                                     "identified": bool(candidates) or metadata_only,
                                     "resolution": resolution, "target": target,
                                     "body_expanded": expanded})
        if metadata_only and not candidates:
            features.append(_feature("call-visibility", "REVIEW",
                                     "Call site occurs only in nested metadata, not as a visible call activity.",
                                     [line], {"call": expr}))
        elif candidates and resolution in {"unresolved", "possible"} and expr.split(".")[-1] not in vars(builtins):
            features.append(_feature("call-target", "REVIEW",
                                     "Call target is unresolved or has multiple possible targets; retain it as uncertainty.",
                                     [line], {"call": expr, "resolution": resolution}))
        elif target and target_function and not expanded and _has_control_flow(target_function):
            features.append(_feature("callee-expansion", "REVIEW",
                                     "A resolved local target contains control flow that is not expanded in the graph.",
                                     [line], {"call": expr, "target": target,
                                              "target_body_lines": sorted(target_lines)}))

    if graph.get("warnings"):
        features.append(_feature("analyzer-uncertainty", "REVIEW",
                                 "The analyzer reported approximation or truncation warnings.",
                                 evidence={"warnings": list(graph["warnings"])}))

    statuses = [f["status"] for f in features]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "UNSUPPORTED" in statuses:
        overall = "UNSUPPORTED"
    elif "REVIEW" in statuses:
        overall = "REVIEW"
    else:
        overall = "PASS"
    return {"status": overall, "features": features, "calls": call_classifications}


def json_key(value) -> str:
    """Stable equality key for literal Python values in return expressions."""
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _target_function(modules, target):
    if not target or ":" not in target:
        return None
    qual = target.split(":", 1)[1].split(".")
    wanted = qual[-1]
    wanted_parent = qual[-2] if len(qual) > 1 else None
    for _, module in modules:
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != wanted:
                continue
            if wanted_parent is None or any(
                isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and parent.name == wanted_parent and node in parent.body
                for parent in ast.walk(module)
            ):
                return node
    return None


def _has_control_flow(function):
    flow_types = (ast.If, ast.Match, ast.For, ast.AsyncFor, ast.While,
                  ast.Try, ast.With, ast.AsyncWith, ast.Raise)
    return any(isinstance(node, flow_types) for node in _direct_scope(function))
