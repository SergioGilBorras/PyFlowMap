"""UML-inspired notation and branching invariants."""

import json
import os
from pathlib import Path

import pytest

from pyflowmap.cli import main
from pyflowmap.diagrams.activity import analyze
from pyflowmap.hierarchy import build_hierarchical_outline
from pyflowmap.mcp_server import generate_activity_diagram
from pyflowmap.project import load_project
from pyflowmap.service import generate_diagram

P4 = Path(__file__).parent / "fixtures" / "references" / "synthetic-activity-regression-v1"
ENTRY = "planning.coordinator:PlanningCoordinator.plan"


def test_pinned_p4_conditional_polality_shared_return_and_uml_markers():
    with load_project(P4) as project:
        graph = analyze(project, project.entry(ENTRY), language="es")
    kinds = [n.kind for n in graph.nodes.values()]
    assert kinds.count("initial") == 1
    assert kinds.count("final") == 1
    assert kinds.count("result") >= 1
    assert len([n for n in graph.nodes.values() if n.kind == "decision"]) == 1
    decision = next(n.id for n in graph.nodes.values() if n.kind == "decision"
                    and "NEEDS_CLARIFICATION" in n.label)
    results = [n for n in graph.nodes.values()
               if n.kind == "result" and n.label_metadata.get("control_transfer") == "return"]
    assert results
    starts = [e.target for e in graph.edges if e.source == decision and e.label == "S\u00ed"]
    reachable = set(starts)
    while starts:
        current = starts.pop()
        for edge in graph.edges:
            if edge.source == current and edge.target not in reachable:
                reachable.add(edge.target)
                starts.append(edge.target)
    assert reachable.intersection(n.id for n in results)
    assert any(e.source == decision and e.label == "No" and
               graph.nodes[e.target].label.startswith("Investigar reuse") for e in graph.edges)
    assert all(any(e.source == n.id for e in graph.edges) for n in results)
    assert all(any(e.target == n.id for e in graph.edges) for n in results)
    assert any(n.kind == "final" for n in graph.nodes.values())


def test_activity_from_pinned_p4_export_and_renderer(tmp_path):
    result = generate_diagram(str(P4), entry=ENTRY, language="es", format="all",
                              renderer="graphviz", output=str(tmp_path))
    assert result["renderer"] == "graphviz"
    for extension in ("mmd", "json", "svg", "png"):
        assert Path(result["files"][extension]).is_file()
    text = Path(result["files"]["mmd"]).read_text(encoding="utf-8")
    assert "(( ))" in text and "((( )))" in text
    assert "NEEDS_CLARIFICATION" in text
    assert "Sí" in text and "No" in text
    graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert any(n["kind"] == "final" for n in graph["nodes"])


def test_single_entry_cli_and_per_type_mcp(tmp_path, capsys, monkeypatch):
    target = tmp_path / "generated"
    assert main(["analyze", str(P4), "--entry", ENTRY, "--diagram-type", "activity",
                 "--language", "es", "--renderer", "graphviz", "--format", "svg",
                 "--output", str(target)]) == 0
    assert "graphviz" in capsys.readouterr().out
    monkeypatch.setenv("PYFLOWMAP_ALLOWED_ROOTS", os.pathsep.join((str(tmp_path.parent), str(P4.parent))))
    generated = generate_activity_diagram(str(P4), entry_point=ENTRY, language="es",
                                           output_path=str(target), renderer="graphviz")
    assert generated["diagram_type"] == "activity"
    assert "NEEDS_CLARIFICATION" in generated["mermaid"]
    with pytest.raises(ValueError, match="outside allowed"):
        generate_activity_diagram(str(tmp_path.parent.parent), output_path=str(target))


def test_other_diagram_types_rejected_explicitly(tmp_path):
    with pytest.raises(ValueError, match="Unsupported diagram type"):
        generate_diagram(str(P4), entry=ENTRY, diagram_type="sequence",
                         output=str(tmp_path))


