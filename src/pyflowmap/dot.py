"""Pure DOT exporter so SVG/PNG can be rendered without Mermaid CLI."""

from html import escape

from .diagrams.activity_labels import source_caption
from .models import FlowGraph


def _quoted(label: str) -> str:
    return '"' + label.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _action_label(description: str, source: str | None) -> str:
    # Graphviz HTML labels let the secondary source reference use a smaller font.
    title = escape(description, quote=True)
    if not source:
        return f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2"><TR><TD><B>{title}</B></TD></TR></TABLE>>'
    sub = escape(source, quote=True)
    return (
        '< <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">'
        f'<TR><TD><B>{title}</B></TD></TR>'
        f'<TR><TD><FONT POINT-SIZE="10" COLOR="#64748b">{sub}</FONT></TD></TR>'
        '</TABLE> >'
    )


def to_dot(graph: FlowGraph, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    lines = ["digraph activity {", f"  rankdir={'TB' if direction == 'TD' else 'LR'};",
             '  graph [bgcolor="white", nodesep=0.65, ranksep=0.8, pad=0.22];',
             '  node [fontname="Arial", fontsize=13, color="#333333", margin="0.14,0.10"];',
             '  edge [fontname="Arial", fontsize=14, color="#475569", fontcolor="#1e293b", arrowsize=0.8];']
    for n in graph.nodes.values():
        if n.kind == "initial":
            attrs = 'shape=circle, label="", width=0.18, fixedsize=true, style=filled, fillcolor=black, color=black'
        elif n.kind == "final":
            attrs = 'shape=doublecircle, label="", width=0.25, fixedsize=true, style=filled, fillcolor=black, color=black'
        elif n.kind == "decision":
            attrs = f'shape=diamond, label={_quoted(n.label)}, style=filled, fillcolor="#fff7e6"'
        else:
            attrs = ('shape=box, style="rounded,filled", fillcolor="#f1f5f9", '
                     f'label={_action_label(n.label, source_caption(n))}')
        lines.append(f"  {n.id} [{attrs}];")
    for edge in graph.edges:
        # Head labels are offset away from the arrow tip rather than sitting
        # directly on the line. Graphviz recognizes labelangle/labeldistance.
        title = (f" [headlabel={_quoted(edge.label)}, labelfontsize=14, "
                 'labeldistance=2.6, labelangle=25]') if edge.label else ""
        lines.append(f"  {edge.source} -> {edge.target}{title};")
    lines.append("}")
    return "\n".join(lines) + "\n"
