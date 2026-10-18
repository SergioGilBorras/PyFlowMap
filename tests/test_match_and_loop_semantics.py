"""Generic control-flow regressions for Python structural matching and loops."""

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def _graph(tmp_path, source):
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry("app:main"), max_depth=0)


def _node(graph, predicate):
    return next(node for node in graph.nodes.values() if predicate(node))


def _edge(graph, source, target, label=None):
    return any(edge.source == source and edge.target == target
               and (label is None or edge.label == label) for edge in graph.edges)


def _control_topology(graph):
    roles = []
    for node in graph.nodes.values():
        metadata = node.label_metadata
        roles.append((node.kind, metadata.get("loop_kind"), metadata.get("pattern_kind"),
                      metadata.get("pattern_irrefutable"), metadata.get("control_transfer")))
    edges = [(edge.source, edge.target, edge.label) for edge in graph.edges]
    return roles, edges


def test_match_evaluates_subject_once_and_routes_failed_pattern_and_guard_in_order(tmp_path):
    graph = _graph(tmp_path,
        "def main():\n"
        "    match read_value():\n"
        "        case 10 if permitted():\n"
        "            accept_ten()\n"
        "        case [item] | {'item': item}:\n"
        "            accept_container()\n"
        "        case _:\n"
        "            fallback()\n"
        "    finish()\n")

    subject_calls = [node for node in graph.nodes.values()
                     if node.label_metadata.get("call_expression") == "read_value"]
    assert len(subject_calls) == 1
    subject = _node(graph, lambda n: n.label_metadata.get("match_subject") == "read_value()")
    assert subject.label_metadata["evaluation_count"] == 1
    cases = sorted((node for node in graph.nodes.values()
                    if "match_case_index" in node.label_metadata),
                   key=lambda node: node.label_metadata["match_case_index"])
    assert len(cases) == 3
    assert cases[1].label_metadata["pattern_alternatives"] == ["[item]", "{'item': item}"]
    assert _edge(graph, subject.id, cases[0].id)
    assert _edge(graph, cases[0].id, cases[1].id, "No")
    guard = _node(graph, lambda n: n.kind == "decision"
                  and n.label_metadata.get("source_expression") == "permitted()")
    assert _edge(graph, guard.id, cases[1].id, "No")
    assert not any(edge.source == cases[2].id and edge.label == "No" for edge in graph.edges)
    accept_ten = _node(graph, lambda n: n.label_metadata.get("call_expression") == "accept_ten")
    accept_container = _node(
        graph, lambda n: n.label_metadata.get("call_expression") == "accept_container")
    assert not _edge(graph, accept_ten.id, accept_container.id)
    assert any("Pattern matching is data-dependent" in warning for warning in graph.warnings)


def test_match_pattern_captures_are_bound_before_the_guard_reads_them(tmp_path):
    graph = _graph(tmp_path,
        "def main(message):\n"
        "    match message:\n"
        "        case {'payload': payload} if usable(payload):\n"
        "            consume(payload)\n"
        "        case _:\n"
        "            skip()\n")

    capture = _node(graph, lambda n: n.label_metadata.get("pattern_captures") == ["payload"])
    guard = _node(graph, lambda n: n.label_metadata.get("match_guard_case_index") == 0)
    body = _node(graph, lambda n: n.label_metadata.get("call_expression") == "consume")
    guard_call = _node(graph, lambda n: n.label_metadata.get("call_expression") == "usable")
    assert _edge(graph, capture.id, guard_call.id)
    assert _edge(graph, guard_call.id, guard.id)
    assert _edge(graph, guard.id, body.id, "Yes")
    assert not _edge(graph, guard.id, capture.id)


