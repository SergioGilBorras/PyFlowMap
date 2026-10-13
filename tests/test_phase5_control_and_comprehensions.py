"""Language-level regressions for explicit transfers and comprehension timing."""

import json

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def graph_for(tmp_path, source, entry="sample:run"):
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry(entry), max_depth=0, max_nodes=100)


def test_all_explicit_return_values_keep_source_and_distinct_paths(tmp_path):
    graph = graph_for(tmp_path, """
def calculate(flag, value):
    if flag:
        return None
    if value:
        return transform(value)
    return {'items': {b'x', 1j}}
""", entry="sample:calculate")
    returns = [node for node in graph.nodes.values()
               if node.label_metadata.get("control_transfer") == "return"]
    assert len(returns) == 3
    assert {node.label_metadata["return_expression"] for node in returns} == {
        "None", "transform(value)", "{'items': {b'x', 1j}}"
    }
    assert all(node.locations and node.label_metadata.get("significant_control_flow")
               for node in returns)
    json.dumps(graph.to_dict())


def test_call_invocation_and_returned_call_value_are_distinct(tmp_path):
    graph = graph_for(tmp_path, """
def run():
    transform()
    return transform()
""")
    calls = [n for n in graph.nodes.values() if n.label_metadata.get("significant_call")]
    returns = [n for n in graph.nodes.values()
               if n.label_metadata.get("control_transfer") == "return"]
    assert len(calls) == 2
    assert len(returns) == 1
    assert returns[0].label_metadata["return_expression"] == "transform()"


def test_return_transfer_survives_finally_and_nested_context_exit_order(tmp_path):
    graph = graph_for(tmp_path, """
class Manager:
    def __enter__(self): return self
    def __exit__(self, *args): return False
def left(): return Manager()
def right(): return Manager()
def run():
    with left(), right():
        try:
            return 7
        finally:
            cleanup()
""")
    exits = [n for n in graph.nodes.values()
             if n.label_metadata.get("context_manager_phase") == "exit"]
    return_exits = [node for node in exits if node.label_metadata["pending_outcome"] == "return"]
    assert len(return_exits) == 2
    assert return_exits[0].label_metadata["context_expression"] == "right()"
    assert return_exits[1].label_metadata["context_expression"] == "left()"
    assert any(node.label_metadata.get("exception_origin") == "context_exit"
               for node in graph.nodes.values())
    returned = [n for n in graph.nodes.values()
                if n.label_metadata.get("control_transfer") == "return"]
    assert returned and returned[0].label_metadata["return_expression"] == "7"


def test_finally_transfer_replaces_pending_return_and_loop_control_is_retained(tmp_path):
    graph = graph_for(tmp_path, """
def run(items):
    for item in items:
        try:
            if item:
                return 1
            continue
        finally:
            if item == 2:
                break
    else:
        return 3
""")
    transfers = [n.label_metadata.get("control_transfer") for n in graph.nodes.values()]
    assert "return" in transfers and "continue" in transfers and "break" in transfers
    assert {n.label_metadata["return_expression"] for n in graph.nodes.values()
            if n.label_metadata.get("control_transfer") == "return"} == {"1", "3"}


def test_finally_return_or_raise_replaces_pending_return(tmp_path):
    replacement = graph_for(tmp_path, """
def run():
    try:
        return 1
    finally:
        return 2
""")
    results = [node.label_metadata.get("return_expression") for node in replacement.nodes.values()
               if node.label_metadata.get("control_transfer") == "return"]
    assert results == ["2"]

    raised = graph_for(tmp_path, """
def run():
    try:
        return 3
    finally:
        raise RuntimeError('cleanup failed')
""")
    assert not any(node.label_metadata.get("control_transfer") == "return"
                   for node in raised.nodes.values())
    assert any("RuntimeError" in node.label for node in raised.nodes.values())


