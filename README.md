# PyFlowMap

PyFlowMap extracts conservative, static activity diagrams from Python source.
It parses with `ast` and **never imports or executes the analyzed project**.
Diagrams retain source symbols and locations; inspect JSON warnings for
approximated or unsupported control flow.

## Install

Requires Python 3.11 or later. Graphviz is recommended for SVG and PNG output.

### Windows

Install Python, Git for Windows, and Graphviz (`winget install -e --id
Graphviz.Graphviz`), then open PowerShell in this checkout:

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git'
.\Setup-PyFlowMap-Local.ps1 -Action All -SemanticProvider disabled
```

The installer creates or updates `.venv`, runs pytest and Ruff, and can render
the coordinator and entry-point diagrams from the read-only P4 source. Set
`-P4Root` if P4 is in a different location. Use `-Action Setup`, `Test`, or
`Diagrams` to run a single phase. `-SemanticProvider mock` exercises the
optional labeler without AI inference; `disabled` keeps deterministic labels.
Codex inference is never enabled implicitly. The script can also be run from
another directory with `-PyFlowMapRoot <checkout>`.

The installer pins `portable-tempdirs` to commit
`fd6dbd640630e6911a53b4d756089099ec870a8b`. Pytest allocates an owned,
per-run directory under this checkout for `--basetemp`; this applies to the
installer, direct pytest runs, and PyCharm. ZIP inputs use the same manager.
For direct CLI or MCP use, temporary files go under the current directory by
default; set `$env:PYFLOWMAP_TEMP_ROOT` to an existing writable directory when
the current directory is not an approved workspace.

### macOS and Linux

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,mcp]'
```

Install Graphviz with the operating system's package manager when image export
is needed. Mermaid CLI is an alternative renderer and requires Node.js.

## Use the CLI

```bash
pyflowmap inspect ./my_project
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --format mmd
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run \
  --format images --renderer graphviz --output ./diagrams
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --view overview --format images --renderer graphviz --output ./diagrams
```

Inputs can be a directory, a Python file, or a ZIP containing Python files.
Use the fully qualified entry ID returned by `inspect` when a name is
ambiguous. `--scope` restricts entry discovery; resolvable local dependencies
may still be examined outside that scope.

Each analysis writes editable Mermaid (`.mmd`) and a traceable graph (`.json`).
`--format svg`, `png`, `images`, or `all` adds rendered images. Graphviz SVG
uses UTF-8, including for Spanish labels. `max_nodes` is a soft limit: the
analyzer preserves branch topology and reports when a graph cannot be
simplified safely to the requested size.

`--view overview` makes a function-level overview from observed source-symbol
transitions. Cross-function edges retain their original branch labels. JSON
records source locations and original node IDs. Decisions and paths inside a
function are summarized; use the detailed view to inspect them. The overview
warning states this abstraction explicitly.

## Use the MCP server

Install the MCP extra and set the roots the server may inspect or write:

```powershell
python -m pip install -e '.[mcp]'
$env:PYFLOWMAP_ALLOWED_ROOTS = 'F:\Work\MyProject;F:\Work\Diagrams'
pyflowmap-mcp
```

On Windows, separate roots with `;` (`os.pathsep`); on POSIX, use `:`. The
server defaults to the current directory if the variable is unset. Every
source and output path must resolve within an allowed root. Keep P4 outside
the allowlist when using MCP if it must remain read-only. Set
`PYFLOWMAP_TEMP_ROOT` to an existing writable approved workspace for ZIP inputs.

## Optional semantic labels

Normal analysis uses deterministic labels and makes no provider calls. The
optional P4-Semantic-Labeler integration can be checked with
`--semantic-provider mock`; mock labels are synthetic and do not assess
semantic quality. `--semantic-provider codex` requires the explicit Codex
extra and a deliberate command-line choice. Provider output can change node
text only; it cannot change decisions, edges, or source provenance.

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

Technical details are kept in focused documents:

- [Architecture](docs/architecture.md)
- [Analysis rules and limitations](docs/analysis-rules.md)
- [Diagram type roadmap](docs/diagram-types.md)
- [P4 labeler integration API](docs/p4-semantic-labeler-integration.md)
- [Reference snapshot and hash policy](docs/reference-testing.md)
- [Semantic labeling details](docs/semantic-labeling.md)

Historical result README files under `examples/results/` document earlier
outputs and remain alongside their artifacts.

## Limitations

The diagram represents possible static control flow, not a runtime trace.
Dynamic dispatch, reflection, imports, exception-group matching, and complex
exception flow can be approximated. `try/finally` paths are retained, but
handler selection is not inferred from runtime exception types. Check the
warnings and source locations before relying on a diagram as a specification.

MIT License.
