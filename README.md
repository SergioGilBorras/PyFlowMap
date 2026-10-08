# PyFlowMap

**Python source → simplified Mermaid activity diagrams.** PyFlowMap extracts conservative, static control-flow sketches from Python functions/methods. The goal is **readability over exhaustive call graphs**: hide implementation noise, retain important decisions, and keep links back to the original code.

> **Early preview (0.1.0).** Not a compiler, full CFG or runtime tracer. Python code is **never executed**. Dynamic dispatch, decorators, reflection, imports and exception flows may be incomplete or approximated; inspect the JSON warnings and source locations.

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

Every analysis saves an editable `.mmd` **and** a `.json` intermediate graph; SVG/PNG is optional. If `mmdc` is unavailable, the image command fails with a clear diagnostic while retaining `.mmd` and `.json`.

### Run as an MCP server

```bash
pip install -e '.[mcp]'
PYFLOWMAP_ALLOWED_ROOTS="$PWD" pyflowmap-mcp
```

The local **stdio** MCP server offers `inspect_project` and `generate_diagram` tools. A generic MCP client can configure it like this:

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

`generate_diagram` accepts `project_path`, `entry_point`, `scope`, `max_nodes`, `max_depth`, `format`, and `output_path`. It returns the Mermaid source, warnings, and absolute output filenames. MCP file paths must stay under `PYFLOWMAP_ALLOWED_ROOTS` (defaults to the server's current working directory). Run this only against workspaces you trust; although it doesn't execute Python, image rendering invokes an installed local executable.

## How it works

1. Parse `.py` files with the standard-library `ast` module (without importing them).
2. Index top-level functions, classes, and methods; resolve simple calls and local constructor receivers.
3. Build a sequence with simple `if/else` branches and `for`/`while` loops, expanding small local orchestrators when useful.
4. Contract only **linear activities** until `--max-nodes` is reached, retaining branching topology. If this isn't possible, warn and preserve the extra nodes rather than silently misrepresenting the code.
5. Serialize to Mermaid `flowchart`, write provenance JSON, and optionally invoke `mmdc` for SVG/PNG.

## Usage

```text
pyflowmap inspect SOURCE [--scope RELATIVE_PATH]
pyflowmap analyze SOURCE [--entry MODULE:FUNCTION_OR_CLASS.METHOD]
                         [--scope RELATIVE_PATH] [--max-nodes 8]
                         [--max-depth 2] [--direction TD|LR]
                         [--format mmd|svg|png|all] [--output DIR_OR_FILE]
```

For example, `--entry pipeline:main` analyzes the `main` function in `pipeline.py`. `--scope` limits **entry-point discovery**, while imported dependencies can still be examined outside the scope when statically resolvable.

## Development

```bash
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

See [architecture](docs/architecture.md), [analysis rules](docs/analysis-rules.md), and [roadmap](docs/roadmap.md). The tests include a sample multi-file project.

## Important limitations

- A diagram illustrates **possible static control flow**, not a verified runtime trace.
- Calls made through reflection, dynamic imports, abstract dispatch, higher-order functions, and decorators cannot always be resolved. For ambiguous symbols, choose an explicit entry.
- `try/except` is approximated and marked with a warning. `match/case` is collapsed. Relative imports aren't fully resolved.
- `max_nodes` is a **soft limit** if lowering further would destroy topology.
- Rendering requires a separately installed `mmdc`. The core parser and `.mmd` output have no external runtime dependencies.
- ZIP input is restricted by size and path safety checks; nested ZIP archives and non-Python files are ignored.


## Generic activity labels (no project-specific dictionaries)

Labels are derived from method/function identifiers and optional docstrings. For methods,
common verb names and CamelCase class words provide context. This is deterministic and
works independently of the project. For instance, `GalaxyAnalysisAgent.analyze` becomes
`Analyze galaxy` or `Analizar galaxy` with `--language es`. The source symbol is displayed
in a smaller second line and kept in full in the JSON graph.

**No AI and no full natural-language translator are included.** Generic action verbs can
be localized, but unknown domain-specific nouns stay in their original language rather
than being replaced by hard-coded project aliases. The actual condition predicate appears
in each decision node, so Yes/No (Sí/No) always retain their logical truth values.

See [analysis rules](docs/analysis-rules.md) for limitations and future AI labeling options.

## License

MIT.
