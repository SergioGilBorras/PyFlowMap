"""P4 labels may be corrected only from unambiguous, verified source tokens."""

from types import SimpleNamespace

import pytest

from pyflowmap.semantic.contracts import LabelRequest
from pyflowmap.semantic.p4_provider import (
    P4SemanticLabelProvider,
    _close_verified_literal_quote,
)


@pytest.mark.parametrize(
    ("label", "expression", "expected", "changed"),
    [
        ("Call emit with the literal argument 'halt", "emit('halt')",
         "Call emit with the literal argument 'halt'", True),
        ("Call emit with the literal argument 'unreadable", "emit('unreadable')",
         "Call emit with the literal argument 'unreadable'", True),
        ('Call emit with the argument "halt', 'emit("halt")',
         'Call emit with the argument "halt"', True),
        ("Call emit with the literal argument 'halt'", "emit('halt')",
         "Call emit with the literal argument 'halt'", False),
        ("Call emit with the literal argument 'stop", "emit('halt')",
         "Call emit with the literal argument 'stop", False),
        ('Call RuntimeError with literal argument "missing',
         "RuntimeError('missing')",
         'Call RuntimeError with literal argument "missing"', True),
        ("Call RuntimeError with literal argument 'missing",
         'RuntimeError("missing")',
         "Call RuntimeError with literal argument 'missing'", True),
        ('Call RuntimeError with literal argument "missing_other',
         "RuntimeError('missing')",
         'Call RuntimeError with literal argument "missing_other', False),
        ("Call emit with the literal argument 'halt", "emit('halt', key=1)",
         "Call emit with the literal argument 'halt", False),
        ("Call emit with tuple 'north_east", "emit(('north_east', 1, 2))",
         "Call emit with tuple 'north_east", False),
        ("Call emit with literal 'halt", None,
         "Call emit with literal 'halt", False),
    ],
)
def test_source_literal_quote_correction_is_conservative(
    label, expression, expected, changed
):
    assert _close_verified_literal_quote(label, expression) == (expected, changed)


def test_real_provider_literal_correction_is_audited():
    raw = "Call emit with the literal argument 'halt"

    class StubCodex:
        def generate_label(self, **_kwargs):
            return SimpleNamespace(
                label=raw, char_count=len(raw), provider="codex",
                warnings=[], language="en", style="neutral", output_type="title",
            )

    request = LabelRequest(
        node_id="n14", current_label="Emit",
        symbols=("signal:emit",), filename="signal.py", language="en",
        docstring=None, source_snippet="def emit(code):\n    return code",
        preceding=(), following=(), call_site_expression="emit('halt')",
    )
    provider = P4SemanticLabelProvider(provider="codex", tools=StubCodex())
    result = provider.label(request)
    assert result.label == "Call emit with the literal argument 'halt'"
    assert result.char_count == len(result.label)
    assert result.provider == "codex"
    assert result.warnings == ("pyflowmap_source_literal_quote_closed",)
