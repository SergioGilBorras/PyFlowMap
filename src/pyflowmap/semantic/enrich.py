"""Enrich labels without modifying activity nodes, topology, or symbol provenance."""

import ast
import re

from ..models import FlowGraph, Node
from ..project import ProjectIndex
from .contracts import LabelRequest, SemanticLabelOutcome, SemanticLabelProvider

MAX_SOURCE_CHARS = 3000
MAX_DOCSTRING_CHARS = 350
MAX_LABEL_CHARS = 80
MAX_CONTEXT_ITEMS = 3
MAX_CALL_SITE_CHARS = 180
MAX_CALL_SITE_FILE_BYTES = 512_000


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


def _call_site_expression(index: ProjectIndex, node: Node) -> str | None:
    """Read a matching call AST at this node's original source line, without executing it.

    Refuse ambiguous multi-call sites rather than attributing the wrong
    arguments to an activity. The result is a bounded source expression.
    """
    called = node.label_metadata.get("call_expression")
    if not isinstance(called, str) or not called:
        return None
    for location in node.locations:
        file_name, sep, line_text = location.rpartition(":")
        if not sep or not line_text.isdecimal():
            continue
        path = (index.root / file_name).resolve()
        if not path.is_relative_to(index.root) or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_CALL_SITE_FILE_BYTES:
                continue
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
            target_line = int(line_text)
            calls = [
                ast.unparse(call)
                for call in ast.walk(tree)
                if isinstance(call, ast.Call)
                and call.lineno == target_line
                and ast.unparse(call.func) == called
            ]
        except (OSError, UnicodeError, SyntaxError, ValueError, RecursionError):
            continue
        if len(calls) == 1 and len(calls[0]) <= MAX_CALL_SITE_CHARS:
            return calls[0]
    return None


def _invalid_label_reason(label: object) -> str | None:
    """Validate labels while allowing ordinary comparisons, never markup."""
    if not isinstance(label, str):
        return "non_string"
    if not label.strip():
        return "empty"
    if len(label.strip()) > MAX_LABEL_CHARS:
        return "length_limit"
    if "\n" in label or "\r" in label:
        return "multiline"
    if any(ord(char) < 32 or ord(char) == 127 for char in label):
        return "control_character"
    # Renderers escape "<" and ">" for Mermaid and Graphviz. A tag-like
    # prefix is still refused (including <script> and closing tags).
    if re.search(r"<[A-Za-z!/]", label):
        return "possible_markup"
    return None


def _valid_label(label: object) -> bool:
    return _invalid_label_reason(label) is None


def enrich_activity_labels(graph: FlowGraph, index: ProjectIndex,
                           provider: SemanticLabelProvider, language: str, *,
                           strict: bool = False) -> None:
    """Change activity labels only. Provider errors propagate if strict=True.

    In explicit P4 provider mode, warn/return fake success is prohibited.
    User-supplied Python providers use a documented best-effort fallback.
    """
    reported_provider_warnings: set[str] = set()
    for node in graph.nodes.values():
        if node.kind != "activity" or not node.symbols:
            continue
        # Protect transfer semantics during exception/finally unwinding.
        # In particular, an activity tagged pending_control_transfer="return"
        # must retain its return value; a model can otherwise relabel the
        # duplicated pending returns as the shared finally-body call.
        if ("control_transfer" in node.label_metadata
                or "pending_control_transfer" in node.label_metadata
                or "generator_event" in node.label_metadata):
            continue
        known = [key for key in node.symbols if key in index.symbols]
        if not known:
            continue
        before = tuple(graph.nodes[e.source].label for e in graph.edges
                       if e.target == node.id and e.source in graph.nodes)[:MAX_CONTEXT_ITEMS]
        after = tuple(graph.nodes[e.target].label for e in graph.edges
                      if e.source == node.id and e.target in graph.nodes)[:MAX_CONTEXT_ITEMS]
        filename, docstring, source = _source(index, known[0])
        request = LabelRequest(
            node_id=node.id, current_label=node.label, symbols=tuple(node.symbols),
            filename=filename, language=language, docstring=docstring,
            source_snippet=source, preceding=before, following=after,
            call_site_expression=_call_site_expression(index, node),
        )
        try:
            candidate = provider.label(request)
        except Exception as exc:  # Best-effort fallback for custom Python providers.
            if strict:
                raise
            graph.warnings.append(f"Semantic label unavailable for {node.id}: {type(exc).__name__}")
            continue
        if candidate is None:
            continue
        outcome = candidate if isinstance(candidate, SemanticLabelOutcome) else None
        label = outcome.label if outcome else candidate
        issue = _invalid_label_reason(label)
        if issue is not None:
            if strict:
                raise ValueError(
                    f"Invalid external semantic label for {node.id} ({issue})"
                )
            graph.warnings.append(
                f"Rejected invalid semantic label for {node.id} ({issue})"
            )
            continue
        node.label = label.strip()
        node.label_source = "external"
        if outcome:
            # Preserve analysis metadata (resolution, source expressions,
            # control transfers, provenance, etc.). Provider details have a
            # separate namespace and cannot overwrite those semantics.
            node.label_metadata = {
                **node.label_metadata,
                "external_label": {
                "provider": outcome.provider, "char_count": outcome.char_count,
                "language": outcome.language, "style": outcome.style,
                "output_type": outcome.output_type, "warnings": list(outcome.warnings),
                "call_site_expression": request.call_site_expression,
                },
            }
            for warning in outcome.warnings:
                # Keep the graph warning list useful for large diagrams. The
                # same provider warning is reported once globally; its exact
                # per-node scope remains available in label_metadata.
                if warning not in reported_provider_warnings:
                    graph.warnings.append(f"Semantic provider warning: {warning}")
                    reported_provider_warnings.add(warning)
