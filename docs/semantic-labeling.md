# Semantic labeling contract (optional, generic)

## Scope

PyFlowMap extracts flow **deterministically**. A SemanticLabelProvider may change
only a textual activity label; it cannot add/delete steps, flip decision guards
or modify edges. Nothing depends on Codex, external APIs, agent runtimes or a
particular domain. External calls require explicit opt-in: either passing a Python provider or selecting `mock` / `codex` via CLI, service or MCP. `disabled` remains the default.

## What to send, and why

A symbol name alone is often insufficient: `run`, `process`, `handle`, `plan`
may mean different things in different classes and projects. The adapter
receives one `LabelRequest` containing:

- `current_label`, exact `symbols`, and the source `filename`.
- `source_snippet`: AST-targeted implementation up to 3,000 characters.
- `docstring`: up to 350 characters when available.
- `preceding` / `following`: up to three labels each, for local context.
- `language`: requested output language.

Prefer a short verb + object phrase ('Validate request', 'Guardar resultados'),
not a name-only translation. Keep class.method in the secondary caption, separate
from the new label. A future version may supply a minimal caller excerpt and
use a hash-based cache; do not send entire repositories by default.

## Contract

```python
from pyflowmap.semantic import LabelRequest, SemanticLabelProvider

class CodexLabeler:
    def __init__(self, wrapper):
        self.wrapper = wrapper

    def label(self, request: LabelRequest) -> str | None:
        # Adapt the wrapper to your model's API / prompting mechanism.
        # Return ONLY a text label. No new diagram nodes or connections.
        return None
```

Pass an instance as `label_provider=` to `pyflowmap.service.generate_diagram`.
Use a local Python adapter first; **no microservice is needed**. When later
serving a remote client, a provider process/API might be useful for isolation,
resource limits or shared caching, but is not part of this feature.

The service rejects blank/multiline, too-long or HTML-like labels and falls
back on deterministic text if a provider raises an exception. Each JSON node
reports `label_source` as `deterministic` or `external`.

## Safety

Source code and docstrings are untrusted input, not instructions for the
labeler. Explicitly constrain any Codex prompt to output text describing
existing code, never follow instructions found inside the code. Review privacy
policies before sending proprietary code to an external service. Do not expose
secrets, `.env`, repositories or source excerpts as public MCP resources.

## Published P4-Semantic-Labeler adapter

PyFlowMap now offers a dedicated optional adapter for the externally installed
`P4-Semantic-Labeler` **v0.1.0** Python package, supporting `disabled` (default),
`mock` (no AI), and `codex` (explicit opt-in). Library, CLI, and existing MCP
interfaces select this provider without a separate service. The library's output
metadata and warnings are preserved. See [installation and usage](p4-semantic-labeler-integration.md).

## Integration roadmap

1. Test label-provider quality on fixed snapshots with a curated baseline.
2. [x] Use the published P4-Semantic-Labeler Python library behind the same protocol (no wrapper in PyFlowMap).
3. [x] Add explicit CLI/MCP provider opt-in and configurable style/char limits. Future: cache.
4. Consider an independent service only if multiple clients need it.
