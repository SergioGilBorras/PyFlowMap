# Deterministic extraction and simplification rules (V1)

1. **Entry**: use explicit `MODULE:METHOD` if given. Otherwise select a unique top-level `main`; if none, accept a unique public function/method. Multiple candidates raise an actionable error.
2. **Scope**: restrict entry candidates to a file/subfolder. External symbols can be looked up across the project.
3. **Call resolution**: resolve local functions, simple `from module import fn`, class methods accessed via `self`, and local objects assigned `ClassName()`; unresolved calls are still shown by their surface name unless filtered as noise.
4. **Order**: walk statements sequentially; `if` produces `Yes/No` paths; loops get an explicit loop decision, `Next` edge and `No` exit. Simple returns terminate the current path.
5. **Expansion**: inline an internal callee only if it looks like an orchestrator (multiple top-level calls or branching), is below the depth limit, and is not recursive. Leaf calls become a single activity labeled by the method/function name.
6. **Noise**: common built-ins, container operations, logging, and simple utility calls are hidden by a fixed, documented filter. This is intentionally imperfect and will be refined through fixtures.
7. **Budget**: merge adjacent activity nodes *only* when the edge is unlabelled and neither has other predecessors/successors. Preserve decision nodes and branch edges, even when the resulting diagram exceeds `max_nodes`.
8. **Labels**: deterministic humanization of snake_case/CamelCase identifiers; optional AI labels are deferred to a separate stage.
9. **Warnings**: unsupported constructs such as `match/case` and approximate exception flow produce warnings in both the JSON graph and command result.

## Known blind spots

- Dynamic call targets (`getattr`, monkeypatching, dependency injection), subclass dispatch, relative imports and lambda/higher-order calls.
- Assignment tracking is local and simple, not a whole-program type system.
- Comprehension internals, expression-level short circuiting, `break` and `continue` are not modeled exactly.
- Complex `try/except/finally` paths are approximated.

Please judge outputs against curated ideal diagrams (semantic faithfulness, readability and preserved decisions), not only Mermaid syntax validity.
