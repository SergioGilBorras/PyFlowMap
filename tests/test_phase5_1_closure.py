"""General closure checks for exception paths and call summaries."""

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def graph_for(tmp_path, source, entry="sample:run", *, max_depth=0):
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry(entry), max_depth=max_depth, max_nodes=100)


def test_await_exception_in_try_is_caught_without_parallel_propagation(tmp_path):
    graph = graph_for(tmp_path, """async def run(client):
    try:
        return await client.fetch()
    except TimeoutError:
        return recover()
""")
    awaited = next(node for node in graph.nodes.values()
                   if node.label_metadata.get("async_event") == "await")
    caught = next(node for node in graph.nodes.values()
                  if node.label_metadata.get("exception_route") == "caught")
    finals = {node.id for node in graph.nodes.values() if node.kind == "final"}
    assert any(edge.source == awaited.id and edge.label == "May raise"
               for edge in graph.edges)
    assert not any(edge.source == awaited.id and edge.target in finals for edge in graph.edges)
    assert caught.label_metadata["exception_type_expression"] == "TimeoutError"


def test_uncaught_await_exception_is_explicitly_propagated(tmp_path):
    graph = graph_for(tmp_path, """async def run(client):
    await client.fetch()
    finish()
""")
    awaited = next(node for node in graph.nodes.values()
                   if node.label_metadata.get("async_event") == "await")
    propagated = [node for node in graph.nodes.values()
                  if node.label_metadata.get("exception_route") == "propagated"]
    assert propagated
    assert any(any(edge.source == awaited.id and edge.target == node.id
                   for edge in graph.edges) for node in propagated)
    assert any(node.label_metadata.get("control_transfer") == "raise" for node in propagated)


def test_explicit_raise_propagates_without_an_ordinary_activity_successor(tmp_path):
    graph = graph_for(tmp_path, """def run():
    raise ValueError('invalid')
    unreachable()
""")
    raise_node = next(node for node in graph.nodes.values()
                      if node.label_metadata.get("exception_expression", "").startswith("ValueError"))
    assert raise_node.label_metadata.get("exception_route") == "propagated"
    outgoing = [edge for edge in graph.edges if edge.source == raise_node.id]
    assert len(outgoing) == 1
    assert graph.nodes[outgoing[0].target].kind == "final"
    assert raise_node.label_metadata.get("exception_route") == "propagated"


def test_context_manager_entry_exit_and_suppression_routes_are_distinguished(tmp_path):
    graph = graph_for(tmp_path, """def run(manager, condition):
    with manager:
        if condition:
            raise ValueError('body')
        return 8
    after()
""")
    entry = next(node for node in graph.nodes.values()
                 if node.label_metadata.get("context_manager_phase") == "enter")
    exits = [node for node in graph.nodes.values()
             if node.label_metadata.get("context_manager_phase") == "exit"]
    assert entry.label_metadata.get("exception_route") == "may_raise"
    assert any(node.label_metadata.get("exception_route") == "propagated"
               and node.label_metadata.get("exception_origin") == "context_enter"
               for node in graph.nodes.values())
    assert {node.label_metadata.get("pending_outcome") for node in exits} >= {"return", "raise"}
    suppression = next(node for node in graph.nodes.values()
                       if node.label_metadata.get("context_manager_suppression") == "unknown")
    assert suppression.label_metadata["transfer_outcomes"] == {
        "Yes": "exception_suppressed", "No": "exception_propagated"
    }
    assert any(node.label_metadata.get("exception_origin") == "context_exit"
               for node in graph.nodes.values())


def test_async_context_exit_exception_and_pending_return_are_both_preserved(tmp_path):
    graph = graph_for(tmp_path, """async def run(manager):
    async with manager:
        return await compute()
""")
    assert any(node.label_metadata.get("context_manager_method") == "__aenter__"
               and node.label_metadata.get("exception_route") == "may_raise"
               for node in graph.nodes.values())
    assert any(node.label_metadata.get("context_manager_method") == "__aexit__"
               and node.label_metadata.get("pending_outcome") == "return"
               for node in graph.nodes.values())
    assert any(node.label_metadata.get("exception_origin") == "context_exit"
               for node in graph.nodes.values())
    assert any(node.label_metadata.get("control_transfer") == "return"
               and node.label_metadata.get("return_expression") == "await compute()"
               for node in graph.nodes.values())


