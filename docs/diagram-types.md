# Diagram types and views

## Currently supported

PyFlowMap analyzes Python statically and supports three independent families:
**activity/flow**, selected by `--diagram-type activity` (the default), and
**UML class declarations**, selected by `--diagram-type class`, and
**UML package structure**, selected by `--diagram-type package`.
Activity and class export Mermaid/JSON and optional SVG/PNG. Packages export
DOT/JSON and optional SVG/PNG because Mermaid does not support fully compliant
UML package symbols. See [UML classes](uml-classes.md) and
[UML packages](uml-packages.md).

Within that family, `--view` offers different **presentations**:

| View | What it represents | What it does not assert |
| --- | --- | --- |
| `detailed` | Source-linked operations and possible control-flow paths | A particular runtime path |
| `hierarchical` | Navigable phases and linked detailed activity subdiagrams | That hidden details do not matter |
| `overview` | Possible local calls and process-level organization (`process-summary`) | UML activity semantics or unconditional call order |

`overview` is **not another UML diagram type**. It is a high-level
call outline. Use the detailed diagram and provenance JSON for predicate,
exception and branch evidence.

```bash
pyflowmap analyze ./project --entry app:main --diagram-type activity --view detailed --format all --renderer graphviz
pyflowmap analyze ./project --entry app:main --view hierarchical --format images --renderer graphviz
pyflowmap analyze ./project --entry app:main --view overview --format mmd
```

Other values of `--diagram-type` are **not supported** and must fail clearly;
they must never be silently substituted with an activity graph. For `class` and `package`,
`--entry` is not needed and activity-specific `--view` and Codex labeling are
not available. Package diagrams require `--format all` or `--format dot`
(not Mermaid).

## Possible future diagram families

Ideas for future development, **not currently available as commands**:

| Family | Potential AST evidence | Important limitation |
| --- | --- | --- |
| Component | Imports, exposed interfaces, configuration | Conceptual boundaries are heuristic |
| Sequence | Selected call sites and possible ordering | Dynamic dispatch, branching and async |
| State | Explicit state fields and transitions | Not reliably inferable in arbitrary Python |

These are future proposals, not implemented by the class analyzer.

Any future family should use its own intermediate representation and
serializer rather than forcing class/package/state semantics into the
activity `FlowGraph`. It must preserve file/line/symbol provenance, report
uncertainty, and be covered by reviewed generic regressions.

See [architecture](architecture.md) and [static analysis limits](analysis-rules.md).
