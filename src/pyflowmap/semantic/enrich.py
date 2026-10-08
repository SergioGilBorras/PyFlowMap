"""Enrich labels without modifying activity nodes, topology, or symbol provenance."""

import ast
import re

from ..models import FlowGraph
from ..project import ProjectIndex
from .contracts import LabelRequest, SemanticLabelProvider

MAX_SOURCE_CHARS = 3000
MAX_DOCSTRING_CHARS = 350
MAX_LABEL_CHARS = 80
MAX_CONTEXT_ITEMS = 3


def _source(index: ProjectIndex, symbol_id: str) -> tuple[str, str | None, str]:
    symbol = index.symbols.get(symbol_id)
    if symbol is None:
        return "", None, ""
    source_path = (index.root / symbol.path).resolve()
    if not source_path.is_relative_to(index.root) or not source_path.is_file():
        return symbol.path, None, ""
    try:
        text = source_path.read_text(encoding="utf-8-sig")
    except (UnicodeError, OSError):
        return symbol.path, ast.get_docstring(symbol.node), ""
    snippet = ast.get_source_segment(text, symbol.node) or ""
    return symbol.path, (ast.get_docstring(symbol.node) or "")[:MAX_DOCSTRING_CHARS] or None, snippet[:MAX_SOURCE_CHARS]


def _valid_label(label: object) -> bool:
    return (isinstance(label, str) and 0 < len(label.strip()) <= MAX_LABEL_CHARS
            and "\n" not in label and "\r" not in label
            and not any(ord(char) < 32 for char in label)
            and not re.search(r"[<>]", label))


def enrich_activity_labels(graph: FlowGraph, index: ProjectIndex,
                           provider: SemanticLabelProvider, language: str) -> None:
    """Call provider only for resolved activities; preserve decisions/merges/edges.

    User project code is sent to the provider only when explicitly passed in by
    the caller. A remote provider may transmit that code externally.
    """
    for node in graph.nodes.values():
        if node.kind != "activity" or not node.symbols:
            continue
        known = [key for key in node.symbols if key in index.symbols]
        if not known:
            continue
        # Neighbors are context hints only, never commands to alter connectivity.
        before = tuple(graph.nodes[e.source].label for e in graph.edges
                       if e.target == node.id and e.source in graph.nodes)[:MAX_CONTEXT_ITEMS]
        after = tuple(graph.nodes[e.target].label for e in graph.edges
                      if e.source == node.id and e.target in graph.nodes)[:MAX_CONTEXT_ITEMS]
        filename, docstring, source = _source(index, known[0])
        request = LabelRequest(
            node_id=node.id, current_label=node.label, symbols=tuple(node.symbols),
            filename=filename, language=language, docstring=docstring,
            source_snippet=source, preceding=before, following=after,
        )
        try:
            candidate = provider.label(request)
        except Exception as exc:
            graph.warnings.append(f"Semantic label unavailable for {node.id}: {type(exc).__name__}")
            continue
        if candidate is None:
            continue
        if not _valid_label(candidate):
            graph.warnings.append(f"Rejected invalid semantic label for {node.id}")
            continue
        node.label = candidate.strip()
        node.label_source = "external"
