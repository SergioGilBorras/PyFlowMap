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

ORACLE_VERSION = "phase4.1-match-path-oracle-v1"


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


def _following_statement(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.stmt | None:
    parent = parents.get(node)
    if parent is None:
        return None
    for field in ("body", "orelse", "finalbody"):
        siblings = getattr(parent, field, None)
        if isinstance(siblings, list) and node in siblings:
            position = siblings.index(node)
            return siblings[position + 1] if position + 1 < len(siblings) else None
    return None


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


def _module_name(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(path.name)
    return ".".join(relative.with_suffix("").parts)


def _definition_path(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[str]:
    names = []
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(current.name)
    names.reverse()
    if hasattr(node, "name"):
        names.append(node.name)
    return names


def _entry(source: Path, entry: str) -> tuple[ast.AST | None, list[tuple[Path, ast.Module]]]:
    modules = []
    files = sorted(source.rglob("*.py")) if source.is_dir() else [source]
    for path in files:
        try:
            modules.append((path, ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))))
        except (OSError, SyntaxError):
            continue
    module_qual, function_qual = entry.split(":", 1) if ":" in entry else ("", entry)
    wanted_path = function_qual.split(".")
    root = source.resolve() if source.is_dir() else source.resolve().parent
    module_matches = [(path, module) for path, module in modules
                      if not module_qual or module_qual in {
                          _module_name(path, root), path.stem, path.name,
                          path.name.removesuffix(".py")
                      }]
    matches = []
    for _, module in module_matches:
        parents = {child: parent for parent in ast.walk(module)
                   for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(module):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and _definition_path(node, parents) == wanted_path):
                matches.append(node)
    if len(matches) == 1:
        return matches[0], modules
    return None, modules


def _feature(name: str, status: str, message: str, lines=(), evidence=None) -> dict:
    return {"feature": name, "status": status, "message": message,
            "source_lines": sorted(set(lines)), "evidence": evidence or {}}


def _decision_label(label: str) -> str | None:
    text = label.strip().casefold()
    if (text in {"s\u00ed", "si", "yes", "true", "verdadero", "s\u00c3\u00ad"}
            or text == "s\ufffd"):
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


def _can_reach_before_boundary(seed: str, goals: set[str], adjacency: dict[str, set[str]],
                               boundary: set[str], blocked: set[str] = frozenset()) -> bool:
    """Search one match execution; do not follow a loop back into that match."""
    if seed in blocked:
        return False
    queue, seen = deque([seed]), set()
    while queue:
        current = queue.popleft()
        if current in seen or current in blocked:
            continue
        if current in goals:
            return True
        if current in boundary:
            continue
        seen.add(current)
        queue.extend(adjacency.get(current, set()) - seen - blocked)
    return False


def _warning_classification(warning: str) -> tuple[str, str]:
    """Classify a warning by its stated consequence, not by its mere presence."""
    text = warning.casefold()
    if any(token in text for token in ("comprehension evaluation summarized",
                                       "except handler dispatch is approximated")):
        return "analysis-approximation", "REVIEW"
    if any(token in text for token in ("data-dependent", "depends on runtime data", "runtime-dependent branch")):
        return "data-dependent-branch", "PASS"
    if any(token in text for token in ("unresolved", "multiple possible", "dynamic dispatch", "ambiguous import")):
        return "dynamic-resolution", "REVIEW"
    if "suppression behavior is dynamic" in text or "context manager exception" in text:
        return "dynamic-runtime-behavior", "REVIEW"
    if any(token in text for token in ("depth boundary", "max depth", "node budget", "expansion limit", "truncated expansion")):
        return "expansion-limit", "REVIEW"
    if any(token in text for token in ("not represented", "omitted activity", "call site occurs only", "not expanded")):
        return "activity-not-represented", "REVIEW"
    if any(token in text for token in ("approximation", "approximated", "summarized", "suppression behavior", "iteration count")):
        return "analysis-approximation", "REVIEW"
    if any(token in text for token in ("skipped oversized", "unparsable file", "unresolved relative import")):
        return "source-coverage", "REVIEW"
    return "informational", "PASS"


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


def _evaluate_phase4(case: dict, source: Path, graph: dict) -> dict:
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

    # Structural matching: each match execution is keyed by its source context,
    # case location, and enclosing entry symbol. Case indices are local only.
    entry_symbol = case["entry"]
    for match_node in (n for n in scoped if isinstance(n, ast.Match)):
        missing_cases = []
        uncertain_cases = []
        selectors: dict[int, dict] = {}
        guards_by_case: dict[int, list[dict]] = defaultdict(list)
        captures_by_case: dict[int, list[dict]] = defaultdict(list)

        def belongs_to_entry(node: dict) -> bool:
            symbols = node.get("symbols") or []
            metadata = node.get("label_metadata", {}) or {}
            return (not symbols or entry_symbol in symbols
                    or metadata.get("caller_symbol") == entry_symbol)

        for case_index, arm in enumerate(match_node.cases):
            arm_line = getattr(arm.pattern, "lineno", match_node.lineno)
            for node in nodes:
                meta = node.get("label_metadata", {}) or {}
                if not belongs_to_entry(node) or arm_line not in _locations(node):
                    continue
                if (node.get("kind") == "decision"
                        and meta.get("match_case_index") == case_index):
                    selectors[case_index] = node
                if (node.get("kind") == "decision"
                        and meta.get("match_guard_case_index") == case_index):
                    guards_by_case[case_index].append(node)
                if (meta.get("pattern_capture_case_index") == case_index):
                    captures_by_case[case_index].append(node)

        match_selector_ids = {node["id"] for node in selectors.values()}
        following = _following_statement(match_node, parents)
        following_lines = _line_numbers(following) if following is not None else set()
        continuation_ids = {node["id"] for node in nodes
                            if belongs_to_entry(node) and _locations(node) & following_lines}

        def edge_list(node_id: str, polarity: str | None = None) -> list[dict]:
            return [edge for edge in outgoing.get(node_id, [])
                    if polarity is None or _decision_label(edge.get("label", "")) == polarity]

        body_nodes: dict[int, list[dict]] = {}
        for case_index, arm in enumerate(match_node.cases):
            body_lines = set().union(*(_line_numbers(statement) for statement in arm.body))
            represented = [node for node in nodes
                           if belongs_to_entry(node) and _locations(node) & body_lines
                           and node.get("kind") not in {"initial", "final", "decision"}
                           and "pattern_capture_case_index" not in (node.get("label_metadata", {}) or {})]
            body_nodes[case_index] = represented
            if case_index not in selectors or not represented:
                missing_cases.append({"case_index": case_index,
                                      "selector_present": case_index in selectors,
                                      "body_represented": bool(represented)})

        for case_index, arm in enumerate(match_node.cases):
            selector = selectors.get(case_index)
            if selector is None:
                continue
            own_ids = {node["id"] for node in body_nodes[case_index]}
            next_selector = selectors.get(case_index + 1)
            irrefutable = bool((selector.get("label_metadata", {}) or {}).get("pattern_irrefutable"))
            yes_edges = edge_list(selector["id"], "yes")
            no_edges = edge_list(selector["id"], "no")
            captures = _pattern_capture_names(arm.pattern)
            capture_nodes = [node for node in captures_by_case[case_index]
                             if set((node.get("label_metadata", {}) or {}).get("pattern_captures", [])) >= captures]
            guard_nodes = guards_by_case[case_index]
            guard_ids = {node["id"] for node in guard_nodes}

            if not yes_edges or not any(
                _can_reach_before_boundary(edge["target"], own_ids, adjacency,
                                           match_selector_ids)
                for edge in yes_edges
            ):
                missing_cases.append({"case_index": case_index,
                                      "selection_yes": "pattern success does not reach its own body"})

            if irrefutable:
                if no_edges:
                    missing_cases.append({"case_index": case_index,
                                          "selection_no": "irrefutable pattern has a failure route"})
            elif case_index + 1 < len(match_node.cases):
                allowed = {next_selector["id"]} if next_selector else set()
                actual = {edge["target"] for edge in no_edges}
                if not no_edges or actual != allowed:
                    missing_cases.append({"case_index": case_index,
                                          "selection_no": "pattern failure must target only the next case selector",
                                          "actual_targets": sorted(actual),
                                          "allowed_targets": sorted(allowed)})
            else:
                wrong = [edge["target"] for edge in no_edges
                         if edge["target"] in match_selector_ids
                         or _can_reach_before_boundary(edge["target"], own_ids, adjacency,
                                                       match_selector_ids)]
                if not no_edges or wrong:
                    missing_cases.append({"case_index": case_index,
                                          "selection_no": "final pattern failure must leave this case and continue after the match",
                                          "invalid_targets": sorted(set(wrong))})
                elif continuation_ids and any(not _can_reach_before_boundary(
                        edge["target"], continuation_ids, adjacency, match_selector_ids)
                        for edge in no_edges):
                    missing_cases.append({"case_index": case_index,
                                          "selection_no": "final pattern failure does not reach the post-match statement"})
                elif not continuation_ids and any(by_id.get(edge["target"], {}).get("kind") != "final"
                                                   for edge in no_edges):
                    uncertain_cases.append({"case_index": case_index,
                                            "selection_no": "post-match continuation is not source-linked"})

            # Every selected route must pass through every required binding
            # event before it can evaluate the guard or enter the case body.
            if captures:
                if not capture_nodes:
                    missing_cases.append({"case_index": case_index,
                                          "capture_order": "required capture activity is missing"})
                else:
                    capture_ids = {node["id"] for node in capture_nodes}
                    milestones = guard_ids or own_ids
                    bypasses = [edge["target"] for edge in yes_edges
                                if any(_can_reach_before_boundary(
                                    edge["target"], {milestone}, adjacency,
                                    match_selector_ids, capture_ids)
                                       for milestone in milestones)]
                    reached_after_capture = any(
                        any(_can_reach_before_boundary(capture_id, {milestone}, adjacency,
                                                       match_selector_ids)
                            for milestone in milestones)
                        for capture_id in capture_ids
                    )
                    if bypasses or not reached_after_capture:
                        missing_cases.append({"case_index": case_index,
                                              "capture_order": "all selected routes must bind captures before guard/body",
                                              "bypass_targets": sorted(set(bypasses))})

            if arm.guard is None:
                continue
            if not guard_nodes:
                missing_cases.append({"case_index": case_index, "guard": "guard decision is not source-linked"})
                continue
            compound_guard = any(isinstance(item, ast.BoolOp) for item in ast.walk(arm.guard))
            if compound_guard:
                uncertain_cases.append({"case_index": case_index,
                                        "guard": "aggregate result of short-circuit evaluation is not fully identified"})
                continue

            for guard in guard_nodes:
                yes = edge_list(guard["id"], "yes")
                no = edge_list(guard["id"], "no")
                if not yes or not any(
                    _can_reach_before_boundary(edge["target"], own_ids, adjacency,
                                               match_selector_ids)
                    for edge in yes
                ):
                    missing_cases.append({"case_index": case_index,
                                          "guard_yes": "true guard outcome does not reach its own body"})
                false_reaches_body = [edge["target"] for edge in no
                                      if _can_reach_before_boundary(
                                          edge["target"], own_ids, adjacency,
                                          match_selector_ids)]
                if false_reaches_body:
                    missing_cases.append({"case_index": case_index,
                                          "guard_no": "false guard outcome reaches its own body",
                                          "targets": sorted(set(false_reaches_body))})
                if case_index + 1 < len(match_node.cases):
                    allowed = {next_selector["id"]} if next_selector else set()
                    actual = {edge["target"] for edge in no}
                    if not no or actual != allowed:
                        missing_cases.append({"case_index": case_index,
                                              "guard_no": "false guard must target only the next case selector",
                                              "actual_targets": sorted(actual),
                                              "allowed_targets": sorted(allowed)})
                else:
                    false_targets = {edge["target"] for edge in no}
                    invalid = {target for target in false_targets
                               if target in match_selector_ids
                               or _can_reach_before_boundary(target, own_ids, adjacency,
                                                             match_selector_ids)}
                    if invalid:
                        missing_cases.append({"case_index": case_index,
                                              "guard_no": "false guard must leave this case and continue after the match",
                                              "invalid_targets": sorted(invalid)})
                    elif continuation_ids and any(not _can_reach_before_boundary(
                            edge["target"], continuation_ids, adjacency, match_selector_ids)
                            for edge in no):
                        missing_cases.append({"case_index": case_index,
                                              "guard_no": "false guard does not reach the post-match statement"})
                    elif not continuation_ids and any(by_id.get(edge["target"], {}).get("kind") != "final"
                                                       for edge in no):
                        uncertain_cases.append({"case_index": case_index,
                                                "guard_no": "post-match continuation is not source-linked"})

        match_status = "FAIL" if missing_cases else "REVIEW" if uncertain_cases else "PASS"
        features.append(_feature(
            "match-case", match_status,
            "Pattern polarity, exclusive destinations and capture ordering must follow Python semantics." if missing_cases
            else "Compound guard aggregate outcome requires review." if uncertain_cases
            else "Pattern selection, captures, guards and forward dispatch follow Python's ordered semantics.",
            [match_node.lineno], {"match_location": match_node.lineno,
                                  "alternatives": len(match_node.cases),
                                  "missing": missing_cases, "uncertain": uncertain_cases}))

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

    warning_groups: dict[str, dict] = {}
    for warning in graph.get("warnings", []):
        category, status = _warning_classification(str(warning))
        group = warning_groups.setdefault(category, {"status": status, "warnings": []})
        if status == "REVIEW":
            group["status"] = "REVIEW"
        group["warnings"].append(str(warning))
    for category, group in warning_groups.items():
        if category == "informational":
            continue
        features.append(_feature(
            f"analyzer-warning:{category}", group["status"],
            "Warnings are classified by whether they imply uncertainty or omitted flow; data-dependent branching alone is informational.",
            evidence={"warnings": group["warnings"], "category": category}))

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

    def normalize(item):
        if item is None or isinstance(item, (bool, int, str)):
            return [type(item).__name__, item]
        if isinstance(item, float):
            return ["float", repr(item)]
        if isinstance(item, complex):
            return ["complex", repr(item.real), repr(item.imag)]
        if isinstance(item, bytes):
            return ["bytes", item.hex()]
        if isinstance(item, tuple):
            return ["tuple", [normalize(part) for part in item]]
        if isinstance(item, list):
            return ["list", [normalize(part) for part in item]]
        if isinstance(item, (set, frozenset)):
            return [type(item).__name__, sorted((normalize(part) for part in item), key=repr)]
        if isinstance(item, dict):
            pairs = [(normalize(key), normalize(val)) for key, val in item.items()]
            return ["dict", sorted(pairs, key=repr)]
        return [type(item).__qualname__, repr(item)]

    return json.dumps(normalize(value), sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))


