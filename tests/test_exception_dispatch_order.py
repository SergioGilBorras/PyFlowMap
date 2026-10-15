from __future__ import annotations

from pathlib import Path

from pyflowmap.diagrams.activity import analyze
from pyflowmap.project import load_project


def _analyze(tmp_path: Path, source: str):
    module = tmp_path / "dispatch_case.py"
    module.write_text(source, encoding="utf-8")
    with load_project(tmp_path) as project:
        return analyze(project, project.entry("dispatch_case:run"), max_nodes=100)


def _reachable_without(graph, start: str, target: str, forbidden: set[str]) -> bool:
    adjacency: dict[str, list[str]] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)
    pending = [start]
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in visited or node in forbidden:
            continue
        visited.add(node)
        pending.extend(adjacency.get(node, ()))
    return False


def test_except_star_dispatch_requires_an_exception_from_its_try_body(tmp_path):
    graph = _analyze(tmp_path, """def run():
    try:
        raise sentinel
    except* ValueError:
        recover()
""")

    raise_nodes = {
        node.id for node in graph.nodes.values()
        if node.label_metadata.get("control_transfer") == "raise"
        and node.label_metadata.get("exception_origin") != "except_star_remainder"
    }
    handlers = {
        node.id for node in graph.nodes.values()
        if node.label_metadata.get("exception_route") == "caught_subgroup"
    }
    assert raise_nodes
    assert handlers
    assert not any(
        _reachable_without(graph, next(n.id for n in graph.nodes.values()
                                       if n.kind == "initial"), handler, raise_nodes)
        for handler in handlers
    ), "except* handler is reachable without executing the try body's raise"


def test_regular_except_dispatch_requires_an_exception_from_its_try_body(tmp_path):
    graph = _analyze(tmp_path, """def run():
    try:
        raise sentinel
    except ValueError:
        recover()
""")

    raise_nodes = {
        node.id for node in graph.nodes.values()
        if node.label_metadata.get("control_transfer") == "raise"
    }
    handlers = {
        node.id for node in graph.nodes.values()
        if node.label_metadata.get("exception_route") == "caught"
    }
    assert raise_nodes and handlers
    assert not any(
        _reachable_without(graph, next(n.id for n in graph.nodes.values()
                                       if n.kind == "initial"), handler, raise_nodes)
        for handler in handlers
    ), "except handler is reachable without executing the try body's raise"
