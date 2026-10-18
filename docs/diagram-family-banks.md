# Diagram family-specific validation

The reference activity corpus still contains 81 independent tests. The extra
[focused bank](../benchmark/diagram-families/README.md) adds seven curated
small examples **per family** and checks the supported UML semantics with
precise source-backed relationship expectations.

Run `python scripts/validate_diagram_families.py` after installing
PyFlowMap and Graphviz. The resulting timestamped local gallery offers separate
activity/class/package sections, an SVG/PNG preview for every rendered example,
JSON evidence and editable sources. For each package case, modern and strict
visual styles are both generated and must produce identical graph models.

No Codex is called and the source is never imported or executed. Classifiers
or packages without evidence-backed connectors remain isolated: this is an
important correctness regression. The prior 81-case activity bank is retained
without reclassification.
