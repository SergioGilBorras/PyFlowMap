# P4-Semantic-Labeler v0.1.0 integration

PyFlowMap uses **the external published Python library**, not a copied algorithm,
HTTP microservice, MCP bridge or Codex wrapper. The package is available from the
private GitHub repository `SergioGilBorras/P4-Semantic-Labeler` at tag `v0.1.0`.

## Installation (Git access to the private repository is required)

Install PyFlowMap's optional extra from your PyFlowMap checkout:

```bash
python -m pip install -e '.[labeler]'
python -m pip check
```

For Codex support, which includes P4's `codex` extra:

```bash
python -m pip install -e '.[labeler-codex]'
python -m pip check
codex login
```

The pinned underlying dependency is:

```text
p4-semantic-labeler[codex] @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@v0.1.0
```

This is a Git URL, **not** a PyPI publication. Installation also fetches the
version-pinned dependencies of P4-Semantic-Labeler. CI in this repository does
not access another private GitHub repository: adapter tests use public-API-shaped
doubles. Execute an optional real mock-provider smoke test in a trusted Git-
connected environment to validate packaging and dependency resolution.

## Default is offline; opt into a provider

Without any option PyFlowMap uses deterministic AST-derived labels only.

```bash
# No inference, including if Codex has previously been authenticated:
pyflowmap analyze ./project --entry module:main --format images

# Integration smoke test WITHOUT real model inference:
pyflowmap analyze ./project --entry module:main \
  --semantic-provider mock --semantic-style neutral \
  --semantic-max-chars 70 --format images

# Explicit real Codex use: only after authorizing transmission of the code
# snippets to the model and running codex login:
pyflowmap analyze ./project --entry module:main \
  --semantic-provider codex --semantic-style technical \
  --semantic-max-chars 70 --format images
```

The same optional arguments are accepted by PyFlowMap's existing
`generate_diagram` and `generate_activity_diagram` MCP tools. No new server is
created. The Codex CLI and its required authentication are external dependencies;
**PyFlowMap never runs Codex by default**, and CI never runs Codex.

## Python adapter API

```python
from pyflowmap.integrations.semantic_labeler_tools import (
    SemanticLabelerTools,
    generate_label,
    generate_summary,
    agenerate_label,
    generate_labels_batch,
)

# The mock provider returns synthetic name formatting, NOT true AI semantics.
tools = SemanticLabelerTools(provider="mock", reduction_attempts=0)
title = tools.generate_label(
    name="process_pending_orders", kind="function",
    documentation="Validate orders and prepare delivery.",
    language="es", style="formal", max_chars=48,
)
summary = tools.generate_summary(
    name="process_pending_orders", kind="function",
    source_code="def process_pending_orders(...): ...",
    language="es", style="academic", max_chars=120,
)
print(title.label, title.model_dump())
print(summary.label, summary.warnings)
```

Call `await tools.agenerate_label(...)` inside async applications. For batches
use `tools.generate_labels_batch([{...}, {...}])`, or
`await tools.agenerate_labels_batch([...])` inside an event loop. The original
P4 `LabelResult` / `BatchResult` is returned with full metadata and per-item
errors; no caller must guess whether output was truncated or synthetic.

## Diagram-level use (library)

```python
from pyflowmap.service import generate_diagram

output = generate_diagram(
    "./project", entry="module:main", semantic_provider="mock",
    semantic_style="neutral", semantic_max_chars=70, format="images"
)
print(output["warnings"])
```

Only **existing activity nodes** with statically resolved symbols are sent for
enrichment. The labeler sees the unmodified symbol name, optional class/module,
first 350 docstring characters, at most 3,000 source characters for the selected
method, current description, and up to three preceding/following step labels.
Source code is never executed by PyFlowMap. Labeler access to private code must
be explicitly authorized before choosing `codex`.

The original `symbols` and `locations` remain intact in JSON; the `label_metadata`
field on each enriched node stores `provider`, `char_count`, `language`, `style`,
`output_type`, and `warnings`. Warnings, including
`output_truncated: meaning may be incomplete`, are also surfaced in the result's
root-level `warnings` list. The `mock_provider` warning means an example label
is not an AI-semantic interpretation.

P4 provider failures in explicit mock/codex mode raise an error rather than
claiming a fallback label was produced. The existing custom injected
`label_provider=` protocol remains backward-compatible and best-effort.

## Current bounds

- PyFlowMap activity-node labels are limited to 80 characters, with a configurable
  P4 `max_chars` of 1–80. Separate standalone summary calls may use longer limits
  within P4's configured maximum.
- Models cannot change edges, predicates, topology or source provenance.
- No HTTP calls, no new MCP service, and no inference during ordinary analysis.
- Python 3.11+ is required; to use Codex the Codex CLI must be installed and
  authenticated, and the user must explicitly select `semantic_provider=codex`.
- `SemanticLabelerTools.generate_label()` is synchronous; use `agenerate_label()`
  inside async event loops. Batch APIs preserve individual errors from P4.
