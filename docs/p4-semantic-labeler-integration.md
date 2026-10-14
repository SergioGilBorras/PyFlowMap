# P4-Semantic-Labeler integration

P4-Semantic-Labeler is an **optional external Python library** for enriching
existing activity labels. It is not required for static analysis, is not
embedded into PyFlowMap and never builds or changes the control-flow graph.

The integration targets the library's tagged API `v0.1.0` in the private
GitHub repository `SergioGilBorras/P4-Semantic-Labeler`. Installation of
optional extras requires Git access to that repository.

## Install an optional provider

From the PyFlowMap checkout:

```bash
python -m pip install -e '.[labeler]'
python -m pip check
```

For **real Codex inference**, install the dedicated extra, authenticate and
make an explicit provider selection:

```bash
python -m pip install -e '.[labeler-codex]'
codex login
pyflowmap analyze ./project --entry app:main --semantic-provider codex --format mmd
```

**Only use the real provider when code transmission and the associated cost
have been approved.** Merely installing an extra never authorizes inference.
PyFlowMap defaults to `--semantic-provider disabled`.

## Test the integration without inference

```bash
pyflowmap analyze ./project --entry app:main --semantic-provider mock --semantic-max-chars 70 --format mmd
```

Mock output is synthetic and must not be described as semantically validated.
The optional labeler is never necessary for `inspect`, deterministic analysis,
or rendering.

## Python API

```python
from pyflowmap.integrations.semantic_labeler_tools import SemanticLabelerTools

tools = SemanticLabelerTools(provider="mock")
result = tools.generate_label(
    name="validate_record",
    kind="function",
    documentation="Check an input record before saving it.",
    language="en",
    style="neutral",
    max_chars=70,
)
print(result.label)
```

The adapter also supports summary requests, async requests and batch labeling
through the same external library interface. A separate HTTP service or
additional MCP server is not required. The existing PyFlowMap MCP tools can
accept the optional semantic-provider parameters.

## Data boundaries

For eligible, statically resolved activity nodes, PyFlowMap can pass:

- The source symbol and module/class name.
- Up to 350 characters of docstring.
- Up to 3,000 characters of selected source code.
- The current label and up to three nearby activity labels on either side.
- Language, output style and character budget.

The adapter can replace the **activity label text** and record label metadata
and warnings. It cannot alter decision predicates, symbols, locations, edge
routing, node identities or topology.

The optional provider may fail; an explicit failure must be visible rather
than silently reported as successful semantic labeling. Source comments
and docstrings are input data and must never be treated as model commands.

## Verification status

Tests with `disabled` and `mock` establish structural invariance of the
integration, not the quality or availability of the real remote provider.
Actual Codex inference must be assessed separately in an authorized
environment on suitable examples before being advertised as verified.

See [semantic labeling](semantic-labeling.md) for the general contract.
