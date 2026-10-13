"""Readable process-level call outline derived from the detailed activity graph."""

from collections import deque

from .models import FlowGraph


def function_overview(graph: FlowGraph) -> FlowGraph:
    """Build a call outline and explicit subprocess summaries, not fake branches.

    The overview is intentionally a process summary, not an activity diagram:
    its edges show statically observed call nesting. Detailed decisions,
    branches, and their source locations remain in the detailed graph and in
    the omitted-node trace attached to the summary's final node.
    """
    result = FlowGraph(entry=graph.entry, warnings=list(graph.warnings))
    start = result.add("", "initial")
    calls = [node for node in graph.nodes.values()
             if node.label_metadata.get("significant_call")]
    by_caller: dict[str, list] = {}
    for node in calls:
        caller = node.label_metadata.get("caller_symbol")
        target = node.label_metadata.get("resolved_target")
        targets = [target] if target else node.label_metadata.get("possible_targets", [])
        if caller and targets:
            by_caller.setdefault(caller, []).append((node, targets))

    # Stop at the nearest bounded subprocess whose static call list identifies
    # collaborator work. This produces a compact path through the entry's
    # actual invocation boundaries while retaining the subordinate call sites.
    queue = deque([(graph.entry, [])])
    visited: set[str] = set()
    selected: list = []
    while queue:
        symbol, path = queue.popleft()
        if symbol in visited:
            continue
        visited.add(symbol)
        if path:
            candidate = path[-1][0]
            contained = candidate.label_metadata.get("subprocess_calls", [])
            if any(item["expression"].startswith("self.") for item in contained):
                selected = path
                break
        for call_node, targets in sorted(
                by_caller.get(symbol, []),
                key=lambda item: (item[0].locations[0] if item[0].locations else "", item[0].id)):
            for target in targets:
                if target not in visited:
                    queue.append((target, [*path, (call_node, target)]))

    if not selected:
        # Projects without a bounded subprocess still get a traceable entry
        # call outline. Keep only the direct statically observed calls.
        selected = [(node, target) for node, targets in by_caller.get(graph.entry, [])
                    for target in targets]

    previous = start
    for source_node, target in selected:
        step = result.add(source_node.label, "activity")
        node = result.nodes[step]
        node.symbols = list(dict.fromkeys([*source_node.symbols, target]))
        node.locations = list(source_node.locations)
        node.label_source = source_node.label_source
        node.label_metadata = {
            **source_node.label_metadata,
            "overview_source_nodes": [source_node.id],
            "overview_abstraction": "statically observed call boundary",
            "process_target": target,
        }
        # Keep bounded subprocess call inventories legible in the compact
        # process outline. These are source-derived call sites, not new steps.
        for heading, summary in (("\nPossible internal calls: ", "Calls found in source:"),
                                 ("\nLlamadas internas posibles: ",
                                  "Llamadas detectadas en el código:")):
            if heading in node.label:
                title, calls = node.label.split(heading, 1)
                node.label = title + "\n" + summary + "\n" + calls.replace("; ", "\n")
                break
        result.connect(previous, step, "invokes")
        previous = step

    final = result.add("", "final")
    result.connect(previous, final)
    represented = {source_node.id for source_node, _ in selected}
    result.nodes[final].label_metadata.update({
        "overview_source_graph_entry": graph.entry,
        "overview_source_node_ids": [
            node.id for node in graph.nodes.values() if node.id not in represented
        ],
        "overview_source_graph_reference": "the detailed graph JSON generated for the same entry",
    })
    result.warnings.append(
        "This is a process-level call outline, not a UML activity diagram. Edges show "
        "statically observed invocation nesting. Internal control-flow branches are "
        "summarized in the detailed diagram; the final node retains their provenance."
    )
    return result
