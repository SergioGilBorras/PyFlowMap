"""Generic checks that executable AST statements are represented or explicitly scoped."""

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def graph_for(tmp_path, source, *, language="en"):
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry("sample:run"), max_depth=0,
                       max_nodes=100, language=language)


def test_import_delete_and_definition_effects_are_visible_or_summarized(tmp_path):
    graph = graph_for(tmp_path, """def run(items):
    import math as numeric
    del items[key_for_item()]
    @decorate(make_decoration())
    def local(value=make_default()):
        return deferred_body_call(value)
    class Local(base_factory()):
        value = initialize_class_value()
        def method(self):
            return deferred_method_call()
    return local()
""")

    imports = [node for node in graph.nodes.values()
               if node.label_metadata.get("statement_kind") == "Import"]
    deletions = [node for node in graph.nodes.values()
                 if node.label_metadata.get("statement_kind") == "Delete"]
    functions = [node for node in graph.nodes.values()
                 if node.label_metadata.get("statement_kind") == "FunctionDef"]
    classes = [node for node in graph.nodes.values()
               if node.label_metadata.get("statement_kind") == "ClassDef"]

    assert len(imports) == len(deletions) == len(functions) == len(classes) == 1
    for node in (imports[0], deletions[0], functions[0], classes[0]):
        metadata = node.label_metadata
        assert metadata["statement_summary"] == "summarized"
        assert metadata["source_location"] in node.locations
    assert imports[0].label_metadata["possible_exception"] is True
    assert deletions[0].label_metadata["possible_exception"] is True
    assert any(node.label_metadata.get("call_expression") == "key_for_item"
               for node in graph.nodes.values())

    function_calls = {item["expression"] for item in
                      functions[0].label_metadata["contained_call_sites"]}
    assert {"decorate(make_decoration())", "make_decoration()", "make_default()"} <= function_calls
    assert "deferred_body_call" not in function_calls

    class_calls = {item["expression"] for item in
                   classes[0].label_metadata["contained_call_sites"]}
    assert {"base_factory()", "initialize_class_value()"} <= class_calls
    assert "deferred_method_call" not in class_calls
    assert any("Import at" in warning and "runtime-dependent" in warning
               for warning in graph.warnings)
    assert any("Delete at" in warning and "cannot be determined statically" in warning
               for warning in graph.warnings)
    assert any("Class definition" in warning and "summarized" in warning
               for warning in graph.warnings)


def test_context_and_exception_warnings_name_possible_and_unknown_behavior(tmp_path):
    graph = graph_for(tmp_path, """def run(manager, operation):
    try:
        with manager:
            operation()
    except ValueError:
        recover()
""")

    assert any("handler dispatch is approximated" in warning
               and "handler selection cannot be determined statically" in warning
               for warning in graph.warnings)
    assert any("suppression behavior is dynamic" in warning
               and "possible suppression" in warning
               and "cannot be determined statically" in warning
               for warning in graph.warnings)


def test_summarized_call_label_discloses_calls_kept_only_in_metadata(tmp_path):
    graph = graph_for(tmp_path, """def run():
    return orchestrate()

def orchestrate():
    alpha()
    beta()
    gamma()
    delta()
    epsilon()
    zeta()
    eta()

def alpha(): return 1
def beta(): return 2
def gamma(): return 3
def delta(): return 4
def epsilon(): return 5
def zeta(): return 6
def eta(): return 7
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "orchestrate")
    assert call.label_metadata["contained_calls_omitted_from_label"] > 0
    assert "+1 more in graph metadata" in call.label
    assert len(call.label_metadata["subprocess_calls"]) == 7
    assert any("label displays 6 of 7" in warning for warning in graph.warnings)


def test_definition_time_annotation_calls_follow_future_annotations_semantics(tmp_path):
    graph = graph_for(tmp_path, """from __future__ import annotations

def run():
    def local(value: annotation_factory()):
        return value
    return None
""")
    definition = next(node for node in graph.nodes.values()
                      if node.label_metadata.get("statement_kind") == "FunctionDef")
    assert definition.label_metadata["contained_call_sites"] == []
    assert not definition.label_metadata.get("possible_exception", False)


def test_unresolved_call_explains_known_expression_and_unknown_target(tmp_path):
    graph = graph_for(tmp_path, """def run(receiver, item):
    return receiver.dispatch(item)
""")
    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "receiver.dispatch")
    assert call.label_metadata["call_resolution"] == "unresolved"
    assert "expression is shown" in call.label_metadata["call_resolution_explanation"]
    assert "implementation and effects are unavailable statically" in call.label_metadata[
        "call_resolution_explanation"]


def test_comprehensions_show_outer_iterable_and_per_item_calls_without_fake_paths(tmp_path):
    graph = graph_for(tmp_path, """def run(values):
    return [normalize(value) for value in source_values(values)
            if accepts(value)]
""")
    source_call = next(node for node in graph.nodes.values()
                       if node.label_metadata.get("call_expression") == "source_values")
    summary = next(node for node in graph.nodes.values()
                   if node.label_metadata.get("expression_summary"))
    assert any(edge.source == source_call.id and edge.target == summary.id for edge in graph.edges)
    assert "\nPer-item calls by role: filter [accepts]; result_expression [normalize]" in summary.label
    phases = {item["expression"]: item["evaluation_phase"]
              for item in summary.label_metadata["contained_calls"]}
    assert phases == {"source_values": "immediate", "normalize": "per_iteration",
                      "accepts": "per_iteration"}
    assert summary.label_metadata["significant_control_flow"] is True
