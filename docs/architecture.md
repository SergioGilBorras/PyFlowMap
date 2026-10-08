# Architecture

```mermaid
flowchart TD
  CLI[CLI] --> Service[Application service]
  MCP[MCP stdio server] --> Service
  Service --> Loader[Directory / Python file / ZIP loader]
  Loader --> AST[AST and symbol index]
  AST --> Flow[Control-flow builder]
  Flow --> Simple[Topology-preserving simplifier]
  Simple --> Mermaid[Mermaid serializer]
  Mermaid --> MMD[.mmd + provenance JSON]
  MMD --> Render[Optional mmdc renderer]
  Render --> SVG[.svg / .png]
```

Modules:

- `project.py`: file enumeration, archive safety, `ast.parse`, top-level symbols, best-effort imports and call resolution.
- `analysis.py`: ordered statements, conditional/loop paths, selective orchestrator inlining, `FlowGraph` operations.
- `models.py`: portable intermediate representation (`Node`, `Edge`, `FlowGraph`), each activity carries source symbol(s) and file location(s).
- `mermaid.py`: pure serializer; no source-specific heuristics.
- `render.py`: optional subprocess invocation of an installed Mermaid CLI without shell interpolation.
- `service.py`: single API used by all entry points.
- `cli.py`, `mcp_server.py`: thin interfaces. MCP checks allowed workspace roots.

## Non-goals for V1

Full language-level dataflow, precise type inference, exact exception semantics, branch feasibility, fully qualified import graphs, and executing untrusted source. These should not be silently claimed as supported.

## Design constraints

- Deterministic: no LLM required.
- Conservative: when simplification cannot retain decision topology, keep nodes above budget and warn.
- Traceable: stable intermediate graph plus original file/line references.
- Safe by default: inspect source as text, refuse ZIP traversal, keep MCP filesystem operations inside configured workspace roots.

## Extension point: multiple diagram types (planned, not implemented)

Keep the current activity pipeline unchanged while V1.1 improves its UML-like semantics. Future `diagram_type` selection should happen at the application service boundary (and be exposed identically by CLI and MCP). A selected analyzer produces a **diagram-specific intermediate representation** with source provenance; an associated serializer generates suitable Mermaid syntax (or another renderer if necessary). Do not force class, sequence and package models through the activity-only `FlowGraph` structure.

```mermaid
flowchart TD
    API["CLI / MCP / Python service"] --> Type{"diagram_type (future)"}
    Type -->|activity| CFG["Control-flow model (current)"]
    Type -->|class| Classes["Class relationship model (future)"]
    Type -->|package| Packages["Import dependency model (future)"]
    Type -->|sequence| Calls["Interaction trace model (future)"]
    CFG --> Render["Type-aware Mermaid serializer"]
    Classes --> Render
    Packages --> Render
    Calls --> Render
    Render --> Artifacts[".mmd / optional SVG or PNG"]
```

See [diagram types](diagram-types.md). Unsupported types should fail with a clear error until actually implemented.
