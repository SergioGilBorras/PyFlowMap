# Roadmap

## V1 — executable preview
- [x] Local directory, .py file and ZIP inputs
- [x] Inspect entry candidates and select a method/function
- [x] AST-based lightweight flow extraction for conditionals and loops
- [x] Conservative diagram simplification with provenance
- [x] `.mmd` and `.json` outputs; optional SVG/PNG through Mermaid CLI
- [x] CLI and local stdio MCP tools
- [x] Regression fixture tests and GitHub Actions

## V1.x — more faithful flow selection
- [ ] Improve cross-module and relative-import resolution
- [ ] Branch handling for `break`, `continue`, `match` and exceptions
- [ ] Fixture-based comparisons against hand-curated ideal diagrams
- [ ] Configurable call/noise inclusion filters and humanized labels
- [ ] Structural grouping with real subgraphs, rather than only linear merging

## V2 — integration and semantic enhancement
- [ ] Direct GitHub repository source selection with branch/commit options
- [ ] Class collaboration and project overview modes
- [ ] Optional LLM-generated **labels only**, never unconstrained edges
- [ ] MCP resource exposure of rendered diagrams
- [ ] Remote MCP transport with authentication and explicit workspace policies