def test_match_preserves_return_raise_break_and_continue_exits(tmp_path):
    graph = _graph(tmp_path,
        "def main(values):\n"
        "    for value in values:\n"
        "        match value:\n"
        "            case 'stop':\n"
        "                break\n"
        "            case 'skip':\n"
        "                continue\n"
        "            case 'fail':\n"
        "                raise RuntimeError()\n"
        "            case 'done':\n"
        "                return 7\n"
        "            case _:\n"
        "                process(value)\n"
        "    else:\n"
        "        exhausted()\n"
        "    after_loop()\n")

    loop = _node(graph, lambda n: n.label_metadata.get("loop_kind") == "for")
    exhausted = _node(graph, lambda n: n.label_metadata.get("call_expression") == "exhausted")
    after_loop = _node(graph, lambda n: n.label_metadata.get("call_expression") == "after_loop")
    assert _edge(graph, loop.id, exhausted.id, "No")
    # The break case exits the loop and bypasses its else suite.
    break_case = _node(graph, lambda n: n.label_metadata.get("match_pattern") == "'stop'")
    break_node = _node(graph, lambda n: n.label_metadata.get("control_transfer") == "break")
    assert _edge(graph, break_case.id, break_node.id, "Yes")
    assert _edge(graph, break_node.id, after_loop.id)
    assert not _edge(graph, break_case.id, exhausted.id)
    assert any(node.label_metadata.get("exception_expression") == "RuntimeError()"
               for node in graph.nodes.values())
    assert any(node.label == "Return 7" and node.label_metadata.get("return_value") == 7
               for node in graph.nodes.values())
    continue_case = _node(graph, lambda n: n.label_metadata.get("match_pattern") == "'skip'")
    continue_node = _node(graph, lambda n: n.label_metadata.get("control_transfer") == "continue")
    assert _edge(graph, continue_case.id, continue_node.id, "Yes")
    assert _edge(graph, continue_node.id, loop.id)


def test_match_class_sequence_mapping_and_literal_patterns_remain_distinct(tmp_path):
    graph = _graph(tmp_path,
        "def main(value):\n"
        "    match value:\n"
        "        case {'name': name}:\n"
        "            use_mapping(name)\n"
        "        case [first, *rest]:\n"
        "            use_sequence(first, rest)\n"
        "        case Widget(x, y):\n"
        "            use_class(x, y)\n"
        "        case 3 | 4:\n"
        "            use_literal()\n"
        "        case _: use_fallback()\n")

    selections = sorted((node for node in graph.nodes.values()
                         if "match_case_index" in node.label_metadata),
                        key=lambda node: node.label_metadata["match_case_index"])
    assert [node.label_metadata["pattern_kind"] for node in selections] == [
        "MatchMapping", "MatchSequence", "MatchClass", "MatchOr", "MatchAs"]
    assert all(node.locations for node in selections)
    assert all(any(edge.source == selection.id and edge.label == "No"
                   for edge in graph.edges) for selection in selections[:-1])
    assert not any(edge.source == selections[-1].id and edge.label == "No"
                   for edge in graph.edges)
    assert len({edge.target for selection in selections for edge in graph.edges
                if edge.source == selection.id and edge.label == "Yes"}) == len(selections)


def test_match_and_for_control_topology_is_invariant_under_domain_renames(tmp_path):
    original = (
        "def entry(data, records):\n"
        "    match lookup(data):\n"
        "        case 'amber': accept()\n"
        "        case Device(value) if valid(value): inspect(value)\n"
        "        case _: fallback()\n"
        "    for record in records:\n"
        "        if skip(record): continue\n"
        "        if stop(record): break\n"
        "        process(record)\n"
        "    else: exhausted()\n")
    renamed = (
        "def route(payload, batches):\n"
        "    match fetch(payload):\n"
        "        case 'violet': approve()\n"
        "        case Packet(element) if ready(element): examine(element)\n"
        "        case _: other()\n"
        "    for batch in batches:\n"
        "        if omit(batch): continue\n"
        "        if halt(batch): break\n"
        "        handle(batch)\n"
        "    else: complete()\n")
    (tmp_path / "app.py").write_text(original, encoding="utf-8")
    with load_project(tmp_path) as project:
        first = analyze(project, project.entry("app:entry"), max_depth=0, max_nodes=40)
    (tmp_path / "app.py").write_text(renamed, encoding="utf-8")
    with load_project(tmp_path) as project:
        second = analyze(project, project.entry("app:route"), max_depth=0, max_nodes=40)
    assert _control_topology(first) == _control_topology(second)


