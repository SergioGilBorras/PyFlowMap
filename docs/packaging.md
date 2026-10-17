# Build and distribute PyFlowMap

The source repository includes engineering tools; the **installed
distribution contains only runtime code, Python packaging metadata, README,
and license**. There is no production installer PowerShell script.

## Build and verify locally

```bash
python -m pip install -e '.[dev,mcp]'
python scripts/build_release.py
# Outputs: dist/*.whl, dist/*.tar.gz and dist/release-build-report.json
```

The release builder:

1. Copies an allowlisted set of runtime source and packaging files into an
   isolated staging directory.
2. Builds a wheel (`.whl`) and source distribution (`.tar.gz`).
3. Rejects package members outside the declared allowlist.
4. Installs the wheel in a separate virtual environment and smoke-tests
   the module CLI, export formats, and MCP availability.
5. Writes artifacts and a `release-build-report.json` under ignored `dist/`.
   Override with `--output /approved/path` if needed.

The build's scratch workspaces are created under the OS temporary directory
(Windows: `%TEMP%`; POSIX: `TMPDIR` or the standard system directory), while
**deliverables remain locally in `dist/`**. The version comes from
`pyflowmap.__version__`. Building does not create
Git tags, publish to an index, or create a GitHub release.

## Clean wheel installation

```bash
python -m venv /tmp/pyflowmap-test
/tmp/pyflowmap-test/bin/python -m pip install ./dist/pyflowmap-1.0.0-py3-none-any.whl
/tmp/pyflowmap-test/bin/pyflowmap --help
/tmp/pyflowmap-test/bin/python -m pip check
```

On Windows PowerShell, from the repository root with the development
venv installed:

```powershell
.\.venv\Scripts\python.exe scripts\build_release.py
Get-ChildItem .\dist\
```

On Windows use `Scripts\python.exe` and `Scripts\pyflowmap.exe` rather
than `bin/`. Use the actual wheel filename present in `dist/`, not
a guessed path. Graphviz (`dot`) must be installed separately for
`--renderer graphviz`.

## GitHub Actions artifacts

The Linux release job builds and smoke-tests wheel/sdist from the
exact remote commit, then uploads both files and the build report
as an Actions artifact. Pull-request runs checkout the actual branch head
commit rather than GitHub's temporary merge commit. The report records
that Git SHA when the Git checkout is available. Download these from the successful workflow run.
A job that is still queued or failed is **not** package validation.

## Important publishing limitation

The current `pyproject.toml` declares `portable-tempdirs` by an exact
Git commit URL, and optional P4-Semantic-Labeler extras from a separate
Git repository. A local wheel for an upstream package is not proof of an
index-published version. These can be used in authorized Git/local installs;
they are **direct URL dependencies incompatible with public PyPI uploaded
metadata**. Before any PyPI publication, replace them with suitable
versioned packages or a separately tested and approved solution. GitHub
source releases and package-index publishing are distinct operations.

Do not silently remove the temporary-directory dependency: it
provides a safety/ACL contract used by ZIP input handling and
development tests. First prove any alternative preserves that contract.

### What is not shipped

`tests/`, `benchmark/`, fixtures, source banks, generated diagram
galleries, developer scripts, CI workflows, private credentials,
`.serena/`, `.venv/` and the generated contents of `output_validacion/`
and `output_graphs/`.

See [development](development.md) for retained engineering tools.
