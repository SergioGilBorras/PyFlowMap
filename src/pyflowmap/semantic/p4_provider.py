"""Bridge PyFlowMap's immutable activity requests to P4-Semantic-Labeler v0.1.0."""

from ..integrations.semantic_labeler_tools import SemanticLabelerTools
from .contracts import LabelRequest, SemanticLabelOutcome


class P4SemanticLabelProvider:
    """Enrich graph labels using P4's published library, never altering topology."""

    def __init__(self, *, provider: str, max_chars: int = 70, style: str = "neutral",
                 reduction_attempts: int = 1,
                 tools: SemanticLabelerTools | None = None):
        if provider not in ("mock", "codex"):
            raise ValueError("P4 semantic provider must be mock or codex (explicit opt-in)")
        if not 1 <= max_chars <= 80:
            raise ValueError("Semantic label max_chars must be 1..80 for activity diagrams")
        self.tools = tools or SemanticLabelerTools(
            provider=provider, reduction_attempts=reduction_attempts)
        self.max_chars = max_chars
        self.style = style

    def label(self, request: LabelRequest) -> SemanticLabelOutcome:
        full = request.symbols[0]
        module, sep, qualified = full.partition(":")
        name = qualified or full
        owner, dot, _method = name.rpartition(".")
        try:
            # P4 labels SUBJECTS. Using the containing function as the
            # subject encourages it to summarize the *whole function* for
            # every activity node, even unrelated statements. The actual
            # subject must be the individual deterministic activity.
            action = request.current_label.strip()[:200]
            result = self.tools.generate_label(
                name=action,
                kind="activity",
                module=module if sep else None,
                class_name=owner if dot else None,
                documentation=request.docstring,
                source_code=request.source_snippet,
                text=("Label the specific existing graph activity: " + action
                      + ". Use the surrounding source as context only."),
                before="; ".join(request.preceding) or None,
                after="; ".join(request.following) or None,
                purpose=("Provide a faithful caption for ONE static-flow node, "
                         "not a summary of the enclosing function. Preserve "
                         "conditions, uncertainty, and the exact action."),
                language=request.language, style=self.style, max_chars=self.max_chars,
            )
        except Exception as exc:  # surface provider failure without private context
            raise RuntimeError(f"P4 semantic labeling failed ({type(exc).__name__})") from exc
        if len(result.label) > self.max_chars or result.char_count != len(result.label):
            raise ValueError("P4 semantic label violated the configured length limit")
        return SemanticLabelOutcome(
            label=result.label, provider=result.provider, warnings=tuple(result.warnings),
            char_count=result.char_count, output_type=result.output_type,
            language=result.language, style=result.style,
        )
