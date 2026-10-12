"""Optional P4 labeler integration demo (mock: NO Codex inference)."""

from pyflowmap.integrations.semantic_labeler_tools import SemanticLabelerTools


def main():
    # Requires: pip install -e '.[labeler]'
    labeler = SemanticLabelerTools(provider="mock", reduction_attempts=0)
    title = labeler.generate_label(
        name="process_pending_orders", kind="function",
        documentation="Validate pending orders and prepare dispatch.",
        max_chars=50, language="es", style="formal",
    )
    summary = labeler.generate_summary(
        name="process_pending_orders", kind="function",
        documentation="Validate pending orders and prepare dispatch.",
        max_chars=140, language="es", style="academic",
    )
    print(title.model_dump())
    print(summary.model_dump())
    # mock_provider warns about its synthetic formatting; it is not AI.


if __name__ == "__main__":
    main()
