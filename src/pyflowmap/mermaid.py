"""Deterministic Mermaid serializer for FlowGraph."""

from html import escape

from .models import FlowGraph


def _safe(text: str) -> str:
    return escape(text.replace("\n", " ").replace("\r", " "), quote=True)


def to_mermaid(graph: FlowGraph, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    lines = [f"flowchart {direction}"]
    for node in graph.nodes.values():
        label = _safe(node.label)
        if node.kind == "decision":
            lines.append(f'    {node.id}{{"{label}"}}')
        else:
            lines.append(f'    {node.id}["{label}"]')
    for edge in graph.edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_safe(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")
    return "\n".join(lines) + "\n"