def test_for_else_separates_exhaustion_break_and_continue(tmp_path):
    graph = _graph(tmp_path,
        "def main(items):\n"
        "    for item in items:\n"
        "        if skip(item):\n"
        "            continue\n"
        "        if stop(item):\n"
        "            break\n"
        "        process(item)\n"
        "    else:\n"
        "        exhausted()\n"
        "    after()\n")

    loop = _node(graph, lambda n: n.label_metadata.get("loop_kind") == "for")
    exhausted = _node(graph, lambda n: n.label_metadata.get("call_expression") == "exhausted")
    after = _node(graph, lambda n: n.label_metadata.get("call_expression") == "after")
    stop = _node(graph, lambda n: n.kind == "decision"
                 and n.label_metadata.get("source_expression") == "stop(item)")
    skip = _node(graph, lambda n: n.kind == "decision"
                 and n.label_metadata.get("source_expression") == "skip(item)")
    break_node = _node(graph, lambda n: n.label_metadata.get("control_transfer") == "break")
    continue_node = _node(graph, lambda n: n.label_metadata.get("control_transfer") == "continue")
    assert _edge(graph, loop.id, exhausted.id, "No")
    assert _edge(graph, stop.id, break_node.id, "Yes")
    assert _edge(graph, break_node.id, after.id)
    assert not _edge(graph, stop.id, exhausted.id)
    assert _edge(graph, skip.id, continue_node.id, "Yes")
    assert _edge(graph, continue_node.id, loop.id)


def test_nested_break_only_exits_inner_loop_and_outer_else_waits_for_outer_exhaustion(tmp_path):
    graph = _graph(tmp_path,
        "def main(groups):\n"
        "    for group in groups:\n"
        "        for item in group:\n"
        "            if found(item):\n"
        "                break\n"
        "        else:\n"
        "            inner_exhausted()\n"
        "        process_group(group)\n"
        "    else:\n"
        "        outer_exhausted()\n")

    loops = [node for node in graph.nodes.values()
             if node.label_metadata.get("loop_kind") == "for"]
    assert len(loops) == 2
    inner, outer = sorted(loops, key=lambda n: n.locations[0].split(":")[-1], reverse=True)
    decision = _node(graph, lambda n: n.kind == "decision"
                     and n.label_metadata.get("source_expression") == "found(item)")
    group_step = _node(graph, lambda n: n.label_metadata.get("call_expression") == "process_group")
    inner_exhausted = _node(graph, lambda n: n.label_metadata.get("call_expression") == "inner_exhausted")
    outer_exhausted = _node(graph, lambda n: n.label_metadata.get("call_expression") == "outer_exhausted")
    break_node = _node(graph, lambda n: n.label_metadata.get("control_transfer") == "break")
    assert _edge(graph, decision.id, break_node.id, "Yes")
    assert _edge(graph, break_node.id, group_step.id)
    assert not _edge(graph, decision.id, inner_exhausted.id)
    assert not _edge(graph, decision.id, outer_exhausted.id)
    assert _edge(graph, inner.id, inner_exhausted.id, "No")
    assert _edge(graph, outer.id, outer_exhausted.id, "No")


def test_while_else_runs_only_after_false_condition_and_finally_precedes_loop_control(tmp_path):
    graph = _graph(tmp_path,
        "def main(active):\n"
        "    while active():\n"
        "        try:\n"
        "            if should_continue():\n"
        "                continue\n"
        "            if should_break():\n"
        "                break\n"
        "            if should_return():\n"
        "                return 3\n"
        "            work()\n"
        "        finally:\n"
        "            cleanup()\n"
        "    else:\n"
        "        exhausted()\n"
        "    after()\n")

    loop = _node(graph, lambda n: n.label_metadata.get("loop_kind") == "while")
    condition = _node(graph, lambda n: n.label_metadata.get("source_expression") == "active()")
    exhausted = _node(graph, lambda n: n.label_metadata.get("call_expression") == "exhausted")
    after = _node(graph, lambda n: n.label_metadata.get("call_expression") == "after")
    cleanups = [node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "cleanup"]
    assert _edge(graph, condition.id, exhausted.id, "No")
    assert any(edge.source in {node.id for node in cleanups} and edge.target == loop.id
               for edge in graph.edges)
    assert any(edge.source in {node.id for node in cleanups} and edge.target == after.id
               for edge in graph.edges)
    assert not any(edge.source == loop.id and edge.target == after.id and edge.label == "No"
                   for edge in graph.edges)
    assert any(node.label == "Return 3" for node in graph.nodes.values())
