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

## Activity labels and rendering (V1.2)

- The first line of each action is its **human-readable activity label**. The engine uses a **generic method-name vocabulary** plus the class name and, when available, an explicit method docstring. There are **no overrides for any particular repository, class or project status**. **No LLM or AI translation is integrated yet.** Unknown domain nouns remain in the source language; `--language es` translates only commonly recognized action verbs and generic control labels. A fully natural multilingual label will need an optional semantic language model or another general translation backend.
- The second line shows `(Class.method)` or `(module.function)` as a smaller source reference. Long captions are visually truncated with `…`. The JSON always keeps full `symbols` and `locations` unchanged.
- For grouped activities, the caption names the first mapped symbol and adds the number of additional symbols. Refer to the JSON for the complete set.
- Graphviz SVG/PNG uses HTML-like labels with a smaller gray second line. Graphviz `headlabel`, `labeldistance` and `labelfontsize` position decision labels away from the arrow tips and enlarge them. Mermaid text uses a line break with `<small>` and an 18 px base font; exact placement is renderer-dependent.
- Future optional LLM labels should be constrained to names/descriptions of graph nodes; **never** add, delete or reverse edges. Record both original and proposed labels with provenance and a no-AI fallback.
