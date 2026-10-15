"""Bridge PyFlowMap's immutable activity requests to P4-Semantic-Labeler v0.1.0."""

import ast
import logging
import time

from ..integrations.semantic_labeler_tools import SemanticLabelerTools
from .contracts import LabelRequest, SemanticLabelOutcome

LOGGER = logging.getLogger(__name__)
CODEX_TIMEOUT_RETRY_DELAY_SECONDS = 2


def _close_verified_literal_quote(
    label: str, expression: str | None
) -> tuple[str, bool]:
    """Close one missing final quote only when confirmed by the source AST.

    Avoid rewriting arbitrary model output or inferring values. The source
    call must have exactly one positional string literal and no keywords.
    """
    if not expression:
        return label, False
    try:
        parsed = ast.parse(expression, mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        return label, False
    if (not isinstance(parsed, ast.Call) or len(parsed.args) != 1
            or parsed.keywords or not isinstance(parsed.args[0], ast.Constant)
            or not isinstance(parsed.args[0].value, str)):
        return label, False
    literal = ast.get_source_segment(expression, parsed.args[0])
    if (not literal or len(literal) < 2 or literal[0] not in ("'", '"')
            or literal[-1] != literal[0]
            or literal.startswith(literal[0] * 3)):
        return label, False
    if label.endswith(literal[:-1]) and not label.endswith(literal):
        return label + literal[-1], True
    # ast.unparse normalizes quote style: source code using "missing" can
    # become RuntimeError('missing') in the call-site expression. A model
    # can quote the same AST-verified string with either convention.
    value = parsed.args[0].value
    for quote in ("'", '"'):
        if (quote not in value and not any(ord(char) < 32 for char in value)
                and label.endswith(quote + value)):
            return label + quote, True
    return label, False


class P4SemanticLabelProvider:
    """Enrich graph labels using P4's library, never altering topology."""

    def __init__(self, *, provider: str, max_chars: int = 70, style: str = "neutral",
                 reduction_attempts: int = 1,
                 tools: SemanticLabelerTools | None = None):
        if provider not in ("mock", "codex"):
            raise ValueError("P4 semantic provider must be mock or codex (explicit opt-in)")
        if not 1 <= max_chars <= 80:
            raise ValueError("Semantic label max_chars must be 1..80 for activity diagrams")
        self.provider = provider
        self.tools = tools or SemanticLabelerTools(
            provider=provider, reduction_attempts=reduction_attempts)
        self.max_chars = max_chars
        self.style = style

    def label(self, request: LabelRequest) -> SemanticLabelOutcome:
        full = request.symbols[0]
        module, sep, qualified = full.partition(":")
        name = qualified or full
        owner, dot, _method = name.rpartition(".")

        # The actual subject is this node's action, not its containing function.
        # Function source/docstrings are only contextual evidence.
        action = (f"Call {request.call_site_expression}"
                  if request.call_site_expression else request.current_label.strip()[:200])
        retries_used = 0
        for attempt in range(2 if self.provider == "codex" else 1):
            try:
                result = self.tools.generate_label(
                    name=action,
                    kind="activity",
                    module=module if sep else None,
                    class_name=owner if dot else None,
                    documentation=request.docstring,
                    source_code=request.source_snippet,
                    text=("Label the specific existing graph activity: " + action
                          + ". If this is a call, preserve the call-site purpose "
                          "and distinguish literal arguments in each execution "
                          "branch. The enclosing function is context, not the "
                          "operation to label. Do not infer runtime values."),
                    before="; ".join(request.preceding) or None,
                    after="; ".join(request.following) or None,
                    purpose=("Provide a faithful caption for ONE static-flow node, "
                             "not a summary of the enclosing function. Preserve "
                             "conditions, uncertainty, and the exact action."),
                    language=request.language, style=self.style, max_chars=self.max_chars,
                )
                break
            except Exception as exc:  # Never log source excerpts or private context.
                if (self.provider == "codex" and attempt == 0
                        and type(exc).__name__ == "ProviderTimeout"):
                    retries_used = 1
                    LOGGER.warning(
                        "Codex labeling timed out; retrying once in %ss",
                        CODEX_TIMEOUT_RETRY_DELAY_SECONDS,
                    )
                    time.sleep(CODEX_TIMEOUT_RETRY_DELAY_SECONDS)
                    continue
                raise RuntimeError(
                    f"P4 semantic labeling failed ({type(exc).__name__})"
                ) from exc

        if len(result.label) > self.max_chars or result.char_count != len(result.label):
            raise ValueError("P4 semantic label violated the configured length limit")
        # Narrow, source-verified typographic correction: never invent text.
        # Preserve an explicit audit warning for review of the Codex output.
        label, quote_closed = _close_verified_literal_quote(
            result.label, request.call_site_expression,
        )
        if len(label) > self.max_chars:
            raise ValueError("Corrected semantic label exceeds the configured limit")
        return SemanticLabelOutcome(
            label=label, provider=result.provider,
            warnings=(tuple(result.warnings)
                      + (("pyflowmap_codex_timeout_retried",) if retries_used else ())
                      + (("pyflowmap_source_literal_quote_closed",)
                         if quote_closed else ())),
            char_count=len(label), output_type=result.output_type,
            language=result.language, style=result.style,
        )
