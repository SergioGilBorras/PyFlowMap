# Diagram types — design roadmap

PyFlowMap currently supports **only simplified activity/flow diagrams** in Mermaid flowchart syntax. Future support will be selected explicitly via `--diagram-type` (CLI), `diagram_type` (service), and the same parameter in MCP. An unsupported type **must fail clearly**; it must not be replaced silently with another diagram.

## Candidate diagram types

| Proposed type | Purpose | Extractable evidence | Priority | Caveat |
| --- | --- | --- | --- | --- |
| `activity` | Main stages, decision paths, returns | AST, control flow, calls | V1 / V1.1 | UML-style notation approximated with Mermaid flowcharts |
| `class` | Key classes and relationships | AST classes, inheritance, constructors, annotations | V2 | Associations may be uncertain |
| `package` | Module/package dependencies | Imports and package paths | V2 | Dynamic imports may be invisible |
| `component` | Architectural components and interfaces | Modules, exports, dependencies, config hints | V2 exploration | High-level grouping is heuristic; may not be formally UML-compliant |
| `sequence` | Order of calls between participants | Entry-scoped interprocedural call trace | V3 | Ambiguous dispatch, branches and async complicate ordering |
| `state` | States and event-triggered transitions | Explicit enums/state fields/transition methods | V3 exploration | Not inferable for arbitrary code without a defined state model |

We may also support non-UML pipeline/dataflow graphs as a separate family; do not describe these as UML diagrams.

## Design contract

1. **Separate extraction from presentation.** Retain indexed symbols, references and AST-derived evidence; build purpose-specific intermediate graphs (control-flow, type/class relationships, package dependencies, or interactions).
2. **Shared public API.** Expose `diagram_type` and `scope` consistently through CLI, MCP and Python service. Default to `activity` to preserve compatibility.
3. **Typed renderers.** Convert each intermediate representation through a dedicated Mermaid serializer. Mermaid's available syntax varies by diagram type. A future alternative renderer may be needed for stricter UML conventions.
4. **Bounded abstraction.** `max_nodes` and chosen entry/scope should inform relevant extraction and grouping. When a limit would distort behavior, show a warning instead of fabricating or deleting essential structure.
5. **Traceability.** Nodes and edges retain source file, line, symbol and an optional confidence/warning field. A diagram is not proof of runtime behavior.
6. **Deterministic first.** Any later LLM support can suggest human-friendly labels or groupings, but cannot invent source-backed edges.
7. **Test each family.** Create fixtures with manually reviewed references and explicitly test uncertain / unsupported cases.

## Example future commands (NOT available in the current release)

```bash
pyflowmap analyze ./project --diagram-type activity --entry planning.coordinator:PlanningCoordinator.plan
pyflowmap analyze ./project --diagram-type class --scope planning/
pyflowmap analyze ./project --diagram-type package
pyflowmap analyze ./project --diagram-type sequence --entry planning_entrypoint:main
```

## Immediate acceptance criteria for V1.1 activity diagrams

- Render initial and activity final using conventional filled-dot / double-circle forms.
- Correctly associate branch labels with predicate truth values.
- Display one shared final when equivalent terminal actions converge, without incorrectly connecting mutually exclusive paths.
- Validate on P4-Planning-Agent (read-only source) and small synthetic regressions.
