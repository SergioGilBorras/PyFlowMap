"""Activity diagram orchestration (other UML diagram families are separate)."""

from ..analysis import FlowBuilder, simplify
from ..models import FlowGraph
from ..project import ProjectIndex, Symbol


def analyze(project: ProjectIndex, entry: Symbol, *, max_nodes: int = 8,
            max_depth: int = 2, language: str = "en") -> FlowGraph:
    return simplify(FlowBuilder(project, max_depth=max_depth, language=language).build(entry),
                    max_nodes=max_nodes)
