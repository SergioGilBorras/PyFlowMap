# Developer utilities (not end-user commands)

`scripts/` is the conventional folder for **repository maintainers, release
engineers and CI**, not for people installing and using the `pyflowmap`
command. End users need only the installed wheel (or a normal pip
installation), the CLI, and optionally Graphviz/MCP. The scripts do not
ship inside wheel or sdist, and none is required to analyze Python.

Do not rename this folder: GitHub Actions, tests and contributor guides call
these paths. A more descriptive heading and clear ownership avoid a breaking
repository-wide rename.

## Tools and output

| Utility | Developer task | Output |
| --- | --- | --- |
| `build_release.py` | Build an allowlisted wheel and sdist; verify isolated pip installation, graphics, CLI and MCP | `dist/` by default (or `--output`) with a SHA-256 `release-build-report.json` |
| `run_full_validation.py` | Run fresh tests, structural and semantic benchmark oracles, metamorphic checks, V1/V2 generators, and a clean package build; optionally compare mock labels | A **new** `%TEMP%\pyflowmap-output\full-*` folder |
| `compare_labeler_modes.py` (mock only) | Compare topology and provenance with `disabled` versus optional `mock` labels on the baseline (`--corpus all` includes 28 V1 and 30 V2 cases) | `labeler-comparison.json` and separate diagrams; **no Codex** |
| `compare_real_labeler.py` | Invoke authenticated **real Codex** inference on 81 regression cases and 1 example, check topology, and export every label for human review | `python scripts/compare_real_labeler.py --acknowledge-source-transmission --output %TEMP%\\pyflowmap-real` |
| `verify_offline_release_install.py` | Windows-only diagnostic for installing a verified local wheel without downloading dependencies | Caller-specified JSON report; distinguishes PASS, PARTIAL and FAIL |
| `verify_portable_tempdirs.py` | Check the installed managed-temporary-directory dependency matches the exact pinned Git commit | Console status |

Run from the repository root using the appropriate Python virtual
environment. Examples (PowerShell):

```powershell
.\.venv\Scripts\python.exe scripts\build_release.py
.\.venv\Scripts\python.exe scripts\run_full_validation.py
.\.venv\Scripts\python.exe scripts\run_full_validation.py --with-labeler
```

The **optional mock-only** `--with-labeler` run requires `pip install -e '.[dev,mcp,labeler]'` in
advance. It uses the synthetic `mock` provider; real inference with `codex`
is deliberately excluded. The baseline oracles validate selected semantics
on 15+8 cases, whereas V1/V2 are **generation and structural checks**:
their 58 cases remain `NOT_EVALUATED` semantically until separately reviewed.

## Temporary workspace and safety policy

The full validation runner chooses a unique new directory below the current
Windows `%TEMP%` (or the POSIX system temp root), redirects pytest,
bytecode and Ruff caches, and places **all its results** there. It does not
delete earlier runs, overwrite fixtures, alter `.serena/`, or clean unknown
folders. This is a *fresh run*, not a permission-changing cleanup tool.

When run separately, `build_release.py` deliberately writes final packages
to the ignored repository `dist/`; only its staging directories live in the
system temporary folder. Pass `--output` inside `%TEMP%` when you want even
release deliverables outside the checkout. `verify_offline_release_install.py`
requires explicit `--wheel`, `--work-parent` and `--output`.

The test fixture at repository-root `conftest.py` configures pytest
temporary workspaces under `%TEMP%` and disables pytest's cache provider.
No PyFlowMap tool intentionally creates `pytest-cache-files-*` or
`_avast_` in the checkout. However, `_avast_` can be created by endpoint
protection outside Python's control: identify its owner before any cleanup.
Never force-delete protected ACL paths.

## Documentation

- [Development setup](../docs/development.md)
- [Testing and semantic status](../docs/reference-testing.md)
- [Exact output layout](../pyflowmap-output/README.md)
- [Packaging and release artifacts](../docs/packaging.md)
- [Regression corpora](../benchmark/README.md)


## Live Codex validation (not mock)

For the next true end-to-end assessment, install
`pip install -e '.[dev,mcp,labeler-codex]'`, authenticate `codex login`,
and invoke:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_validation.py --with-real-labeler --acknowledge-source-transmission --output-parent .\pyflowmap-output
```

This performs **real provider requests**, not fake inference. It covers
15 baseline + 8 control-flow + 28 V1 + 30 V2 + 1 basic example = 82 source
programs in both deterministic and Codex modes. Source snippets are
transmitted externally; check the Codex CLI's configured MCP connectors and
provider usage policy before running. Real-model labels do not turn
`NOT_EVALUATED` flow-oracle status into semantic PASS.

All transient caches and test working directories remain below `%TEMP%`,
including when the inspection reports are saved in `pyflowmap-output/`.
Historical output folders are **not deleted** by this tool.