def test_resolved_call_says_whether_its_body_was_expanded_or_summarized(tmp_path):
    source = """def operation(value):
    normalize(value)
    validate(value)
def run(value):
    return operation(value)
"""
    summarized = graph_for(tmp_path, source, max_depth=0)
    call = next(node for node in summarized.nodes.values()
                if node.label_metadata.get("call_expression") == "operation")
    body = call.label_metadata["callee_body"]
    assert body["status"] == "summarized"
    assert body["symbol"] == "sample:operation"
    assert body["source_locations"]
    assert body["limits"]

    expanded = graph_for(tmp_path, source, max_depth=2)
    call = next(node for node in expanded.nodes.values()
                if node.label_metadata.get("call_expression") == "operation")
    assert call.label_metadata["callee_body"]["status"] == "expanded"


def test_decorated_resolved_call_references_body_without_claiming_wrapper_behavior(tmp_path):
    graph = graph_for(tmp_path, """def decorate(function):
    return function
@decorate
def operation(value):
    first(value)
    second(value)
def run(value):
    return operation(value)
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "operation")
    body = call.label_metadata["callee_body"]
    assert body["status"] == "referenced"
    assert body["source_locations"]
    assert body["limits"]


def test_ordinary_call_has_possible_exception_outcome_inside_try(tmp_path):
    graph = graph_for(tmp_path, """def run():
    try:
        compute()
    except ValueError:
        recover()
    finish()
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "compute")
    dispatches = [node for node in graph.nodes.values()
                  if node.label_metadata.get("exception_dispatch") == "runtime-dependent"]
    assert dispatches
    assert any(edge.source == call.id and edge.target in {node.id for node in dispatches}
               for edge in graph.edges)


def test_inner_context_expression_failure_exits_already_entered_outer_context(tmp_path):
    graph = graph_for(tmp_path, """def run(outer):
    with outer, create_inner():
        work()
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "create_inner")
    outer_exits = [node for node in graph.nodes.values()
                   if node.label_metadata.get("context_manager_phase") == "exit"
                   and node.label_metadata.get("context_expression") == "outer"]
    assert outer_exits
    assert any(any(edge.source == call.id and edge.target == node.id
                   for edge in graph.edges) for node in outer_exits)


def test_for_iterator_failure_is_dispatchable_without_replacing_exhaustion_else(tmp_path):
    graph = graph_for(tmp_path, """def run(values):
    try:
        for value in values:
            consume(value)
        else:
            exhausted()
    except LookupError:
        recover()
""")
    loop = next(node for node in graph.nodes.values()
                if node.label_metadata.get("loop_kind") == "for")
    dispatch = next(node for node in graph.nodes.values()
                   if node.label_metadata.get("exception_handlers"))
    assert any(edge.source == loop.id and edge.target == dispatch.id for edge in graph.edges)
    exhaustion = next(node for node in graph.nodes.values()
                      if node.label == "exhausted()" or "exhausted" in node.label)
    assert any(edge.source == loop.id and edge.target == exhaustion.id and edge.label == "No"
               for edge in graph.edges)


def test_eager_comprehension_reports_possible_call_exception_but_generator_is_deferred(tmp_path):
    eager = graph_for(tmp_path, """def run(values):
    return [convert(value) for value in values]
""")
    summary = next(node for node in eager.nodes.values()
                   if node.label_metadata.get("expression_summary"))
    assert summary.label_metadata.get("exception_route") == "may_raise"
    assert summary.label_metadata.get("contained_call_expressions") == ["convert"]
    assert any(edge.source == summary.id and edge.label == "May raise" for edge in eager.edges)

    lazy = graph_for(tmp_path, """def run(values):
    return (convert(value) for value in values)
""")
    summary = next(node for node in lazy.nodes.values()
                   if node.label_metadata.get("expression_summary"))
    assert summary.label_metadata.get("exception_route") != "may_raise"
    assert summary.label_metadata.get("deferred_exception_behavior") == "iteration_time"


def test_context_cleanup_coalesces_multiple_unknown_calls_with_traceable_sources(tmp_path):
    graph = graph_for(tmp_path, """def run(manager):
    with manager:
        first()
        second()
        third()
""")
    grouped = [node for node in graph.nodes.values()
               if node.label_metadata.get("exception_origin") == "aggregated_unknown"]
    assert len(grouped) == 1
    source_ids = {item["node_id"] for item in grouped[0].label_metadata["exception_sources"]}
    assert len(source_ids) == 3
    exits = [node for node in graph.nodes.values()
             if node.label_metadata.get("context_manager_phase") == "exit"
             and node.label_metadata.get("pending_outcome") == "raise"]
    assert len(exits) == 1
    assert any(edge.source == grouped[0].id and edge.target == exits[0].id
               for edge in graph.edges)
