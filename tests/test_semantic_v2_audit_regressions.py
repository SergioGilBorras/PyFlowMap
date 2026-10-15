"""Generic, source-based regressions for independently confirmed Python semantics."""

import ast
from collections import deque

from pyflowmap.diagrams.activity import analyze
from pyflowmap.hierarchy import build_hierarchical_outline
from pyflowmap.project import load_project


def _analyze(tmp_path, source, entry="sample:run", max_depth=0):
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry(entry), max_depth=max_depth, max_nodes=100)


def _node(graph, predicate):
    return next(node for node in graph.nodes.values() if predicate(node))


def _reachable(graph, source, target):
    pending = deque([source])
    seen = set()
    while pending:
        current = pending.popleft()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(edge.target for edge in graph.edges if edge.source == current)
    return False


def test_generator_close_injects_generatorexit_through_finally(tmp_path):
    graph = _analyze(tmp_path, """def run():
    try:
        yield produce()
    finally:
        release()
""")
    close = _node(graph, lambda n: n.label_metadata.get("generator_event") == "close")
    cleanup = [n for n in graph.nodes.values()
               if n.label_metadata.get("call_expression") == "release"]
    assert close.label_metadata.get("exception_type") == "GeneratorExit"
    assert close.label_metadata.get("control_transfer") == "raise"
    assert any(_reachable(graph, close.id, node.id) for node in cleanup)
    assert any("GeneratorExit" in warning for warning in graph.warnings)


def test_async_generator_close_retains_async_finally_cleanup(tmp_path):
    graph = _analyze(tmp_path, """async def run():
    try:
        yield await produce()
    finally:
        await release()
""")
    close = _node(graph, lambda n: n.label_metadata.get("generator_event") == "close")
    cleanup = [n for n in graph.nodes.values()
               if n.label_metadata.get("async_event") == "await"
               and n.label_metadata.get("awaited_expression") == "release()"]
    assert close.label_metadata.get("generator_close_kind") == "async"
    assert any(_reachable(graph, close.id, node.id) for node in cleanup)


def test_generator_close_can_be_caught_before_finally_runs(tmp_path):
    graph = _analyze(tmp_path, """def run():
    try:
        yield make_value()
    except GeneratorExit:
        record_close()
    finally:
        release()
""")
    close = _node(graph, lambda n: n.label_metadata.get("generator_event") == "close")
    caught = [n for n in graph.nodes.values()
              if n.label_metadata.get("call_expression") == "record_close"]
    cleanups = [n for n in graph.nodes.values()
                if n.label_metadata.get("call_expression") == "release"]
    assert any(_reachable(graph, close.id, node.id) for node in caught)
    assert any(_reachable(graph, close.id, node.id) for node in cleanups)


def test_generator_call_is_referenced_as_lazy_not_executed_inline(tmp_path):
    graph = _analyze(tmp_path, """def make_stream():
    yield first_value()
    yield second_value()
def run():
    return make_stream()
""", max_depth=3)
    call = _node(graph, lambda n: n.label_metadata.get("call_expression") == "make_stream")
    assert call.label_metadata["callee_body"]["status"] == "summarized"
    assert call.label_metadata["callee_body"]["execution_policy"] == "deferred"
    assert any("Generator body is deferred" in item
               for item in call.label_metadata["callee_body"]["limits"])
    assert not any(n.label_metadata.get("generator_event") in {"yield", "yield_from"}
                   for n in graph.nodes.values())


def test_coroutine_body_is_not_expanded_before_await(tmp_path):
    graph = _analyze(tmp_path, """async def fetch_value():
    before()
    result = await remote_call()
    after()
    return result
async def run():
    return await fetch_value()
""", max_depth=3)
    call = _node(graph, lambda n: n.label_metadata.get("call_expression") == "fetch_value")
    await_node = _node(graph, lambda n: n.label_metadata.get("async_event") == "await"
                        and n.label_metadata.get("awaited_expression") == "fetch_value()")
    assert call.label_metadata["callee_body"]["execution_policy"] == "deferred"
    assert _reachable(graph, call.id, await_node.id)
    assert not any(n.label_metadata.get("call_expression") == "remote_call"
                   for n in graph.nodes.values())


