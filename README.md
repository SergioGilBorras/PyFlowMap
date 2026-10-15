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

### Outputs and one-command validation

- [`output_graphs/`](output_graphs/README.md) is the consumer's diagram history.
  Without `--output`, each analysis creates a separate dated folder under
  the **current working directory**. Explicit `--output` remains supported.
- [`output_validacion/`](output_validacion/README.md) is developer-only
  validation evidence. It holds a clearly named dated run, 81 preserved
  benchmark cases in deterministic and real-Codex mode, all test reports,
  semantic review and built packages. No mock is part of the global command.
- [`benchmark/`](benchmark/README.md) supplies the 81 retained source
  cases and evaluation criteria. [`scripts/`](scripts/README.md) contains
  only developer tools; both are excluded from the installed distribution.
- `%TEMP%` (the OS temp directory) holds test scratch work and caches, not
  generated end-user diagrams. `dist/` remains the optional ignored
  destination of a separately requested local package build.

After installing `.[dev,mcp,labeler-codex]`, authenticating the Codex CLI,
and reviewing its inherited MCP connectors, **one command** runs the full
live evaluation on the authorized local machine:

```powershell
.\.venv\Scripts\python.exe scripts\validate_all.py --acknowledge-source-transmission
```

A successful new evaluation prunes only prior runs identified as belonging
to the validator; failed runs and unknown data are preserved for diagnosis.
Codex produces real labels but their semantic faithfulness still needs
independent review. CI never uses the live provider. No package is published
by this command.

Consumer labeling can be set to Codex as an **explicit, persistent environment
preference** after setup: `PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER=codex`.
An unconfigured installation remains offline to avoid unexpectedly sending
private source code. Explicit `--semantic-provider disabled` overrides the
preference.

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
- [Consumer diagram output](output_graphs/README.md)
- [Complete validation output](output_validacion/README.md)
- [Future directions](docs/roadmap.md)

## License

MIT. See [LICENSE](LICENSE).


## Experimental UML class diagrams (additive feature branch)

The `class` family extracts declared classes, annotated attributes, methods,
and verifiable local inheritance with correct UML generalization arrows.
It does not execute the source or invent associations. See
[UML class documentation](docs/uml-classes.md).

```powershell
pyflowmap analyze ./project --diagram-type class --format all --renderer graphviz
```

The original `activity` family remains the default. UML package diagrams
are also available with real folder notation and local import dependencies:

```powershell
pyflowmap analyze ./project --diagram-type package --format all --renderer graphviz
```

See [UML package documentation](docs/uml-packages.md). A GitHub Pages site is
planned only after both UML families finish cross-platform verification.
