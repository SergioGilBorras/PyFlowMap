"""Pure DOT exporter so SVG/PNG can be rendered without Mermaid CLI."""

from .models import FlowGraph


def _quoted(label: str) -> str:
    return '"' + label.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def to_dot(graph: FlowGraph, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    lines = ["digraph activity {", f"  rankdir={'TB' if direction == 'TD' else 'LR'};",
             '  graph [bgcolor="white"];',
             '  node [fontname="Arial", fontsize=11, color="#333333"];',
             '  edge [fontname="Arial", fontsize=10];']
    for n in graph.nodes.values():
        if n.kind == "initial":
            attrs = 'shape=circle, label="", width=0.18, fixedsize=true, style=filled, fillcolor=black, color=black'
        elif n.kind == "final":
            attrs = 'shape=doublecircle, label="", width=0.25, fixedsize=true, style=filled, fillcolor=black, color=black'
        elif n.kind == "decision":
            attrs = f'shape=diamond, label={_quoted(n.label)}, style=filled, fillcolor="#fff7e6"'
        else:
            attrs = f'shape=box, style="rounded,filled", fillcolor="#f1f5f9", label={_quoted(n.label)}'
        lines.append(f"  {n.id} [{attrs}];")
    for edge in graph.edges:
        title = f" [label={_quoted(edge.label)}]" if edge.label else ""
        lines.append(f"  {edge.source} -> {edge.target}{title};")
    lines.append("}")
    return "\n".join(lines) + "\n"
