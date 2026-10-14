# Developer scripts

These four Python programs are **developer/CI utilities**. None is part of
the installed PyFlowMap wheel or sdist. Run them from the repository root
using a Python environment with the project's relevant extras installed.

| File | Keep? | Purpose | Typical command |
| --- | --- | --- | --- |
| `build_release.py` | **Yes** | Build allowlisted wheel/sdist, install wheel in an isolated venv and verify CLI/MCP/rendering; write hashes and build report | `python scripts/build_release.py` |
| `compare_labeler_modes.py` | **Yes** | Verify `disabled` vs `mock` graph invariance on 15 cases without any AI requests (English labels by default; `--language es` optional) | `python scripts/compare_labeler_modes.py --output pyflowmap-output/labeler-comparison` |
| `verify_offline_release_install.py` | **Yes, diagnostic** | Check a wheel using reconstructed **verified local wheels** on Windows without downloading dependencies; distinguish launcher BLOCKED, FAIL and PASS | `python scripts/verify_offline_release_install.py --help` |
| `verify_portable_tempdirs.py` | **Yes, dependency integrity** | Check that the installed managed-tempdir dependency matches the exact pinned commit | `python scripts/verify_portable_tempdirs.py` |

## Distribution output and temporary workspaces

The normal command `python scripts/build_release.py` writes the installable
wheel, sdist and `release-build-report.json` in the **local** ignored
`dist/` directory. Its isolated staging and clean-install environments are
created under the OS system temp directory (Windows `%TEMP%`) and
cleaned up when possible. To choose another *approved* output folder,
pass `--output /path/to/output`.

The offline installer diagnostic is **Windows-specific** and intentionally
requires explicit `--wheel`, `--work-parent` and `--output` arguments;
use an approved system temp parent, not the checkout. Its nonzero exit code
when the launcher is `PARTIAL` or `FAIL` is deliberate.

No script should create `pytest-cache-files-*` or `pyflowmap-pytest-*`
inside the repository. Root `conftest.py` manages test workspaces under
the OS temp directory and disables the checkout's pytest cache.

## What was removed

Project-specific PowerShell installation and redundant historical benchmark
launchers were retired. Use `pip install`, the CLI's own `--help`,
the documented `python -m benchmark.runners.*` commands and GitHub Actions
instead. Do not resurrect shell installers or generated examples as runtime
requirements.

For full developer setup see [development](../docs/development.md),
for the output contract see [packaging](../docs/packaging.md), and for semantic
test entry points see [benchmark](../benchmark/README.md).
