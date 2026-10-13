"""Generic checks that executable assignments remain in their source control-flow paths."""

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def _graph(tmp_path, source):
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry("app:main"), max_nodes=100, max_depth=0)


def _node(graph, **metadata):
    return next(node for node in graph.nodes.values()
                if all(node.label_metadata.get(key) == value
                       for key, value in metadata.items()))


def _reachable_without(graph, start, target, excluded):
    adjacency = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)
    pending = [start]
    seen = set(excluded)
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(adjacency.get(current, ()))
    return False


def test_match_case_assignments_feed_later_match_without_cross_case_execution(tmp_path):
    graph = _graph(tmp_path,
        "def main(raw, enabled):\n"
        "    match raw:\n"
        "        case ('set', name, value) if enabled(name):\n"
        "            current = (name, value)\n"
        "        case ('clear', name):\n"
        "            current = (name, None)\n"
        "        case ('reject',):\n"
        "            raise ValueError()\n"
        "        case _:\n"
        "            return None\n"
        "    match current:\n"
        "        case ('mode', 'safe'):\n"
        "            consume_safe()\n"
        "        case (name, None):\n"
        "            consume_clear(name)\n"
        "        case _:\n"
        "            consume_other()\n")

    first = _node(graph, match_subject="raw")
    second = _node(graph, match_subject="current")
    first_assignment = _node(graph, assignment="current = (name, value)")
    second_assignment = _node(graph, assignment="current = (name, None)")
    assert first_assignment.locations == ["app.py:4"]
    assert second_assignment.locations == ["app.py:6"]
    assert any(edge.source == first_assignment.id and edge.target == second.id
               for edge in graph.edges)
    assert any(edge.source == second_assignment.id and edge.target == second.id
               for edge in graph.edges)
    assert not any(edge.source == first_assignment.id and edge.target == second_assignment.id
                   for edge in graph.edges)
    assert not any(edge.source == second_assignment.id and edge.target == first_assignment.id
                   for edge in graph.edges)
    assert not _reachable_without(
        graph, first.id, second.id, {first_assignment.id, second_assignment.id})

    returned = _node(graph, return_expression="None")
    raised = _node(graph, exception_expression="ValueError()")
    assert not any(edge.source == returned.id and edge.target == second.id for edge in graph.edges)
    assert not any(edge.source == raised.id and edge.target == second.id for edge in graph.edges)


def test_assignments_in_if_try_and_loop_bodies_are_retained_with_provenance(tmp_path):
    graph = _graph(tmp_path,
        "def main(flag, items):\n"
        "    if flag:\n"
        "        left = make_left()\n"
        "    else:\n"
        "        right: object = make_right()\n"
        "    try:\n"
        "        selected = make_selected()\n"
        "    except LookupError:\n"
        "        selected = make_fallback()\n"
        "    for item in items:\n"
        "        latest = make_item(item)\n"
        "        if stop(item):\n"
        "            break\n"
        "    consume(left, right, selected, latest)\n")

    expected = {
        "left = make_left()": "app.py:3",
        "right: object = make_right()": "app.py:5",
        "selected = make_selected()": "app.py:7",
        "selected = make_fallback()": "app.py:9",
        "latest = make_item(item)": "app.py:11",
    }
    for expression, location in expected.items():
        assignment = _node(graph, assignment=expression)
        assert assignment.locations == [location]
        assert assignment.label_metadata["significant_state_change"] is True
        assert any(expression.partition(" = ")[2].split("(")[0]
                   in node.label_metadata.get("call_expression", "")
                   for node in graph.nodes.values())


def test_augmented_assignment_evaluates_target_before_value_and_is_visible(tmp_path):
    graph = _graph(tmp_path,
        "def main():\n"
        "    box().field += amount()\n")

    calls = {node.label_metadata.get("call_expression"): node
             for node in graph.nodes.values() if node.label_metadata.get("call_expression")}
    update = next(node for node in graph.nodes.values()
                  if node.label_metadata.get("significant_state_change")
                  and node.locations == ["app.py:2"])
    assert list(calls).index("box") < list(calls).index("amount")
    assert any(edge.source == calls["box"].id and edge.target == calls["amount"].id
               for edge in graph.edges)
    assert any(edge.source == calls["amount"].id and edge.target == update.id
               for edge in graph.edges)


def test_possible_uninitialized_path_is_not_filled_with_a_synthetic_assignment(tmp_path):
    graph = _graph(tmp_path,
        "def main(flag):\n"
        "    if flag:\n"
        "        value = initialize()\n"
        "    consume(value)\n")

    condition = _node(graph, source_expression="flag")
    assignment = _node(graph, assignment="value = initialize()")
    consume = _node(graph, call_expression="consume")
    assert any(edge.source == condition.id and edge.label == "No"
               and edge.target == consume.id for edge in graph.edges)
    assert not any(edge.source == condition.id and edge.label == "No"
                   and edge.target == assignment.id for edge in graph.edges)


def test_named_expression_assignment_is_visible_before_its_condition(tmp_path):
    graph = _graph(tmp_path,
        "def main():\n"
        "    if (candidate := lookup()):\n"
        "        consume(candidate)\n")

    lookup = _node(graph, call_expression="lookup")
    assignment = _node(graph, named_expression=True)
    condition = next(node for node in graph.nodes.values()
                     if node.kind == "decision" and "candidate" in node.label)
    assert any(edge.source == lookup.id and edge.target == assignment.id
               for edge in graph.edges)
    assert any(edge.source == assignment.id and edge.target == condition.id
               for edge in graph.edges)
