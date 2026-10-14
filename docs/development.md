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

## Retained tools and why they exist

| Location | Purpose | Shipping? |
| --- | --- | --- |
| `tests/`, root `conftest.py` | Automated checks and shared pytest isolation under the OS temporary directory | No |
| `benchmark/` | Four known regression corpora, canonical evaluator, mutation and metamorphic tools | No |
| `benchmark/independent-v1/run.py`, `independent-v2/run.py` | Repeatable generation from intact source banks | No |
| `scripts/build_release.py` | Build checked local wheel/sdist and isolated install smoke | No |
| `scripts/verify_offline_release_install.py` | Windows-specific offline installation diagnostic when internet downloads fail | No |
| `scripts/verify_portable_tempdirs.py` | Check exact installed Git dependency revision in development | No |
| `scripts/compare_labeler_modes.py` | Compare deterministic and synthetic labels without model inference | No |
| `.github/workflows/` | Clean Linux/macOS/Windows CI and downloadable release artifacts | No |

The evaluator's older `oracles_phase*` modules remain in use through
the canonical evaluator and mutation tests. A number in a regression
filename is *test provenance*, not a supported old application mode.
Remove a test utility only after showing it is unreferenced or its
replacement catches the same regressions.

### Regression commands

```bash
python benchmark/run.py --output pyflowmap-output/baseline --render
python benchmark/independent-v1/run.py --project-root . --output pyflowmap-output/v1
python benchmark/independent-v2/run.py --project-root . --output pyflowmap-output/v2
python benchmark/metamorphic.py --output pyflowmap-output/metamorphic
```

Benchmark strict mode intentionally treats REVIEW more severely; do not
present a generated diagram as a semantically validated PASS. See
[benchmark README](../benchmark/README.md).

## Temporary workspaces and cleanup

`pyflowmap-output/`, `dist/`, Python caches, editable-install metadata,
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

Use `disabled` for ordinary development or `mock` for structural
invariance. Real `codex` inference sends excerpts to a provider and
requires separate explicit authorization. Do not use Codex inference
as part of the default CI.

See [package building](packaging.md) and
[reference testing](reference-testing.md).
