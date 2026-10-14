# Build and distribute PyFlowMap

The source repository includes engineering tools; the **installed
distribution contains only runtime code, Python packaging metadata, README,
and license**. There is no production installer PowerShell script.

## Build and verify locally

```bash
python -m pip install -e '.[dev,mcp]'
python scripts/build_release.py
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

On Windows use `Scripts\python.exe` and `Scripts\pyflowmap.exe` rather
than `bin/`. Use the actual wheel filename present in `dist/`, not
a guessed path. Graphviz (`dot`) must be installed separately for
`--renderer graphviz`.

## GitHub Actions artifacts

The Linux release job builds and smoke-tests wheel/sdist from the
exact remote commit, then uploads both files and the build report
as an Actions artifact. Download these from the successful workflow run.
A job that is still queued or failed is **not** package validation.

## Important publishing limitation

The current `pyproject.toml` declares `portable-tempdirs` by an exact
Git commit URL, and an optional P4-Semantic-Labeler extra from a private
Git repository. These can be used in authorized Git/local installs;
they are **not a conventional dependency strategy for a public PyPI
release**. Before publishing to PyPI, replace direct Git requirements
with suitable published dependencies or an approved, separately tested
packaging arrangement.

Do not silently remove the temporary-directory dependency: it
provides a safety/ACL contract used by ZIP input handling and
development tests. First prove any alternative preserves that contract.

### What is not shipped

`tests/`, `benchmark/`, fixtures, source banks, obsolete diagram
galleries, developer scripts, CI workflows, private credentials,
`.serena/`, `.venv/` and the contents of `pyflowmap-output/`.

See [development](development.md) for retained engineering tools.
