# Optional semantic labeling

The PyFlowMap analyzer is deterministic. **Label enrichment changes text,
not flow.** It must not add/delete nodes or edges, reverse guards, change
source provenance, or claim that opaque dynamic behavior was observed.

## Provider choices

| Provider | Behavior | External inference |
| --- | --- | --- |
| `disabled` (default) | Deterministic AST-derived labels | None |
| `mock` | Synthetic labels to test the integration | None |
| `codex` | P4-Semantic-Labeler using authenticated Codex CLI | Explicit opt-in; selected source excerpts may leave the local machine |

The optional package comes from a separately maintained private Git
repository. The normal PyFlowMap installation and activity extraction
must not depend on Codex.

## Context and safety

When enrichment is explicitly requested, a provider receives a bounded
`LabelRequest` with the existing activity label, source symbols/filename,
a selected code excerpt (up to 3,000 characters), docstring (up to 350
characters), language, and up to three neighboring labels per side.

The source under analysis is untrusted data, **not instructions** to a
model. Avoid supplying secrets or confidential source to external models.
Enable real-provider inference only after authorization for the precise
source and any associated usage cost.

The core label validation rejects empty, multiline, HTML-like and
excessively long activity labels. Accepted labels keep the original
source identifiers in graph metadata and add provenance for the label
source. The external P4 adapter returns provider metadata and warnings.

## Developer API

Applications may supply a custom object implementing
`pyflowmap.semantic.SemanticLabelProvider` through
`generate_diagram(..., label_provider=provider)`. This is an optional
extension point, not a requirement for ordinary CLI or MCP use.

```python
from pyflowmap.service import generate_diagram

result = generate_diagram(
    "./project",
    entry="app:main",
    semantic_provider="disabled",
    format="mmd",
)
print(result["warnings"])
```

`mock` exercises the external integration pathway but does not establish
semantic fidelity. Quality should be evaluated independently for
faithfulness to the source, helpfulness, absence of invented intent,
brevity and structural invariance.

## Error behavior

Explicit provider failures must not be reported as successful labeling.
When the code falls back to deterministic labels for a custom optional
provider, the warning must make that fallback visible. Neither failure
mode is permitted to mutate graph structure.

See [P4-Semantic-Labeler integration](p4-semantic-labeler-integration.md).
