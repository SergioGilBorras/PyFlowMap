"""Stable intermediate graph shared by the CLI, renderers, and MCP server."""

from dataclasses import asdict, dataclass, field


@dataclass
class Node:
    id: str
    label: str
    kind: str = "activity"
    symbols: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass
class FlowGraph:
    entry: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, label: str, kind: str = "activity", symbol: str = "", location: str = "") -> str:
        identifier = f"n{len(self.nodes) + 1}"
        self.nodes[identifier] = Node(
            id=identifier,
            label=label,
            kind=kind,
            symbols=[symbol] if symbol else [],
            locations=[location] if location else [],
        )
        return identifier

    def connect(self, source: str, target: str, label: str = "") -> None:
        if not any(e.source == source and e.target == target and e.label == label for e in self.edges):
            self.edges.append(Edge(source, target, label))

    def to_dict(self) -> dict:
        return {
            "entry": self.entry,
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
            "warnings": self.warnings,
        }
