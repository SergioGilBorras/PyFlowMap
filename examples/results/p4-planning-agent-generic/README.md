# P4 Planning Agent: generic labeling regression

This is a **read-only test case**, not a P4 customization. It pins source code from
`SergioGilBorras/P4-Planning-Agent` to commit
`8e68c720bef75e24acd6b3ed8a237b41fa3a838d`.

Generated with:

```bash
pyflowmap analyze tests/fixtures/references/p4-planning-agent-v1 \
  --entry planning.coordinator:PlanningCoordinator.plan \
  --language es --format all --renderer graphviz \
  --output examples/results/p4-planning-agent-generic
```

The `.mmd`/`.json`/`.svg` files are machine-generated. Their labels now come from a
**generic** action-verb vocabulary, CamelCase/snake_case decomposition, and optional
docstrings. There are **no mappings for `RequirementAnalysisAgent`, P4, or any status
literal**. Decisions show the actual predicate and preserve true → Sí, false → No.

The limitation is intentional and visible: unknown nouns from class names are not
translated to Spanish (`Analizar requirement`, `Investigar reuse`). Fully natural
language would require a general translation/LLM stage, not repository-specific
exceptions. All source symbols are retained exactly in the JSON output.

The earlier `p4-planning-agent-v1-1` example remains as historical output for
before/after comparison; do not treat it as the current label-generation behavior.
