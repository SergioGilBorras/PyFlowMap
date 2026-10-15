# Independent diagram-family banks (offline)

This focused bank **complements**, never replaces, the existing 81-case
activity regression corpus. It has 21 small Python fixtures, seven each for
activity, UML class and UML package diagrams. Each model is checked against
source-derived oracles. No Codex, network inference, consumer metadata or
execution of the analyzed source is required.

| Family | Coverage |
|---|---|
| Activity (7) | branches, loops, exceptions/finally, match guards, async, generators, local calls |
| Class (7) | single/multiple inheritance, annotated dependencies, visibility, abstraction, independent classes, unknown ancestor |
| Package (7) | relative/cross imports, cycles, nested packages, external imports, independent packages, display capitalization |

Every package case is exported with **both modern and strict**; only the
rendering style may differ. UML IDs, dependencies and evidence must be identical.
Absence of relations in specifically independent test cases is intentional.

From project root with Graphviz installed:

```powershell
.\.venv\Scripts\python.exe scripts\validate_diagram_families.py
```

The script writes a *new* dated folder in output_graphs with a local index.html,
three separated diagram-family directories and shared CSS/report JSON. SVG, PNG
and editable Mermaid/DOT are included. No historical output is deleted.

Static structural PASS does not imply full UML 2.5.1 or runtime correctness,
and visual font/layout differences can be influenced by Graphviz versions.