def test_except_star_can_run_multiple_handlers_and_propagate_remainder(tmp_path):
    graph = _analyze(tmp_path, """def run():
    try:
        raise build_group()
    except* ValueError:
        handle_value()
    except* TypeError:
        handle_type()
    finally:
        cleanup()
""")
    first = _node(graph, lambda n: n.label_metadata.get("call_expression") == "handle_value")
    second = _node(graph, lambda n: n.label_metadata.get("call_expression") == "handle_type")
    cleanup = _node(graph, lambda n: n.label_metadata.get("call_expression") == "cleanup")
    assert _reachable(graph, first.id, second.id)
    assert _reachable(graph, second.id, cleanup.id)
    assert any(n.label_metadata.get("exception_route") == "propagated_subgroup"
               for n in graph.nodes.values())
    dispatches = [n for n in graph.nodes.values() if n.kind == "decision"
                  and n.label_metadata.get("exception_dispatch") == "except_star_ordered"]
    assert len(dispatches) == 2


def test_assignment_feeding_match_subject_is_an_explicit_activity(tmp_path):
    source = """def run(raw):
    subject = normalize(raw)
    match subject:
        case 1:
            return accept()
        case _:
            return reject()
"""
    tree = ast.parse(source)
    graph = _analyze(tmp_path, source)
    assignment_line = next(n.lineno for n in ast.walk(tree)
                           if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "subject"
                                   for t in n.targets))
    assignment = _node(graph, lambda n: n.label_metadata.get("assignment") ==
                       "subject = normalize(raw)")
    subject = _node(graph, lambda n: n.label_metadata.get("match_subject") == "subject")
    assert any(f"sample.py:{assignment_line}" in loc for loc in assignment.locations)
    assert _reachable(graph, assignment.id, subject.id)


def test_unpacking_assignment_has_source_linked_may_raise_route(tmp_path):
    source = """def run():
    try:
        left, right = read_pair()
    except (TypeError, ValueError):
        recover()
    return left
"""
    tree = ast.parse(source)
    graph = _analyze(tmp_path, source)
    unpack = _node(graph, lambda n: n.label_metadata.get("unpacking_assignment") is True)
    handler = _node(graph, lambda n: n.kind == "decision"
                    and n.label_metadata.get("exception_handlers") is not None)
    syntax = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                  and isinstance(n.targets[0], (ast.Tuple, ast.List)))
    assert {"TypeError", "ValueError"} <= set(unpack.label_metadata["possible_exception_types"])
    assert any(f"sample.py:{syntax.lineno}" in location for location in unpack.locations)
    assert _reachable(graph, unpack.id, handler.id)


def test_with_target_unpack_failure_runs_context_exit(tmp_path):
    graph = _analyze(tmp_path, """def run(manager):
    with manager as (left, right):
        use(left, right)
""")
    binding = _node(graph, lambda n: n.label_metadata.get("context_manager_binding") ==
                    "(left, right)")
    exits = [n for n in graph.nodes.values()
             if n.label_metadata.get("context_manager_phase") == "exit"]
    assert binding.label_metadata.get("unpacking_assignment") is True
    assert binding.label_metadata.get("exception_route") == "may_raise"
    assert any(_reachable(graph, binding.id, node.id) for node in exits)


def test_call_provenance_remains_attached_when_reached_from_finally(tmp_path):
    graph = _analyze(tmp_path, """def release():
    return None
def run():
    try:
        return 7
    finally:
        release()
""")
    call = _node(graph, lambda n: n.label_metadata.get("call_expression") == "release")
    assert call.label_metadata.get("caller_symbol") == "sample:run"
    assert call.locations == ["sample.py:7"]
    body = call.label_metadata.get("callee_body", {})
    assert body.get("symbol") == "sample:release"
    assert "sample.py:1-2" in body.get("source_locations", [])
    assert all(n.label_metadata.get("caller_symbol") == "sample:run"
               and n.locations == ["sample.py:7"]
               for n in graph.nodes.values()
               if n.label_metadata.get("call_expression") == "release")


def test_nested_context_managers_remain_navigable_in_hierarchical_view(tmp_path):
    source = """def run(first, second):
    with first:
        async with second:
            perform()
"""
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        outline = build_hierarchical_outline(project.entry("sample:run"))
    phases = [node for node in outline.nodes.values()
              if node.label_metadata.get("phase_summary")]
    assert phases
    phase = phases[0]
    assert phase.label_metadata["detail_symbol"] == "sample:run"
    assert {"sample.py:2", "sample.py:3", "sample.py:4"} <= set(
        phase.label_metadata["source_locations"])
    assert phase.label_metadata["source_references"]
    assert outline.warnings and "detailed activity graph" in outline.warnings[-1]
