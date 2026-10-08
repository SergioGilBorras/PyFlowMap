# Roadmap

## V1 — executable preview
- [x] Local directory, .py file and ZIP inputs
- [x] Inspect entry candidates and select a method/function
- [x] AST-based lightweight flow extraction for conditionals and loops
- [x] Conservative diagram simplification with provenance
- [x] `.mmd` and `.json` outputs; optional SVG/PNG through Mermaid CLI
- [x] CLI and local stdio MCP tools
- [x] Regression fixture tests and GitHub Actions

## V1.1 — UML-inspired activity diagrams (current priority)
- [ ] Add UML-style initial (filled circle) and activity-final (bullseye) nodes
- [ ] Correct decision guard polarity and make Yes/No labels match the actual predicate
- [ ] Merge equivalent terminal outcomes with a single shared end, preserving path semantics
- [ ] Improve semantic action/decision labels without fabricating paths
- [ ] Keep read-only P4-Planning-Agent as an acceptance/regression test, comparing generated diagrams with reviewed references

## V1.x — more faithful flow selection
- [ ] Improve cross-module and relative-import resolution
- [ ] Branch handling for `break`, `continue`, `match` and exceptions
- [ ] Fixture-based comparisons against hand-curated ideal diagrams
- [ ] Configurable call/noise inclusion filters and humanized labels
- [ ] Structural grouping with real subgraphs, rather than only linear merging

## V2 — selectable diagram types (not yet implemented)
- [ ] Introduce explicit `diagram_type` to the service, CLI and MCP API (default: `activity`)
- [ ] Add class diagrams from class definitions, inheritance, attributes and high-confidence associations
- [ ] Add package/module dependency diagrams from imports, with boundaries/filters
- [ ] Explore component diagrams from project modules and exposed interfaces (often approximate rather than strict UML)
- [ ] Dispatch renderers by diagram type; keep source references and confidence/warnings
- [ ] Reject unsupported types explicitly; do not silently produce an activity diagram in their place

## V3 — deeper behavioral diagrams (subject to feasibility)
- [ ] Sequence diagrams for a selected entry point when call ordering and participants can be resolved
- [ ] State-machine diagrams only where states/transitions are expressed clearly in code or annotations
- [ ] Optional non-UML data/pipeline diagrams for projects that benefit from them
- [ ] Explicitly report dynamic-dispatch, asynchronous and reflection limitations
- [ ] Keep the user's chosen scope, max detail and output format across diagram types

See [diagram types](diagram-types.md) for requirements and implementation constraints.

## V2 — integration and semantic enhancement
- [ ] Direct GitHub repository source selection with branch/commit options
- [ ] Class collaboration and project overview modes
- [ ] Optional LLM-generated **labels only**, never unconstrained edges
- [ ] MCP resource exposure of rendered diagrams
- [ ] Remote MCP transport with authentication and explicit workspace policies