def test_return_from_inlined_function_reconnects_to_caller(tmp_path):
    (tmp_path / "run.py").write_text(
        "def load(): pass\n"
        "def process(): pass\n"
        "def finish(): pass\n"
        "def stage(flag):\n"
        "    load()\n"
        "    if flag:\n"
        "        return process()\n"
        "    return load()\n"
        "def main():\n"
        "    stage(True)\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("run:main"), max_nodes=15)
    nodes = {n.id: n.label for n in graph.nodes.values()}
    finishes = [key for key, label in nodes.items() if label == "Finish"]
    assert len(finishes) == 1
    ending = finishes[0]
    # The two explicit returns in stage() converge on the caller continuation.
    assert len([edge for edge in graph.edges if edge.target == ending]) == 2


def test_nested_calls_conditional_arguments_and_dynamic_receiver_are_visible(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Request:\n"
        "    @staticmethod\n"
        "    def from_dict(value): return value\n"
        "class Planner:\n"
        "    def plan(self, request): return request\n"
        "def main(coordinator=None):\n"
        "    raw = load() if enabled() else fallback()\n"
        "    request = Request.from_dict(raw)\n"
        "    result = (coordinator or Planner()).plan(request)\n"
        "    return result\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=2, max_nodes=8)

    calls = [node for node in graph.nodes.values()
             if node.label_metadata.get("significant_call")]
    assert any(node.label.endswith(".plan(request)") for node in calls)
    plan = next(node for node in calls if node.label.endswith(".plan(request)"))
    assert plan.label_metadata["call_resolution"] in {"possible", "unresolved"}
    assert plan.locations == ["app.py:9"]
    assert any("from_dict" in node.label_metadata.get("call_expression", "") for node in calls)
    assert any("load" in node.label_metadata.get("call_expression", "") for node in calls)
    assert any("fallback" in node.label_metadata.get("call_expression", "") for node in calls)
    assert any("budget" in warning.lower() for warning in graph.warnings)


def test_resolved_cross_module_call_keeps_target_symbol_and_caller_location(tmp_path):
    (tmp_path / "worker.py").write_text(
        "def execute(value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "entry.py").write_text(
        "from worker import execute\n"
        "def main():\n"
        "    execute(1)\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("entry:main"))

    call = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression") == "execute")
    assert call.label_metadata["call_resolution"] == "resolved"
    assert call.symbols == ["worker:execute"]
    assert call.locations == ["entry.py:3"]


def test_pinned_entrypoint_keeps_plan_call_and_callsite_location():
    with load_project(P4) as project:
        graph = analyze(project, project.entry("planning_entrypoint:main"),
                        max_depth=2, language="es")

    plan = next(node for node in graph.nodes.values()
                if node.label_metadata.get("call_expression", "").endswith(".plan"))
    assert plan.label.startswith("Planificar coordinator")
    assert plan.locations == ["planning_entrypoint.py:12"]
    assert plan.label_metadata["call_resolution"] == "resolved"
    assert plan.label_metadata["resolved_target"] == "planning.coordinator:PlanningCoordinator.plan"


def test_nested_local_function_is_indexed_and_inlined_with_lexical_resolution(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main():\n"
        "    def stage():\n"
        "        analyze()\n"
        "        research()\n"
        "    stage()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        assert "app:main.stage" in project.symbols
        graph = analyze(project, project.entry("app:main"), max_depth=2, max_nodes=8)

    assert any("analyze()" in node.label for node in graph.nodes.values())
    assert any("research()" in node.label for node in graph.nodes.values())


def test_constant_return_values_remain_distinct(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(ok):\n"
        "    if ok:\n"
        "        return 0\n"
        "    return 1\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"))

    results = {node.label for node in graph.nodes.values() if node.kind == "result"}
    assert results == {"Return 0", "Return 1"}


def test_short_circuit_decisions_use_valid_spanish_branch_labels(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(ready, valid):\n"
        "    if ready and valid:\n"
        "        accept()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), language="es")

    decision_ids = {node.id for node in graph.nodes.values() if node.kind == "decision"}
    branch_labels = {edge.label for edge in graph.edges
                     if edge.label and edge.source in decision_ids}
    assert branch_labels <= {"Sí", "No"}
    assert "Sí" in branch_labels
    assert all("Ã" not in edge.label for edge in graph.edges)


def test_state_mutation_in_a_branch_is_not_contracted_away(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(flag, events):\n"
        "    if flag:\n"
        "        events.append('changed')\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=4)

    mutation = next(node for node in graph.nodes.values()
                    if node.label_metadata.get("call_expression", "").endswith("append"))
    decision = next(node for node in graph.nodes.values() if node.kind == "decision")
    assert mutation.locations == ["app.py:3"]
    assert any(edge.source == decision.id and edge.target == mutation.id for edge in graph.edges)
    assert any("budget" in warning.lower() for warning in graph.warnings)


def test_continue_and_break_have_distinct_loop_transitions(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(items):\n"
        "    for item in items:\n"
        "        if should_skip(item):\n"
        "            continue\n"
        "        if should_stop(item):\n"
        "            break\n"
        "        process(item)\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=6)

    decisions = [node for node in graph.nodes.values() if node.kind == "decision"]
    loop = next(node for node in decisions if "More items" in node.label)
    process = next(node for node in graph.nodes.values()
                   if "process" in node.label.lower())
    skip = next(node for node in decisions if "skip" in node.label.lower())
    stop = next(node for node in decisions if "stop" in node.label.lower())
    finish = next(node for node in graph.nodes.values()
                  if "finish" in node.label.lower())
    continue_node = next(node for node in graph.nodes.values()
                         if node.label_metadata.get("control_transfer") == "continue")
    break_node = next(node for node in graph.nodes.values()
                      if node.label_metadata.get("control_transfer") == "break")
    assert any(edge.source == skip.id and edge.target == continue_node.id
               and edge.label == "Yes" for edge in graph.edges)
    assert any(edge.source == continue_node.id and edge.target == loop.id for edge in graph.edges)
    assert any(edge.source == stop.id and edge.target == break_node.id
               and edge.label == "Yes" for edge in graph.edges)
    assert any(edge.source == break_node.id and edge.target == finish.id for edge in graph.edges)
    assert any(edge.target == process.id for edge in graph.edges)
    assert any(edge.source == loop.id and edge.label == "No"
               for edge in graph.edges)


def test_continue_keeps_its_decision_polarity_on_loop_backedge(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(items):\n"
        "    for item in items:\n"
        "        if should_skip(item):\n"
        "            continue\n"
        "        process(item)\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"))

    decision = next(node for node in graph.nodes.values()
                    if node.kind == "decision" and "skip" in node.label.lower())
    loop = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "More items" in node.label)
    continue_node = next(node for node in graph.nodes.values()
                         if node.label_metadata.get("control_transfer") == "continue")
    assert any(edge.source == continue_node.id and edge.target == loop.id
               for edge in graph.edges)
    assert any(edge.source == decision.id and edge.target == continue_node.id
               and edge.label == "Yes" for edge in graph.edges)
    process = next(node for node in graph.nodes.values()
                   if "process" in node.label.lower())
    assert any(edge.source == decision.id and edge.target == process.id
               and edge.label == "No" for edge in graph.edges)


@pytest.mark.parametrize("terminal", ["raise ValueError('bad')", "return 1"])
def test_terminal_branch_does_not_continue_to_following_activity(tmp_path, terminal):
    (tmp_path / "app.py").write_text(
        "def main(flag):\n"
        "    if flag:\n"
        f"        {terminal}\n"
        "    else:\n"
        "        proceed()\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=40)

    terminal_node = next(node for node in graph.nodes.values()
                         if node.label.startswith("Raise" if terminal.startswith("raise")
                                           else "Return 1"))
    finish = next(node for node in graph.nodes.values() if "finish" in node.label.lower())
    assert not any(edge.source == terminal_node.id and edge.target == finish.id
                   for edge in graph.edges)
    assert any(edge.target == finish.id for edge in graph.edges)


def test_raise_inside_expanded_call_does_not_reach_caller_continuation(tmp_path):
    (tmp_path / "app.py").write_text(
        "def guard(flag):\n"
        "    if flag:\n"
        "        raise TypeError('invalid')\n"
        "    inspect()\n"
        "    audit()\n"
        "def main(flag):\n"
        "    guard(flag)\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=2, max_nodes=40)

    raised = next((node for node in graph.nodes.values() if node.label.startswith("Raise")), None)
    assert raised is not None, [
        (node.label, node.label_metadata) for node in graph.nodes.values()
    ]
    finish = next(node for node in graph.nodes.values() if "finish" in node.label.lower())
    assert not any(edge.source == raised.id and edge.target == finish.id for edge in graph.edges)
    assert not any(edge.target == finish.id and edge.source == raised.id for edge in graph.edges)


def test_break_and_continue_inside_expanded_function_keep_their_own_loop(tmp_path):
    (tmp_path / "app.py").write_text(
        "def traverse(items):\n"
        "    for item in items:\n"
        "        if should_skip(item):\n"
        "            continue\n"
        "        if should_stop(item):\n"
        "            break\n"
        "        process(item)\n"
        "    audit()\n"
        "def main(items):\n"
        "    traverse(items)\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=1, max_nodes=40)

    loop = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "More items" in node.label)
    skip = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "should skip" in node.label.lower())
    stop = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "should stop" in node.label.lower())
    audit = next(node for node in graph.nodes.values() if "audit" in node.label.lower())
    process = next(node for node in graph.nodes.values() if "process" in node.label.lower())
    finish = next(node for node in graph.nodes.values() if "finish" in node.label.lower())
    continue_node = next(node for node in graph.nodes.values()
                         if node.label_metadata.get("control_transfer") == "continue")
    break_node = next(node for node in graph.nodes.values()
                      if node.label_metadata.get("control_transfer") == "break")
    assert any(edge.source == skip.id and edge.target == continue_node.id and edge.label == "Yes"
               for edge in graph.edges)
    assert any(edge.source == continue_node.id and edge.target == loop.id for edge in graph.edges)
    assert any(edge.source == stop.id and edge.target == break_node.id and edge.label == "Yes"
               for edge in graph.edges)
    assert any(edge.source == break_node.id and edge.target == audit.id for edge in graph.edges)
    assert any(edge.source == stop.id and edge.target == process.id and edge.label == "No"
               for edge in graph.edges)
    assert any(edge.target == finish.id for edge in graph.edges)


def test_finally_runs_before_break_and_continue_leave_a_branch(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(items):\n"
        "    for item in items:\n"
        "        try:\n"
        "            if should_skip(item):\n"
        "                continue\n"
        "            if should_stop(item):\n"
        "                break\n"
        "            process(item)\n"
        "        finally:\n"
        "            cleanup(item)\n"
        "    after_loop()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=40)

    loop = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "More items" in node.label)
    skip = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "should skip" in node.label.lower())
    stop = next(node for node in graph.nodes.values()
                if node.kind == "decision" and "should stop" in node.label.lower())
    cleanup = [node for node in graph.nodes.values() if "cleanup" in node.label.lower()]
    after = next(node for node in graph.nodes.values()
                 if "after_loop" in node.label.lower())
    transfers = {node.id for node in graph.nodes.values()
                 if node.label_metadata.get("control_transfer") == "continue"}
    breaks = {node.id for node in graph.nodes.values()
              if node.label_metadata.get("control_transfer") == "break"}
    assert any(edge.source == skip.id and edge.target in transfers
               and edge.label == "Yes" for edge in graph.edges)
    assert any(edge.source == stop.id and edge.target in breaks
               and edge.label == "Yes" for edge in graph.edges)
    assert any(edge.source in transfers | breaks and edge.target in {node.id for node in cleanup}
               for edge in graph.edges)
    assert any(edge.source in {node.id for node in cleanup} and edge.target == loop.id
               for edge in graph.edges)
    assert any(edge.source in {node.id for node in cleanup} and edge.target == after.id
               for edge in graph.edges)


@pytest.mark.parametrize("operator", ["and", "or"])
def test_boolean_condition_evaluates_each_effectful_operand_once(tmp_path, operator):
    (tmp_path / "app.py").write_text(
        "def main():\n"
        f"    if first() {operator} second():\n"
        "        accept()\n"
        "    reject()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"))

    calls = [node.label_metadata.get("call_expression") for node in graph.nodes.values()]
    assert calls.count("first") == 1
    assert calls.count("second") == 1
    decisions = [node.label for node in graph.nodes.values() if node.kind == "decision"]
    assert len(decisions) == 2
    assert not any(operator in label for label in decisions)


def test_short_circuit_assignment_preserves_conditional_state_change(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(current):\n"
        "    selected = current or create_default()\n"
        "    use(selected)\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=30)

    assignment = next(node for node in graph.nodes.values()
                     if node.label_metadata.get("assignment") ==
                     "selected = current or create_default()")
    decision = next(node for node in graph.nodes.values() if node.kind == "decision")
    assert assignment.label_metadata["significant_state_change"] is True
    assert any(edge.source == decision.id and edge.target == assignment.id for edge in graph.edges)


def test_conditional_expression_does_not_recheck_its_short_circuit_predicate(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(flag):\n"
        "    value = first() and second() if flag else fallback()\n"
        "    consume(value)\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=30)

    calls = [node.label_metadata.get("call_expression") for node in graph.nodes.values()]
    assert calls.count("first") == calls.count("second") == calls.count("fallback") == 1
    assert sum(node.kind == "decision" for node in graph.nodes.values()) == 2
    assert all("first() and second()" not in node.label for node in graph.nodes.values())


def test_comprehension_predicate_is_summarized_without_fake_single_iteration_branches(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(values):\n"
        "    if any(not valid(value) or should_skip(value) for value in values):\n"
        "        reject()\n"
        "    accept()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_nodes=30)

    summaries = [node for node in graph.nodes.values()
                 if node.label_metadata.get("expression_summary")]
    assert len(summaries) == 1
    assert summaries[0].label_metadata["evaluation_policy"] == "lazy"
    assert {"valid", "should_skip"} <= set(
        summaries[0].label_metadata["contained_call_expressions"]
    )
    assert any("per-item short-circuit" in warning for warning in graph.warnings)


def test_possible_internal_calls_have_independent_navigable_subdiagrams(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Backend:\n"
        "    def execute(self):\n"
        "        return True\n"
        "    def audit(self):\n"
        "        return True\n"
        "class Coordinator:\n"
        "    def __init__(self):\n"
        "        self.backend = Backend()\n"
        "    def dispatch(self):\n"
        "        self.backend.execute()\n"
        "        self.backend.audit()\n"
        "    def main(self):\n"
        "        self.dispatch()\n",
        encoding="utf-8",
    )
    target = tmp_path / "diagrams"
    result = generate_diagram(str(tmp_path), entry="app:Coordinator.main", max_depth=0,
                              format="mmd", output=str(target))

    assert len(result["subdiagrams"]) == 2
    assert all(item["target_symbol"].startswith("app:Backend.")
               for item in result["subdiagrams"])
    assert all(Path(item["files"]["json"]).is_file() for item in result["subdiagrams"])
    index = target / "app_Coordinator_main.subdiagrams" / "index.html"
    assert index.is_file()
    index_text = index.read_text(encoding="utf-8")
    assert "ordering does not imply execution order" in index_text
    assert "Return to main activity" in index_text
    main_graph = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert any(node["label_metadata"].get("subdiagram_index") for node in main_graph["nodes"])


def test_sync_with_models_entry_body_exit_return_raise_and_possible_suppression(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(manager, ok):\n"
        "    with manager as resource:\n"
        "        if ok:\n"
        "            return 1\n"
        "        raise ValueError()\n"
        "    after()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=0)
    entries = [node for node in graph.nodes.values()
               if node.label_metadata.get("context_manager_phase") == "enter"]
    exits = [node for node in graph.nodes.values()
             if node.label_metadata.get("context_manager_phase") == "exit"]
    assert len(entries) == 1 and entries[0].label_metadata["context_manager_method"] == "__enter__"
    assert any(node.label_metadata.get("context_manager_binding") == "resource"
               for node in graph.nodes.values())
    assert {node.label_metadata["pending_outcome"] for node in exits} == {"return", "raise"}
    return_value = next(node for node in graph.nodes.values()
                        if node.label_metadata.get("return_value") == 1)
    returned = next(node for node in graph.nodes.values()
                    if node.label_metadata.get("return_after_context_exit"))
    assert return_value.kind == "activity"
    assert any(edge.source in {node.id for node in exits
                               if node.label_metadata["pending_outcome"] == "return"}
               and edge.target == returned.id for edge in graph.edges)
    suppression = [node for node in graph.nodes.values()
                   if node.label_metadata.get("context_manager_suppression") == "unknown"]
    # A body exception may be suppressed; an exception raised by __exit__ is a
    # separate possible exception and may itself replace the pending outcome.
    assert len(suppression) >= 1
    decision = suppression[0]
    assert {edge.label for edge in graph.edges if edge.source == decision.id} == {"Yes", "No"}
    after = next(node for node in graph.nodes.values() if node.label_metadata.get("call_expression", "").startswith("after"))
    assert any(edge.source == decision.id and edge.label == "Yes" and edge.target == after.id
               for edge in graph.edges)
    assert any("suppression behavior is dynamic" in warning for warning in graph.warnings)


def test_async_with_marks_async_enter_and_exit_without_assuming_suppression(tmp_path):
    (tmp_path / "app.py").write_text(
        "async def main(manager):\n"
        "    async with manager:\n"
        "        await work()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=0)
    phases = [node for node in graph.nodes.values()
              if node.label_metadata.get("context_manager_phase")]
    assert {node.label_metadata["context_manager_phase"] for node in phases} == {"enter", "exit"}
    assert all(node.label_metadata["async"] for node in phases)
    assert {node.label_metadata["context_manager_method"] for node in phases} == {
        "__aenter__", "__aexit__"}


def test_generic_context_and_call_labels_are_spanish_without_domain_rules(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(manager):\n"
        "    with manager:\n"
        "        unexplained_operation()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=0, language="es")
    labels = [node.label for node in graph.nodes.values()]
    assert "Entrar en gestor de contexto" in labels
    assert "Salir del gestor de contexto" in labels
    assert any(label.startswith("Invocar unexplained_operation") for label in labels)


def test_nested_context_managers_exit_in_reverse_order_before_loop_control(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(first, manager, second):\n"
        "    while first:\n"
        "        with manager, second:\n"
        "            if first:\n"
        "                continue\n"
        "            break\n"
        "    after()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        graph = analyze(project, project.entry("app:main"), max_depth=0)
    exits = [node for node in graph.nodes.values()
             if node.label_metadata.get("context_manager_phase") == "exit"]
    for outcome in ("break", "continue"):
        chain = [node for node in exits if node.label_metadata["pending_outcome"] == outcome]
        assert {node.label_metadata["context_expression"] for node in chain} == {"manager", "second"}
        inner = next(node for node in chain if node.label_metadata["context_expression"] == "second")
        outer = next(node for node in chain if node.label_metadata["context_expression"] == "manager")
        assert any(edge.source == inner.id and edge.target == outer.id for edge in graph.edges)
    loop_decision = next(node for node in graph.nodes.values()
                         if node.label_metadata.get("loop_kind") == "while")
    outer_continue_exit = next(node for node in exits
                               if node.label_metadata["pending_outcome"] == "continue"
                               and node.label_metadata["context_expression"] == "manager")
    assert any(edge.source == outer_continue_exit.id and edge.target == loop_decision.id
               for edge in graph.edges)


def test_hierarchical_view_keeps_branching_in_child_activity_and_links_back(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Backend:\n"
        "    def execute(self): pass\n"
        "    def audit(self): pass\n"
        "class Coordinator:\n"
        "    def __init__(self): self.backend = Backend()\n"
        "    def dispatch(self, mode):\n"
        "        if mode == 'execute': self.backend.execute()\n"
        "        else: self.backend.audit()\n"
        "    def main(self, mode): self.dispatch(mode)\n",
        encoding="utf-8",
    )
    output = tmp_path / "diagrams"
    result = generate_diagram(str(tmp_path), entry="app:Coordinator.main", max_depth=0,
                              view="hierarchical", format="all", renderer="graphviz",
                              output=str(output))
    assert result["diagram_type"] == "activity-hierarchy"
    details = [item for item in result["subdiagrams"]
               if item["kind"] == "full-detail activity"]
    assert result["hierarchy_root_symbol"] == "app:Coordinator.dispatch"
    assert details
    outline = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert len([node for node in outline["nodes"] if node["kind"] == "decision"]) == 1
    assert any(node["label_metadata"].get("summarized_call_count") == 1
               for node in outline["nodes"])
    index = output / "app_Coordinator_main.subdiagrams" / "index.html"
    content = index.read_text(encoding="utf-8")
    assert "Return to main activity" in content
    assert "full-detail activity" in content
    for item in result["subdiagrams"]:
        for extension in ("svg", "png", "json", "mmd"):
            target = index.parent / f"{item['id']}.{extension}"
            assert target.is_file()
            assert f'href="{item["id"]}.{extension}"' in content
    back = index.parent / "../app_Coordinator_main.svg"
    assert back.resolve() == Path(result["files"]["svg"]).resolve()
    assert back.is_file()


def test_hierarchical_outline_keeps_predicates_and_calls_in_their_branches(tmp_path):
    (tmp_path / "app.py").write_text(
        "def main(mode):\n"
        "    if mode == 'a':\n"
        "        analyze()\n"
        "    else:\n"
        "        validate()\n"
        "    finish()\n",
        encoding="utf-8",
    )
    with load_project(tmp_path) as project:
        outline = build_hierarchical_outline(project.entry("app:main"), language="es")
    decision = next(node for node in outline.nodes.values() if node.kind == "decision")
    assert decision.label.startswith("¿mode == 'a'?")
    actions = [node for node in outline.nodes.values() if node.label_metadata.get("phase_summary")]
    branch_calls = [node for node in actions
                    if any(ref["expression"] in {"analyze", "validate"}
                           for ref in node.label_metadata["source_references"])]
    assert len(branch_calls) == 2
    assert {edge.label for edge in outline.edges if edge.source == decision.id} == {"Sí", "No"}
    assert all(node.locations for node in branch_calls)
    assert all(node.label_metadata["detail_symbol"] == "app:main" for node in branch_calls)


def test_mcp_exposes_hierarchical_view_with_format_appropriate_links(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(
        "class Backend:\n"
        "    def execute(self): pass\n"
        "    def audit(self): pass\n"
        "class Coordinator:\n"
        "    def __init__(self): self.backend = Backend()\n"
        "    def dispatch(self, mode):\n"
        "        if mode: self.backend.execute()\n"
        "        else: self.backend.audit()\n"
        "    def main(self, mode): self.dispatch(mode)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYFLOWMAP_ALLOWED_ROOTS", str(tmp_path))
    output = tmp_path / "mcp-output"
    result = generate_activity_diagram(
        str(tmp_path), entry_point="app:Coordinator.main", output_path=str(output),
        format="mmd", view="hierarchical")
    assert result["diagram_type"] == "activity-hierarchy"
    assert result["hierarchy_root_symbol"] == "app:Coordinator.main"
    index = output / "app_Coordinator_main.subdiagrams" / "index.html"
    content = index.read_text(encoding="utf-8")
    assert (output / "app_Coordinator_main.mmd").is_file()
    assert 'href="../app_Coordinator_main.mmd"' in content
    assert ".svg\">SVG" not in content and ".png\">PNG" not in content
