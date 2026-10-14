# PyFlowMap

PyFlowMap generates **static activity diagrams from Python source code** without
importing or executing the analyzed project. It preserves possible control-flow
routes, source references, and warnings when runtime behavior cannot be
determined from the AST.

The primary output is an editable Mermaid diagram (`.mmd`) and a source-linked
graph (`.json`). SVG and PNG are available through Graphviz or Mermaid CLI.
The analyzer is domain-independent: it does not require an agent framework,
a particular application, or a semantic language model.

## Requirements and installation

- Python **3.11+**.
- Git access for dependencies installed from their pinned Git repositories.
- **Graphviz** (`dot`) for SVG/PNG with `--renderer graphviz`, or the optional
  Mermaid CLI (`mmdc`) for `--renderer mermaid`.
- Optional MCP extra for the local MCP server.
- Optional P4-Semantic-Labeler extra for semantic label enrichment.

Install from a local checkout:

```bash
python -m pip install -e .
python -m pip install -e '.[mcp]'      # only if MCP is needed
python -m pip check
```

For ordinary use, install the built wheel instead of installing development
extras. Benchmarks, test fixtures, result galleries, and validation tools are
**not required by the installed product**.

See the [Windows setup guide](docs/windows-local-setup.md) for PowerShell
commands. Linux and macOS can use a Python virtual environment and an installed
Graphviz executable; platform verification is recorded by CI, not presumed
from the documentation.

## Analyze a project

Use the built-in CLI guide to discover the available commands and options:

```bash
pyflowmap --help
pyflowmap inspect --help
pyflowmap analyze --help
```

Then analyze a source project:

```bash
pyflowmap --version
pyflowmap inspect ./my_project
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --format mmd
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --renderer graphviz --format all --output ./diagrams
```

Use `python -m pyflowmap.cli` instead of the `pyflowmap` launcher if a
restricted terminal cannot run installed executable shims.

Inputs are a directory, an individual `.py` file, or a ZIP containing Python
files. Use the qualified entry ID returned by `inspect` when resolution is
ambiguous. `--scope` limits entry-point discovery; statically resolvable local
dependencies may lie outside that scope.

The CLI supports `--language en|es`, `--max-depth`, `--max-nodes`,
`--direction TD|LR`, `--renderer auto|graphviz|mermaid` and
`--format mmd|svg|png|images|all`. The node budget is **soft**: paths are
preserved rather than silently deleted.

### Diagram views

```bash
pyflowmap analyze ./my_project --entry app:main --view detailed --format all --renderer graphviz
pyflowmap analyze ./my_project --entry app:main --view overview --format images --renderer graphviz
pyflowmap analyze ./my_project --entry app:main --view hierarchical --format images --renderer graphviz
```

- **`detailed`** is the activity graph with branch and exception paths.
- **`overview`** is a *process/call summary*, not a UML activity diagram.
  Calls shown as possible targets must not be read as an unconditional sequence.
- **`hierarchical`** links condensed phases and subprocesses back to detailed
  diagrams. Internal decisions remain accessible.

Every graph contains source references and warnings; inspect the JSON when a
caption is abbreviated or a callable is summarized.

## MCP server

```bash
python -m pip install -e '.[mcp]'
pyflowmap-mcp
```

The stdio MCP server provides project inspection and diagram generation.
`PYFLOWMAP_ALLOWED_ROOTS` restricts which source/output paths the server
may access; without it the working directory is used. Separate paths with
the platform's `os.pathsep` (`;` on Windows, `:` on POSIX).
Set `PYFLOWMAP_TEMP_ROOT` to an existing approved writable directory if
temporary ZIP extraction should occur elsewhere.

## Optional semantic labels

Normal analysis uses `--semantic-provider disabled`. It is deterministic,
does **not** call Codex, and does not send source code to a model.

- `mock` tests the optional integration with synthetic labels. It is **not**
  evidence of semantic-label quality.
- `codex` is explicit opt-in, requires the `labeler-codex` extra and an
  authenticated Codex CLI, and can send selected code excerpts for labeling.
  Use only with authorization to transmit that source.

A provider may change permitted node captions and label metadata, **never**
the graph topology, source symbols, decisions, or routes. Real provider
quality must be assessed separately from static flow correctness.
See [semantic labeling](docs/semantic-labeling.md) and
[P4-Semantic-Labeler setup](docs/p4-semantic-labeler-integration.md).

## Scope and limitations

PyFlowMap describes **possible static flow**, not a runtime execution trace.
It can represent syntactic branching, loop transfers, match patterns, exception
handlers, cleanup, and suspension points; it cannot know arbitrary runtime
values, dispatch decisions, external effects, task schedules, or iteration
counts. An unresolved target, summarized body, possible exception, or
context-manager suppression is represented conservatively rather than guessed.

**REVIEW** in a benchmark may mean justified uncertainty, not a defect.
Successful diagram generation alone is **not** semantic PASS.
The precise rules and accepted static limits are in
[analysis rules](docs/analysis-rules.md).

## Development, testing, and releases

```bash
python -m pip install -e '.[dev,mcp]'
python -m pytest -q
python -m ruff check src tests scripts
python scripts/build_release.py     # writes wheel, sdist and verification report to dist/
```

The repository retains reusable regressions (`tests/`) and independent
evaluation programs and oracles (`benchmark/`). These are development
assets, not dependencies of the installed package. The release builder checks
local artifacts; it does **not** publish them.

### Where things live

- [`examples/`](examples/README.md) contains small **input programs** that demonstrate
  what to analyze; the examples are not generated outputs.
- [`pyflowmap-output/`](pyflowmap-output/README.md) documents **generated
  diagrams, galleries and benchmark reports**. The tracked directory contains
  only its README. For complete validation runs, write all actual outputs
  under `%TEMP%\pyflowmap-output` on Windows.
- [`scripts/`](scripts/README.md) holds **developer-only tools** (not end-user
  commands or runtime dependencies). Keep this conventional folder name to
  preserve documented commands and CI paths.
- `dist/` is the ignored destination for explicitly requested local release
  deliverables, not a test workspace.

For a fresh, isolated end-to-end validation of the deterministic analyzer and
optional mock-labeler integration, follow [the validation guide](docs/reference-testing.md).
The real `codex` provider is never run by this test workflow.

Technical documentation:

- [Architecture](docs/architecture.md)
- [Static analysis rules and limits](docs/analysis-rules.md)
- [Supported and proposed diagram types](docs/diagram-types.md)
- [Optional semantic labeling](docs/semantic-labeling.md)
- [Labeler integration](docs/p4-semantic-labeler-integration.md)
- [Development validation and reference cases](docs/reference-testing.md)
- [Developer guide and reusable scripts](docs/development.md)
- [Building wheel and sdist locally](docs/packaging.md)
- [Windows setup](docs/windows-local-setup.md)
- [Example input programs](examples/README.md)
- [Generated output directory contract](pyflowmap-output/README.md)
- [Future directions](docs/roadmap.md)

## License

MIT. See [LICENSE](LICENSE).
