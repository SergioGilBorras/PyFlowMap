from __future__ import annotations
"""Dependency-free interface to plug a local wrapper or external label provider."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LabelRequest:
    """Read-only, bounded context for ONE existing activity node."""

    node_id: str
    current_label: str
    symbols: tuple[str, ...]
    filename: str
    language: str
    docstring: str | None
    source_snippet: str
    preceding: tuple[str, ...]
    following: tuple[str, ...]


class SemanticLabelProvider(Protocol):
    """Implement with any local library, Codex wrapper, LLM or offline model.

    Return a human-readable *label only*, or None to keep deterministic text.
    The provider never receives a mutable FlowGraph and cannot change edges.
    """

    def label(self, request: LabelRequest) -> str | SemanticLabelOutcome | None: ...


@dataclass(frozen=True)
class SemanticLabelOutcome:
    """Presentation metadata returned by an external labeling library."""

    label: str
    provider: str
    warnings: tuple[str, ...] = ()
    char_count: int = 0
    output_type: str = "title"
    language: str = "es"
    style: str = "neutral"