def _target_function(modules, target):
    if not target or ":" not in target:
        return None
    module_qual, function_qual = target.split(":", 1)
    wanted_path = function_qual.split(".")
    matches = []
    for path, module in modules:
        if module_qual and module_qual not in {path.stem, path.name, path.name.removesuffix(".py")}:
            # A dotted module name must match the suffix of the module path,
            # so same-named functions in sibling modules cannot collide.
            normalized = ".".join(path.with_suffix("").parts)
            if not normalized.endswith(module_qual):
                continue
        parents = {child: parent for parent in ast.walk(module)
                   for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(module):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and _definition_path(node, parents) == wanted_path):
                matches.append(node)
    return matches[0] if len(matches) == 1 else None


def _has_control_flow(function):
    flow_types = (ast.If, ast.Match, ast.For, ast.AsyncFor, ast.While,
                  ast.Try, ast.With, ast.AsyncWith, ast.Raise)
    return any(isinstance(node, flow_types) for node in _direct_scope(function))


def _source_successors_are_terminal(function: ast.AST, graph: dict) -> list[dict]:
    """Find visible terminal return/raise activities with an ordinary successor.

    A return may pass through a finally suite or a context-manager exit before
    reaching the function final node. Other direct successors are evidence of
    an impossible normal continuation.
    """
    nodes = graph.get("nodes", [])
    by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("source") in by_id and edge.get("target") in by_id:
            outgoing[edge["source"]].append(edge)
    parents = {child: parent for parent in ast.walk(function)
               for child in ast.iter_child_nodes(parent)}
    violations = []
    terminals = [n for n in _direct_scope(function) if isinstance(n, (ast.Return, ast.Raise))]
    for statement in terminals:
        source_nodes = []
        for item in nodes:
            if statement.lineno not in _locations(item):
                continue
            meta = item.get("label_metadata", {}) or {}
            label = str(item.get("label", "")).casefold()
            if isinstance(statement, ast.Return):
                if (item.get("kind") == "result" or "return_value" in meta
                        or meta.get("return_after_context_exit")):
                    source_nodes.append(item)
            elif ("raise" in label or "lanzar" in label or "throw" in label
                  or "exception_expression" in meta):
                source_nodes.append(item)
        if not source_nodes:
            continue
        cleanup_lines: set[int] = set()
        parent = parents.get(statement)
        while parent is not None:
            if isinstance(parent, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                for cleanup in parent.finalbody:
                    cleanup_lines.update(_line_numbers(cleanup))
            parent = parents.get(parent)
        for source_node in source_nodes:
            for edge in outgoing.get(source_node.get("id"), []):
                target = by_id[edge["target"]]
                meta = target.get("label_metadata", {}) or {}
                target_lines = _locations(target)
                allowed = target.get("kind") == "final"
                allowed |= bool(meta.get("return_after_context_exit"))
                allowed |= meta.get("context_manager_phase") == "exit"
                allowed |= bool(target_lines & cleanup_lines)
                # A finally suite can contain its own return/raise, which then
                # replaces the pending transfer under Python semantics.
                if not allowed:
                    violations.append({"line": statement.lineno,
                                       "source_node": source_node.get("id"),
                                       "successor": target.get("id"),
                                       "successor_label": target.get("label", "")})
    return violations


def _audit_match_edges(function: ast.AST, entry_symbol: str, graph: dict) -> list[dict]:
    """Check both allowed and forbidden paths within each individual match.

    Searches stop at the current arm's body. This keeps a loop's next execution
    of the same match from being mistaken for a backward dispatch edge.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    outgoing: dict[str, list[dict]] = defaultdict(list)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("source") in by_id and edge.get("target") in by_id:
            outgoing[edge["source"]].append(edge)
            adjacency[edge["source"]].add(edge["target"])

    def belongs(node: dict) -> bool:
        meta = node.get("label_metadata", {}) or {}
        symbols = node.get("symbols") or []
        return not symbols or entry_symbol in symbols or meta.get("caller_symbol") == entry_symbol

    failures = []
    for match in (item for item in _direct_scope(function) if isinstance(item, ast.Match)):
        selectors = {}
        guards: dict[int, list[dict]] = defaultdict(list)
        captures: dict[int, list[dict]] = defaultdict(list)
        for index, arm in enumerate(match.cases):
            line = getattr(arm.pattern, "lineno", match.lineno)
            for node in nodes:
                meta = node.get("label_metadata", {}) or {}
                if not belongs(node) or line not in _locations(node):
                    continue
                if node.get("kind") == "decision" and meta.get("match_case_index") == index:
                    selectors[index] = node
                if node.get("kind") == "decision" and meta.get("match_guard_case_index") == index:
                    guards[index].append(node)
                if meta.get("pattern_capture_case_index") == index:
                    captures[index].append(node)
        all_selector_ids = {n["id"] for n in selectors.values()}
        arm_bodies = {}
        for index, arm in enumerate(match.cases):
            lines = set().union(*(_line_numbers(statement) for statement in arm.body))
            arm_bodies[index] = {n["id"] for n in nodes if belongs(n) and _locations(n) & lines
                                 and n.get("kind") not in {"initial", "final", "decision"}
                                 and "pattern_capture_case_index" not in (n.get("label_metadata", {}) or {})}

        for index, arm in enumerate(match.cases):
            selector = selectors.get(index)
            if selector is None:
                continue
            own_body = arm_bodies[index]
            next_selector = selectors.get(index + 1)
            meta = selector.get("label_metadata", {}) or {}
            irrefutable = bool(meta.get("pattern_irrefutable"))
            for edge in outgoing.get(selector["id"], []):
                polarity = _decision_label(edge.get("label", ""))
                target = edge.get("target")
                if polarity == "yes":
                    for later in range(index + 1, len(match.cases)):
                        forbidden = arm_bodies[later]
                        if _can_reach_before_boundary(target, forbidden, adjacency,
                                                      own_body | all_selector_ids):
                            failures.append({"match_line": match.lineno, "case_index": index,
                                             "rule": "pattern-success-enters-later-case",
                                             "target": target, "later_case": later})
                            break
                    if target in all_selector_ids and target != selector["id"]:
                        failures.append({"match_line": match.lineno, "case_index": index,
                                         "rule": "pattern-success-jumps-to-selector", "target": target})
                elif polarity == "no":
                    if _can_reach_before_boundary(target, own_body, adjacency,
                                                  all_selector_ids - {selector["id"]}):
                        failures.append({"match_line": match.lineno, "case_index": index,
                                         "rule": "pattern-failure-enters-own-body", "target": target})
                    if irrefutable:
                        failures.append({"match_line": match.lineno, "case_index": index,
                                         "rule": "irrefutable-pattern-has-failure-edge", "target": target})
                    elif next_selector and target != next_selector["id"]:
                        failures.append({"match_line": match.lineno, "case_index": index,
                                         "rule": "pattern-failure-wrong-destination", "target": target,
                                         "expected": next_selector["id"]})

            for guard in guards.get(index, []):
                for edge in outgoing.get(guard["id"], []):
                    polarity = _decision_label(edge.get("label", ""))
                    target = edge.get("target")
                    if polarity == "no":
                        if _can_reach_before_boundary(target, own_body, adjacency,
                                                      all_selector_ids - {selector["id"]}):
                            failures.append({"match_line": match.lineno, "case_index": index,
                                             "rule": "false-guard-enters-own-body", "target": target})
                        if next_selector and target != next_selector["id"]:
                            failures.append({"match_line": match.lineno, "case_index": index,
                                             "rule": "false-guard-wrong-destination", "target": target,
                                             "expected": next_selector["id"]})
                    elif polarity == "yes":
                        for later in range(index + 1, len(match.cases)):
                            if _can_reach_before_boundary(target, arm_bodies[later], adjacency,
                                                          own_body | all_selector_ids):
                                failures.append({"match_line": match.lineno, "case_index": index,
                                                 "rule": "true-guard-enters-later-case", "target": target,
                                                 "later_case": later})
                                break

            required = _pattern_capture_names(arm.pattern)
            if required:
                capture_ids = {n["id"] for n in captures.get(index, [])
                               if set((n.get("label_metadata", {}) or {}).get("pattern_captures", [])) >= required}
                guard_ids = {n["id"] for n in guards.get(index, [])}
                milestones = guard_ids or own_body
                for edge in outgoing.get(selector["id"], []):
                    if _decision_label(edge.get("label", "")) != "yes":
                        continue
                    if any(_can_reach_before_boundary(edge["target"], {m}, adjacency,
                                                      all_selector_ids, capture_ids)
                           for m in milestones):
                        failures.append({"match_line": match.lineno, "case_index": index,
                                         "rule": "positive-pattern-bypasses-capture",
                                         "target": edge["target"]})
    return failures


def _context_manager_audit(function: ast.AST, modules, graph: dict) -> list[dict]:
    nodes = graph.get("nodes", [])
    warnings = [str(w).casefold() for w in graph.get("warnings", [])]
    features = []
    with_nodes = [n for n in _direct_scope(function) if isinstance(n, (ast.With, ast.AsyncWith))]
    for stmt in with_nodes:
        line = stmt.lineno
        entries = [n for n in nodes if (n.get("label_metadata", {}) or {}).get("context_manager_phase") == "enter"
                   and line in _locations(n)]
        exits = [n for n in nodes if (n.get("label_metadata", {}) or {}).get("context_manager_phase") == "exit"
                 and line in _locations(n)]
        body_lines = set().union(*(_line_numbers(s) for s in stmt.body)) if stmt.body else set()
        body_nodes = [n for n in nodes if _locations(n) & body_lines
                      and (n.get("label_metadata", {}) or {}).get("context_manager_phase") not in {"enter", "exit"}]

        def executable_lines(statement: ast.AST) -> set[int]:
            lines = set()

            def visit(node: ast.AST, *, root: bool = False) -> None:
                if not root and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                  ast.ClassDef, ast.Lambda)):
                    return
                if isinstance(node, ast.stmt) and not isinstance(node, ast.Pass):
                    lines.add(node.lineno)
                for child in ast.iter_child_nodes(node):
                    visit(child)

            visit(statement, root=True)
            return lines

        required_body_lines = set().union(*(executable_lines(s) for s in stmt.body)) if stmt.body else set()
        represented_body_lines = set().union(*(_locations(n) for n in body_nodes)) if body_nodes else set()
        missing_body_lines = sorted(required_body_lines - represented_body_lines)
        transfers = [n for s in stmt.body for n in ([s, *_direct_scope(s)])
                     if isinstance(n, (ast.Return, ast.Raise, ast.Break, ast.Continue))]
        transfer_kinds = {"return": ast.Return, "raise": ast.Raise,
                          "break": ast.Break, "continue": ast.Continue}
        missing_transfers = []
        for transfer in transfers:
            outcome = next(name for name, cls in transfer_kinds.items() if isinstance(transfer, cls))
            if outcome in {"break", "continue"}:
                visible = any(transfer.lineno in _locations(n)
                              and (n.get("label_metadata", {}) or {}).get("control_transfer") == outcome
                              for n in nodes)
            elif outcome == "return":
                visible = any((n.get("label_metadata", {}) or {}).get("pending_outcome") == "return"
                              and (n.get("label_metadata", {}) or {}).get("context_manager_phase") == "exit"
                              for n in exits)
                visible |= any(transfer.lineno in _locations(n)
                               and (n.get("label_metadata", {}) or {}).get("return_after_context_exit")
                               for n in nodes)
            else:
                visible = any((n.get("label_metadata", {}) or {}).get("pending_outcome") == "raise"
                              and (n.get("label_metadata", {}) or {}).get("context_manager_phase") == "exit"
                              for n in exits)
                visible |= any(transfer.lineno in _locations(n)
                               and ("exception_expression" in (n.get("label_metadata", {}) or {})
                                    or "raise" in str(n.get("label", "")).casefold()
                                    or "lanzar" in str(n.get("label", "")).casefold())
                               for n in nodes)
            if not visible:
                missing_transfers.append({"line": transfer.lineno, "outcome": outcome})
        warning = any("context manager" in w or "suppression" in w for w in warnings)
        possible_suppression = any((n.get("label_metadata", {}) or {}).get("context_manager_suppression")
                                   for n in nodes)
        missing = []
        if len(entries) < len(stmt.items): missing.append("entry")
        if len(exits) < len(stmt.items): missing.append("exit")
        if missing_body_lines: missing.append("body")
        if missing_transfers: missing.append("transfer")
        status = "FAIL" if missing else "REVIEW" if warning or possible_suppression else "PASS"
        features.append(_feature("context-manager", status,
                                 "Entry, body, exits and transfers must be visible; suppression remains uncertain unless proven for every path.",
                                 [line], {"async": isinstance(stmt, ast.AsyncWith),
                                          "entry_count": len(entries), "exit_count": len(exits),
                                          "body_nodes": [n.get("id") for n in body_nodes],
                                          "missing_body_lines": missing_body_lines,
                                          "missing": missing, "missing_transfers": missing_transfers,
                                          "possible_suppression": bool(possible_suppression),
                                          "dynamic_warning": warning}))
    return features


def evaluate_semantics(case: dict, source: Path, graph: dict) -> dict:
    """Phase 4.1 oracle: add adversarial path exclusions and transfer checks."""
    result = _evaluate_phase4(case, source, graph)
    entry, modules = _entry(source, case["entry"])
    if entry is None:
        return result

    entry_symbol = case["entry"]
    invalid_match_edges = _audit_match_edges(entry, entry_symbol, graph)
    match_features = [f for f in result.get("features", []) if f.get("feature") == "match-case"]
    if invalid_match_edges:
        if match_features:
            for feature in match_features:
                feature["status"] = "FAIL"
                feature.setdefault("evidence", {}).setdefault("phase4_1_invalid_routes", []).extend(invalid_match_edges)
        else:
            result.setdefault("features", []).append(_feature(
                "match-case-path-exclusion", "FAIL",
                "A positive or negative match outcome has a forbidden successor.",
                evidence={"invalid_routes": invalid_match_edges}))

    # Every explicit return needs a source-linked result or an explicit return
    # after a context exit. A visible expression alone is not a return event.
    nodes = graph.get("nodes", [])
    returns = [n for n in _direct_scope(entry) if isinstance(n, ast.Return)]
    missing_returns = []
    ambiguous_returns = []
    for statement in returns:
        candidates = [n for n in nodes if statement.lineno in _locations(n)]
        explicit = [n for n in candidates if n.get("kind") == "result"
                    or (n.get("label_metadata", {}) or {}).get("return_after_context_exit")]
        if not explicit:
            if candidates:
                ambiguous_returns.append({"line": statement.lineno,
                                          "nodes": [n.get("id") for n in candidates]})
            else:
                missing_returns.append(statement.lineno)
    if missing_returns or ambiguous_returns:
        result.setdefault("features", []).append(_feature(
            "explicit-return-preservation", "FAIL" if missing_returns else "REVIEW",
            "Each explicit return must be a source-linked result or return transfer; an expression activity alone is insufficient.",
            [n.lineno for n in returns], {"missing_lines": missing_returns,
                                         "ambiguous_lines": ambiguous_returns,
                                         "explicit_return_count": len(returns)}))
    else:
        result.setdefault("features", []).append(_feature(
            "explicit-return-preservation", "PASS",
            "Every explicit return has a source-linked result or post-exit transfer.",
            [n.lineno for n in returns], {"explicit_return_count": len(returns)}))

    terminal_violations = _source_successors_are_terminal(entry, graph)
    if terminal_violations:
        result.setdefault("features", []).append(_feature(
            "terminal-successors", "FAIL",
            "A visible return or raise activity has an impossible ordinary successor.",
            sorted({item["line"] for item in terminal_violations}),
            {"violations": terminal_violations}))

    context_features = _context_manager_audit(entry, modules, graph)
    # Replace the Phase 4 heuristic for these features with the path-aware audit.
    result["features"] = [f for f in result.get("features", [])
                          if f.get("feature") != "context-manager"] + context_features
    statuses = [f.get("status") for f in result.get("features", [])]
    if "FAIL" in statuses:
        result["status"] = "FAIL"
    elif "UNSUPPORTED" in statuses:
        result["status"] = "UNSUPPORTED"
    elif "REVIEW" in statuses:
        result["status"] = "REVIEW"
    else:
        result["status"] = "PASS"
    return result
