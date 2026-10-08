"""Presentation-only activity captions; source symbol IDs remain unmodified."""

from ..models import Node


def ellipsize(value: str, limit: int = 43) -> str:
    """Shorten a *display* label without changing the underlying symbol identity."""
    if limit < 2:
        raise ValueError("limit must be at least 2")
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def source_caption(node: Node, limit: int = 43) -> str | None:
    """Show a class.method, or module.function, for action nodes only.

    The original fully-qualified IDs stay in node.symbols and the JSON output.
    The first recorded symbol represents the first operation in grouped nodes;
    subsequent symbols are counted rather than quietly discarded.
    """
    if node.kind != "activity" or not node.symbols:
        return None
    first = node.symbols[0]
    module, sep, name = first.partition(":")
    if not sep:
        name = first
    if "." not in name:
        name = f"{module}.{name}" if sep and module else name
    count = len(node.symbols)
    suffix = f" (+{count - 1})" if count > 1 else ""
    return f"({ellipsize(name, limit - len(suffix))}{suffix})"
