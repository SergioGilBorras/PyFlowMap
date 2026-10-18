# Windows installation and local development

This guide applies to the current PyFlowMap source checkout and wheel. It
does not require a particular drive letter, PyCharm layout or analysis
project.

## Requirements

- Python 3.11 or later and Git for Windows.
- Graphviz for SVG/PNG when using `--renderer graphviz`.
- Access to any pinned Git dependencies in `pyproject.toml`.

In PowerShell, Graphviz may be installed with:

```powershell
winget install -e --id Graphviz.Graphviz
dot -V
```

Open a new terminal if executable paths have changed.

## Set up a development checkout

Run these commands from the **PyFlowMap repository root**:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
```

## Use the installed CLI

```powershell
.\.venv\Scripts\pyflowmap.exe --version
.\.venv\Scripts\pyflowmap.exe inspect .\tests\fixtures\sample_project
.\.venv\Scripts\pyflowmap.exe analyze .\tests\fixtures\sample_project --entry pipeline:main --renderer graphviz --format all
```

When Windows execution restrictions block `.exe` shims, diagnose the host
environment rather than assuming a problem in PyFlowMap. The module form
uses the same installed Python package:

```powershell
.\.venv\Scripts\python.exe -m pyflowmap.cli --help
.\.venv\Scripts\python.exe -m pyflowmap.cli inspect .\tests\fixtures\sample_project
```

Python sources analyzed by PyFlowMap are parsed without importing or
executing them.

## MCP and temporary workspaces

The MCP server is optional. Configure the allowed source/output roots
before running it:

```powershell
$env:PYFLOWMAP_ALLOWED_ROOTS = (Resolve-Path .).Path
.\.venv\Scripts\pyflowmap-mcp.exe
```

Separate multiple roots with `;` on Windows. The fallback is the process's
current directory. For ZIP inputs or restricted folders, set
`PYFLOWMAP_TEMP_ROOT` to an existing approved writable directory.

## Optional semantic labels

Deterministic labeling does not need P4-Semantic-Labeler or Codex.
For integration checks, install `.[labeler]` and choose
`--semantic-provider mock`. This does **not** run inference.
Real `codex` use requires separate installation, authentication and
explicit permission to transmit source excerpts. See the
[labeler guide](p4-semantic-labeler-integration.md).

## Publishing and validation

For release builds use `python scripts/build_release.py` from the checkout.
It creates local wheel/sdist and the verification report in `dist/` while
temporary build/test files are isolated under `%TEMP%`.
The builder must keep tests, benchmarks, generated reports, personal files
and workspaces out of the wheel/sdist. Running tests and building release artifacts are developer tasks, not
requirements for users of an installed wheel.

See [reference testing](reference-testing.md) for how to regenerate a clean
verification folder.

## Real Codex evaluation and consumer output

After installing `.[dev,mcp,labeler-codex]`, authenticate Codex and inspect
the MCP connectors configured for Codex. Opt into real labeling for future
CLI and MCP invocations with the user environment setting:

```powershell
[Environment]::SetEnvironmentVariable('PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER','codex','User')
```

Open a new shell after configuring the preference. Explicit
`--semantic-provider disabled` still works, and nothing is transmitted
implicitly in an unconfigured installation. Without `--output`, diagrams
are placed in `output_graphs/<timestamp>_<id>/` under the working directory.

To run ALL 81 benchmark cases in both modes, on your authorized checkout:

```powershell
.\.venv\Scripts\python.exe scripts\validate_all.py --acknowledge-source-transmission
```

The run creates `output_validation/validation-<timestamp>_<id>/`.
Scratch files and caches stay in `%TEMP%`. A failed run keeps evidence;
it does not falsely claim semantic correctness or overwrite protected files.
