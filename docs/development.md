# Developer guide

PyFlowMap's installed package is the runtime in `src/pyflowmap/`.
**No installer script, benchmark runner, pytest fixture, evaluation gallery
or reference project is required for the end user.** Those tools live
only in the source repository.

## Local setup

Python 3.11+, Git access to the pinned runtime dependency, and Graphviz
for image tests are required.

```bash
python -m venv .venv
# Activate the environment using your shell, or call its Python directly.
python -m pip install -e '.[dev,mcp]'
python -m pip check
python -m pytest -q
python -m ruff check src tests scripts
```

On Windows PowerShell, use
`.\.venv\Scripts\python.exe` in place of an activated `python`.
On Linux/macOS it is `.venv/bin/python`.

**Do not use a project-specific PowerShell installer.**
For Windows commands and installed launchers, see
[Windows setup](windows-local-setup.md).

## Development tools

| Location | Purpose | Shipping? |
| --- | --- | --- |
| `tests/`, root `conftest.py` | Automated checks and shared pytest isolation under the OS temporary directory | No |
| `benchmark/` | Reusable corpora, `evaluation/` oracles, `runners/`, oracle `tests/` and metamorphic checks | No |
| `benchmark/independent-v1/run.py`, `independent-v2/run.py` | Repeatable generation from intact source banks | No |
| `scripts/build_release.py` | Build checked local wheel/sdist and isolated install smoke | No |
| `scripts/verify_offline_release_install.py` | Windows-specific offline installation diagnostic when internet downloads fail | No |
| `scripts/verify_portable_tempdirs.py` | Check exact installed Git dependency revision in development | No |
| `scripts/compare_labeler_modes.py` | Compare deterministic and synthetic labels without model inference | No |
| `.github/workflows/` | Clean Linux/macOS/Windows CI and downloadable release artifacts | No |

The canonical semantic evaluator imports `oracles_phase*` components;
mutation tests cover their independent semantic obligations. These are
internal test tools, not product execution modes.
Remove a test utility only after showing it is unreferenced or its
replacement catches the same regressions.

### Regression commands

```bash
python -m benchmark.runners.run --output output_validacion/baseline --render
python benchmark/independent-v1/run.py --project-root . --output output_validacion/v1
python benchmark/independent-v2/run.py --project-root . --output output_validacion/v2
python -m benchmark.runners.metamorphic --output output_validacion/metamorphic
```

Benchmark strict mode intentionally treats REVIEW more severely; do not
present a generated diagram as a semantically validated PASS. See
[benchmark README](../benchmark/README.md).

## Temporary workspaces and cleanup

`output_validacion/`, `dist/`, Python caches, editable-install metadata,
ZIP archives and Graphviz images are generated, ignored work products.
Keep the source fixtures, oracles and tests, but do not version their
outputs. Never delete `.serena/`, `.git/`, the current `.venv/`,
unexpected personal files, or protected Windows temporary paths.
Git ignore rules do not remove files that were already committed.

The root `conftest.py` is **not an installer or runtime code**. Pytest
loads it automatically for both `tests/` and `benchmark/`. It creates
scratch test workspaces under the current system temp directory (Windows:
`%TEMP%`) and cleans them after the run. Pytest's cache provider is
disabled so it cannot create a `.pytest_cache` folder in the checkout.
The `_avast_` directory, if present, may come from endpoint protection
software; never delete or attribute it to PyFlowMap without evidence.

To validate a release, use a new ignored output directory and record
the exact Git SHA, OS/Python versions and semantic statuses. Do not
recycle output from another candidate commit.

## Optional external labeling

Use `disabled` for ordinary development. The external `mock` provider
requires the optional `.[labeler]` dependency; it makes no remote inference.
When that dependency is missing in CI, its result is **NOT_VERIFIED** rather
than PASS or FAIL. Injected-provider invariance remains covered by pytest. Real `codex` inference sends excerpts to a provider and
requires separate explicit authorization. Do not use Codex inference
as part of the default CI.

See the [script catalog](../scripts/README.md), [benchmark layout](../benchmark/README.md),
[package building](packaging.md) and
[reference testing](reference-testing.md).


## Canonical one-command validation

The supported full developer workflow is:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler-codex]'
.\.venv\Scripts\python.exe scripts\validate_all.py --acknowledge-source-transmission
```

The script runs pytest, Ruff, pip integrity, temporary-directory validation,
15 baseline semantic-oracle cases, eight control-flow cases, the 28+30
independent banks, metamorphic checks, real Codex labeling over the same
81 sources, graph invariance checks, and clean wheel/sdist verification.
Real inference requires a logged-in Codex CLI and may incur usage. Review
any inherited MCP tools before enabling it.

Validation outputs are retained by default. Removing managed historical
runs requires the explicit pruning option; failures retain their diagnostics. Unrecognized and protected
directories are never forcibly removed. All scratch and caches are under
system TEMP. The validator does not modify `output_graphs/` (consumer
history), fixtures, `.serena/`, or `.git/`.

A generated diagram or a real-model label is NOT automatic semantic approval.
Unresolved V1/V2 obligations remain `NOT_EVALUATED` or `REVIEW` pending
independent checking. See [validation outputs](../output_validacion/README.md).
