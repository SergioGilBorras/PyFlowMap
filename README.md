# PyFlowMap

**Python source → simplified Mermaid activity diagrams.** PyFlowMap extracts conservative, static control-flow sketches from Python functions/methods. The goal is **readability over exhaustive call graphs**: hide implementation noise, retain important decisions, and keep links back to the original code.

> **Early preview (0.1.1).** Not a compiler, full CFG or runtime tracer. Python code is **never executed**. Dynamic dispatch, decorators, reflection, imports and exception flows may be incomplete or approximated; inspect the JSON warnings and source locations.

## Quick start

Requires Python 3.11+.

```bash
pip install -e .
pyflowmap inspect ./my_project
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --max-nodes 8 --format mmd
```

Analyze a subset with a specific entry point:

```bash
pyflowmap inspect ./my_project --scope src/etl
pyflowmap analyze ./my_project --scope src/etl --entry etl.pipeline:Pipeline.execute --format mmd --output ./diagrams
```

Supported inputs: **local directory, `.py` file, ZIP containing `.py` files**. Import resolution is best-effort; use the fully qualified ID reported by `inspect` to avoid ambiguity. GitHub URLs are **not yet** a direct input: clone locally first.

### Image export

Install the [official Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) separately (Node.js and a supported Chromium environment are required):

```bash
npm install -g @mermaid-js/mermaid-cli
pyflowmap analyze ./my_project --entry app:main --format svg
pyflowmap analyze ./my_project --entry app:main --format png
pyflowmap analyze ./my_project --entry app:main --format all
```

Every analysis saves an editable `.mmd` **and** a `.json` intermediate graph; SVG/PNG is optional. When `mmdc` is unavailable, image export can use an installed Graphviz `dot` executable. Select with `--renderer graphviz` or use `--renderer auto` (Mermaid CLI first, Graphviz fallback). If neither is available, the `.mmd` and `.json` remain.

### Run as an MCP server

```bash
pip install -e '.[mcp]'
PYFLOWMAP_ALLOWED_ROOTS="$PWD" pyflowmap-mcp
```

The local **stdio** MCP server offers `inspect_project`, `generate_diagram` and `generate_activity_diagram` tools. A generic MCP client can configure it like this:

```json
{
  "mcpServers": {
    "pyflowmap": {
      "command": "pyflowmap-mcp",
      "env": {"PYFLOWMAP_ALLOWED_ROOTS": "/absolute/path/to/workspace"}
    }
  }
}
```

`generate_diagram` accepts `project_path`, `entry_point`, `scope`, `max_nodes`, `max_depth`, `format`, `language`, `renderer`, `diagram_type` and `output_path`. Currently `activity` is the only supported diagram type; unsupported values fail clearly. It returns the Mermaid source, warnings, and absolute output filenames. MCP file paths must stay under `PYFLOWMAP_ALLOWED_ROOTS` (defaults to the server's current working directory). Run this only against workspaces you trust; although it doesn't execute Python, image rendering invokes an installed local executable.

## How it works

1. Parse `.py` files with the standard-library `ast` module (without importing them).
2. Index top-level functions, classes, and methods; resolve simple calls, relative imports, local constructors and default-instantiated `self` attributes.
3. Build a sequence with simple `if/else` branches and `for`/`while` loops, expanding small local orchestrators when useful.
4. Contract only **linear activities** until `--max-nodes` is reached, retaining branching topology. If this isn't possible, warn and preserve the extra nodes rather than silently misrepresenting the code.
5. Serialize to Mermaid `flowchart`, write provenance JSON, and optionally use Mermaid CLI or Graphviz for SVG/PNG. The activity diagram includes UML-inspired initial/final nodes and shared returns.

## Usage

```text
pyflowmap inspect SOURCE [--scope RELATIVE_PATH]
pyflowmap analyze SOURCE [--entry MODULE:FUNCTION_OR_CLASS.METHOD]
                         [--scope RELATIVE_PATH] [--max-nodes 8]
                         [--max-depth 2] [--direction TD|LR]
                         [--diagram-type activity] [--language en|es]
                         [--renderer auto|mermaid|graphviz]
                         [--format mmd|svg|png|all] [--output DIR_OR_FILE]
```

For example, `--entry pipeline:main` analyzes the `main` function in `pipeline.py`. `--scope` limits **entry-point discovery**, while imported dependencies can still be examined outside the scope when statically resolvable.

## Development

```bash
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

See [architecture](docs/architecture.md), [analysis rules](docs/analysis-rules.md), and [roadmap](docs/roadmap.md). The tests include a sample multi-file project and an **immutable, commit-pinned P4-Planning-Agent** regression snapshot. See [reference testing](docs/reference-testing.md) and [P4 V1.1 diagrams](examples/results/p4-planning-agent-v1-1/README.md).

## Important limitations

- A diagram illustrates **possible static control flow**, not a verified runtime trace.
- Calls made through reflection, dynamic imports, abstract dispatch, higher-order functions, and decorators cannot always be resolved. For ambiguous symbols, choose an explicit entry.
- `try/except` is approximated and marked with a warning. `match/case` is collapsed. Dynamic imports, unusual relative imports and injected class instances may still be unresolved.
- `max_nodes` is a **soft limit** if lowering further would destroy topology.
- Image export needs either Mermaid CLI (`mmdc`) or Graphviz (`dot`). The core parser and `.mmd` output have no external runtime dependencies.
- ZIP input is restricted by size and path safety checks; nested ZIP archives and non-Python files are ignored.

## License

MIT.

## Current activity output and future diagram families

The sole CLI entry point is `pyflowmap analyze`, dispatching through `--diagram-type activity` to `pyflowmap.diagrams.activity`. The MCP service also exposes a dedicated `generate_activity_diagram` tool. New UML families (class, sequence, package, etc.) will have **separate analyzers and representations**, but share the public CLI and output machinery. The REST API/desktop UI remain future interfaces. See [diagram types](docs/diagram-types.md).

Example for the immutable P4 case:

```bash
pyflowmap analyze tests/fixtures/references/p4-planning-agent-v1 \\
  --entry planning.coordinator:PlanningCoordinator.plan \\
  --diagram-type activity --language es --format all --renderer graphviz \\
  --output ./results/p4-v1
```
