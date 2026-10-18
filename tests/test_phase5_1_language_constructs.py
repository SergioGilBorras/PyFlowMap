"""Generic Python syntax coverage for the post-Phase-5 correctness fixes."""

import ast

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def analyze_source(tmp_path, source, entry="sample:run"):
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry(entry), max_depth=0, max_nodes=100)


def test_while_else_exhaustion_state_is_visible_and_break_bypasses_it(tmp_path):
    source = """def run(items):
    index = 0
    while index < len(items):
        index += 1
        if index == 2:
            continue
        if index == 4:
            break
    else:
        index = -1
    return index
"""
    graph = analyze_source(tmp_path, source)
    exhaustion_assignment = next(node for node in graph.nodes.values()
                                 if node.label_metadata.get("assignment") == "index = -1")
    decisions = [node for node in graph.nodes.values()
                 if node.label_metadata.get("source_expression") == "index < len(items)"]
    assert decisions
    assert any(edge.source == decision.id and edge.label == "No"
               and edge.target == exhaustion_assignment.id for edge in graph.edges
               for decision in decisions)
    breaks = [node for node in graph.nodes.values()
              if node.label_metadata.get("control_transfer") == "break"]
    assert breaks and all(any(edge.source == node.id for edge in graph.edges) for node in breaks)


def test_nested_while_else_keeps_exhaustion_separate_from_break_and_transfers(tmp_path):
    graph = analyze_source(tmp_path, """def run(rows):
    outer = 0
    while outer < len(rows):
        inner = 0
        while inner < len(rows[outer]):
            if rows[outer][inner] is None:
                raise ValueError('missing')
            if rows[outer][inner] < 0:
                break
            inner += 1
        else:
            mark_exhausted(outer)
        if outer == 3:
            return inner
        outer += 1
    else:
        mark_all_exhausted()
    return outer
""")
    assignments = [node for node in graph.nodes.values()
                   if node.label_metadata.get("call_expression", "").startswith("mark_")]
    assert {node.label_metadata["call_expression"] for node in assignments} == {
        "mark_exhausted", "mark_all_exhausted"
    }
    assert any(node.label_metadata.get("control_transfer") == "raise"
               for node in graph.nodes.values()) or any("raise" in node.label.casefold()
                                                         for node in graph.nodes.values())
    assert any(node.label_metadata.get("control_transfer") == "return"
               for node in graph.nodes.values())


def test_yield_and_yield_from_have_suspension_resume_and_close_paths(tmp_path):
    graph = analyze_source(tmp_path, """def run(values):
    yield first(values)
    result = yield from make_stream(values)
    return result
""")
    yielded = [node for node in graph.nodes.values()
               if node.label_metadata.get("generator_event") == "yield"]
    delegated = [node for node in graph.nodes.values()
                 if node.label_metadata.get("generator_event") == "yield_from"]
    assert yielded and delegated
    for node in yielded + delegated:
        assert node.label_metadata.get("suspension") is True
        assert node.locations
        assert any(edge.source == node.id and
                   graph.nodes[edge.target].label_metadata.get("generator_event") == "resume"
                   for edge in graph.edges)
        assert any(edge.source == node.id and edge.label.casefold() in {"close", "closed", "cerrar", "cerrado"}
                   for edge in graph.edges)
    assert any("generator" in warning.casefold() or "generador" in warning.casefold()
               for warning in graph.warnings)


def test_assert_has_optimization_gate_failure_and_lazy_message(tmp_path):
    graph = analyze_source(tmp_path, """def run(value):
    assert validate(value), build_message(value)
    continue_work(value)
""")
    assert_nodes = [node for node in graph.nodes.values()
                    if node.label_metadata.get("assertion") is True]
    assert len(assert_nodes) == 1
    assert assert_nodes[0].label_metadata["optimization_sensitive"] is True
    assert assert_nodes[0].label_metadata["message_evaluation"] == "failure path only"
    assert any(node.label_metadata.get("exception_type") == "AssertionError"
               for node in graph.nodes.values())
    assert any("optimization" in warning.casefold() or "optimiz" in warning.casefold()
               for warning in graph.warnings)


def test_dynamic_builtin_calls_in_assignments_are_not_silently_elided(tmp_path):
    graph = analyze_source(tmp_path, """def run(receiver, name):
    method = getattr(receiver, name, None)
    present = hasattr(receiver, name)
    return method, present
""")
    expressions = {node.label_metadata.get("call_expression")
                   for node in graph.nodes.values()
                   if node.label_metadata.get("significant_call")}
    assert "getattr" in expressions
    assert "hasattr" in expressions


def test_decorator_presence_origin_and_uncertainty_are_preserved(tmp_path):
    graph = analyze_source(tmp_path, """def decorate(function):
    return function
@decorate
def operation(value):
    return value
def run(value):
    return operation(value)
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "operation")
    assert call.label_metadata.get("decorators") == ["decorate"]
    assert call.label_metadata.get("decorator_locations")
    assert call.label_metadata.get("decorator_may_replace_callable") is True
    assert call.label_metadata.get("resolved_target") is None
    assert "operation" in call.label_metadata.get("possible_targets", [])[-1]


def test_await_is_an_explicit_suspension_with_possible_exception(tmp_path):
    graph = analyze_source(tmp_path, """async def run(client):
    return await client.fetch()
""")
    awaits = [node for node in graph.nodes.values()
              if node.label_metadata.get("async_event") == "await"]
    assert awaits
    assert awaits[0].label_metadata.get("suspension") is True
    assert awaits[0].label_metadata.get("possible_exception") is True
    assert any("await" in warning.casefold() for warning in graph.warnings)


def test_super_dispatch_resolves_only_static_single_inheritance(tmp_path):
    graph = analyze_source(tmp_path, """class Base:
    def execute(self, value):
        return normalize(value)
class Child(Base):
    def execute(self, value):
        return super().execute(value)
""", entry="sample:Child.execute")
    calls = [node for node in graph.nodes.values()
             if node.label_metadata.get("call_expression") == "super().execute"]
    assert calls
    assert calls[0].label_metadata.get("resolved_target") == "sample:Base.execute"


def test_nested_call_forms_in_assignment_values_keep_source_calls(tmp_path):
    source = """def run(value, key):
    result = combine(value[index()], factory=build(value), **options())
    mapping = {key_for(value): item_for(value)}
    text = f"{render(value)}"
    return result, mapping, text
"""
    tree = ast.parse(source)
    graph = analyze_source(tmp_path, source)
    expected = {ast.unparse(node.func) for node in ast.walk(tree)
                if isinstance(node, ast.Call)}
    represented = {node.label_metadata.get("call_expression")
                   for node in graph.nodes.values()
                   if node.label_metadata.get("significant_call")}
    assert expected <= represented


def test_ast_coverage_has_no_silent_omission_for_relevant_constructs(tmp_path):
    source = """async def run(source, manager):
    async with manager:
        assert source is not None
        yield from source
        await process(source)
"""
    tree = ast.parse(source)
    graph = analyze_source(tmp_path, source)
    required = (ast.Assert, ast.AsyncWith, ast.YieldFrom, ast.Await)
    for construct in required:
        source_nodes = [node for node in ast.walk(tree) if isinstance(node, construct)]
        for syntax in source_nodes:
            represented = any(f"sample.py:{syntax.lineno}" in node.locations
                              for node in graph.nodes.values())
            warned = any(str(syntax.lineno) in warning for warning in graph.warnings)
            assert represented or warned, f"{construct.__name__} silently omitted at {syntax.lineno}"