def test_distinct_pending_returns_remain_distinct_after_finally(tmp_path):
    graph = graph_for(tmp_path, """
def run(flag):
    try:
        if flag:
            return 200
        return 404
    finally:
        cleanup()
""")
    values = {node.label_metadata.get("return_value") for node in graph.nodes.values()
              if node.label_metadata.get("control_transfer") == "return"}
    assert values == {200, 404}

    graph = graph_for(tmp_path, """
class Manager:
    def __enter__(self): return self
    def __exit__(self, *args): return False
def run(flag):
    with Manager():
        if flag:
            return 200
        return 404
""")
    context_values = {node.label_metadata.get("return_value") for node in graph.nodes.values()
                      if node.label_metadata.get("control_transfer") == "return"}
    assert context_values == {200, 404}


def test_async_with_keeps_asynchronous_exit_and_pending_return(tmp_path):
    graph = graph_for(tmp_path, """
async def run(manager):
    async with manager:
        return await compute()
""")
    exits = [node for node in graph.nodes.values()
             if node.label_metadata.get("context_manager_phase") == "exit"]
    assert exits and all(node.label_metadata["async"] for node in exits)
    assert any(node.label_metadata.get("control_transfer") == "return"
               and node.label_metadata.get("return_expression") == "await compute()"
               for node in graph.nodes.values())


def test_comprehensions_record_filters_calls_and_generator_laziness(tmp_path):
    graph = graph_for(tmp_path, """
def run(values):
    eager = [convert(item) for item in values if accept(item)]
    unique = {convert(item) for item in values if accept(item)}
    mapping = {key(item): convert(item) for item in values if accept(item)}
    lazy = (convert(item) for item in values if accept(item))
    return eager, unique, mapping, lazy
""")
    summaries = [n for n in graph.nodes.values() if n.label_metadata.get("expression_summary")]
    eager = next(n for n in summaries if n.label_metadata.get("evaluation_policy") == "eager")
    lazy = next(n for n in summaries if n.label_metadata.get("evaluation_policy") == "lazy")
    assert eager.label_metadata["filters"] == ["accept(item)"]
    assert "convert(item)" in eager.label_metadata["result_expressions"]
    assert {call["role"] for call in eager.label_metadata["contained_calls"]} == {
        "filter", "result_expression"
    }
    assert all(call["location"].endswith(":3") for call in eager.label_metadata["contained_calls"])
    assert lazy.label_metadata["body_execution"] == "deferred until iteration"
    assert "values" in lazy.label_metadata["immediate_expressions"]
    assert "convert(item)" in lazy.label_metadata["deferred_expressions"]
    assert {node.label_metadata["comprehension_kind"] for node in summaries} == {
        "list", "set", "dictionary", "generator"
    }
    mapping = next(node for node in summaries
                   if node.label_metadata["comprehension_kind"] == "dictionary")
    assert mapping.label_metadata["result_expressions"] == ["key(item)", "convert(item)"]


def test_inherited_method_is_resolved_but_decorated_behavior_stays_possible(tmp_path):
    graph = graph_for(tmp_path, """
def wrap(function):
    return function
class Base:
    def execute(self, value):
        return value
class Child(Base):
    @wrap
    def perform(self, value):
        return self.execute(value)
def run():
    direct = Child().execute(2)
    return Child().perform(3)
""")
    method_call = next(node for node in graph.nodes.values()
                       if node.label_metadata.get("call_expression") == "Child().perform")
    assert method_call.label_metadata["call_resolution"] == "possible"
    assert method_call.label_metadata["decorators"] == ["wrap"]
    assert method_call.label_metadata["resolved_target"] is None
    assert method_call.label_metadata["possible_targets"] == ["sample:Child.perform"]
    inherited = [node for node in graph.nodes.values()
                 if node.label_metadata.get("call_expression") == "Child().execute"]
    assert inherited
    assert inherited[0].label_metadata["resolved_target"] == "sample:Base.execute"

