"""Deterministic Mermaid serializer for FlowGraph."""

from html import escape

from .diagrams.activity_labels import source_caption
from .models import FlowGraph


def _safe(text: str) -> str:
    return escape(text.replace("\n", " ").replace("\r", " "), quote=True)


def to_mermaid(graph: FlowGraph, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    # The bigger base font also benefits Yes/No edge labels. Keep edge labels
    # as Mermaid text, and rely on the layout engine for their placement.
    lines = [
        ('%%{init: {"theme": "base", "themeVariables": '
         '{"fontSize": "18px", "edgeLabelBackground": "#ffffff"}}}%%'),
        f"flowchart {direction}",
    ]
    for node in graph.nodes.values():
        label = _safe(node.label)
        if node.kind == "initial":
            lines.append(f"    {node.id}(( ))")
            lines.append(f"    style {node.id} fill:#000000,stroke:#000000,color:#000000")
        elif node.kind == "final":
            lines.append(f"    {node.id}((( )))")
            lines.append(f"    style {node.id} fill:#000000,stroke:#000000,color:#000000")
        elif node.kind == "decision":
            lines.append(f'    {node.id}{{"{label}"}}')
        else:
            caption = source_caption(node)
            if caption:
                label += f'<br/><small>{_safe(caption)}</small>'
            lines.append(f'    {node.id}["{label}"]')
    for edge in graph.edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_safe(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")
    return "\n".join(lines) + "\n"
