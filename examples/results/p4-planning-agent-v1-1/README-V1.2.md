# P4-Planning-Agent diagram — presentation iteration V1.2

Source repository **not modified**: `SergioGilBorras/P4-Planning-Agent` at pinned commit `8e68c720bef75e24acd6b3ed8a237b41fa3a838d`.

Entry: `planning.coordinator:PlanningCoordinator.plan` (language `es`, max_nodes 8).

Changes over V1.1:

1. Activity titles use larger, bold text.
2. A smaller, muted line below each activity shows the source class/method, with ellipsis for long captions.
3. `Sí` and `No` labels use larger fonts and are set off from the arrow tip in Graphviz.
4. Existing UML-like initial, shared result, and activity final remain unchanged.

- `coordinator_activity_v1_2.mmd`: source Mermaid.
- `coordinator_activity_v1_2.svg`: rendered by Graphviz from the same graph.
- Graph source IDs remain complete in `coordinator_activity_v1_2.json`; truncation applies only to the display.

Mermaid CLI image rendering has **not** been visually verified in this environment (no `mmdc`). Graphviz SVG/PNG render output has been verified.

Human-readable labels remain deterministic; no model inference is integrated in this iteration.
