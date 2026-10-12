"""Generic function-level abstraction for readable activity-flow overviews."""

from collections import defaultdict

from .models import FlowGraph, Node


def function_overview(graph: FlowGraph) -> FlowGraph:
    """Group internal nodes by source symbol while retaining observed boundaries.

    Edges crossing source-symbol groups remain explicit, including their
    original branch labels. Decisions and edges internal to a symbol group are
    abstracted; the returned warning makes that scope visible and the detailed
    graph remains available.
    """
    if not graph.nodes:
        return FlowGraph(entry=graph.entry, warnings=list(graph.warnings))

    def symbol_group(node: Node) -> tuple[str, ...]:
        if node.symbols:
            return ("symbol", *node.symbols)
        return ("unattributed", node.id)

    groups = {node_id: symbol_group(node) for node_id, node in graph.nodes.items()}
    def key(node_id: str) -> tuple[str, ...]:
        node = graph.nodes[node_id]
        if node.kind in {"initial", "final", "result"}:
            return ("node", node_id)
        return groups[node_id]

    warnings = [
        f"Detailed view: {warning[5:]}" if warning.startswith("Kept ") else warning
        for warning in graph.warnings
    ]
    result = FlowGraph(entry=graph.entry, warnings=warnings)
    output_ids: dict[tuple[str, ...], str] = {}
    grouped_nodes: dict[tuple[str, ...], list[Node]] = defaultdict(list)
    for node_id, node in graph.nodes.items():
        grouped_nodes[key(node_id)].append(node)

    for group_key, members in grouped_nodes.items():
        if group_key[0] == "node":
            member = members[0]
            new_id = result.add(member.label, member.kind)
            result.nodes[new_id].symbols = list(member.symbols)
            result.nodes[new_id].locations = list(member.locations)
            result.nodes[new_id].label_source = member.label_source
            result.nodes[new_id].label_metadata = {
                **member.label_metadata,
                "overview_source_nodes": [member.id],
            }
        else:
            symbols = list(dict.fromkeys(symbol for member in members for symbol in member.symbols))
            locations = list(dict.fromkeys(location for member in members for location in member.locations))
            if group_key[0] == "symbol":
                label = symbols[0].rsplit(":", 1)[-1]
            else:
                label = members[0].label or "Unattributed activity"
            new_id = result.add(label, "activity")
            result.nodes[new_id].symbols = symbols
            result.nodes[new_id].locations = locations
            result.nodes[new_id].label_source = "source-symbol overview"
            result.nodes[new_id].label_metadata = {
                "overview_source_nodes": [member.id for member in members],
                "overview_abstraction": "internal control flow grouped by source symbol",
            }
        output_ids[group_key] = new_id

    for edge in graph.edges:
        source, target = output_ids[key(edge.source)], output_ids[key(edge.target)]
        if source != target:
            result.connect(source, target, edge.label)

    result.warnings.append(
        "Function overview groups internal control flow by source symbol; "
        "branch labels show observed cross-function outcomes. Use the detailed "
        "diagram for decisions and paths inside each function."
    )
    return result
