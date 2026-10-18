# Developer scripts — not part of the installed product

These scripts are for contributors, semantic reviewers and CI. Consumers
only need the `pyflowmap` CLI / MCP server, optionally Graphviz and the
explicitly configured P4 labeler. Keep the conventional `scripts/` name:
renaming it would break CI and existing developer commands.

| Program | Purpose |
| --- | --- |
| `validate_all.py` | **Canonical global command**: tests, all 81 benchmark cases without and with real Codex, invariant/quality evidence, and package build; historical runs preserved by default |
| `run_full_validation.py` | Lower-level orchestrator, also usable without the real labeler for CI diagnostics |
| `compare_real_labeler.py` | Per-case real Codex inference, compare 81 source diagrams, export label review CSV |
| `compare_labeler_modes.py` | Synthetic-label integration diagnosis; not evidence of real inference |
| `build_release.py` | Build and smoke-test wheel/sdist and record their checksums; defaults to ignored `dist/` |
| `verify_portable_tempdirs.py` | Check the exact Git-pinned tempdir dependency |
| `verify_offline_release_install.py` | Windows-only wheel and local wheelhouse diagnostic |

## Run all checks, using real inference

Install `.[dev,mcp,labeler-codex]`, check Graphviz (`dot -V`),
authenticate the Codex CLI (`codex login`) and review any MCP connectors
inherited by the p4-codex-bridge. From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\validate_all.py --acknowledge-source-transmission
```

This **one command** runs both disabled and **real codex** across the same
81 benchmark cases; it does not run the mock labeler. Because real requests
may transmit source excerpts and incur provider usage, it requires the
transmission acknowledgement flag. It never starts in GitHub CI.

The inspectable reports go to
[`output_validation/`](../output_validation/README.md), under a dated
`validation-YYYY-MM-DD_HH-MM-SS_<id>` directory. The global command now
**preserves all previous runs by default**, including successful and failed
ones. Optional `--prune-managed-history` explicitly opts into removal of older
self-marked runs after full PASS; avoid that flag when keeping evidence.
Unknown data, `.serena/`, `.git/`, unrecognized output folders and all
protected Windows paths are always preserved. Temporary
working directories and caches are under `%TEMP%`, outside the repository.
`_avast_` may be antivirus-owned and is not forcibly removed.

For a targeted run without Codex (development only):

```powershell
.\.venv\Scripts\python.exe scripts\run_full_validation.py
```

The separate `--with-labeler` flag of the lower-level runner is
**mock-only** and must not be mistaken for the global real evaluation.

The real-labeler report tests response provenance, size and graph
invariance. Quality of the text, possible flow branches and V1/V2 semantic
uncertainty require additional review. The runner does not claim that
generating a picture or receiving an AI label implies a semantic PASS.

See [testing](../docs/reference-testing.md),
[setup](../docs/development.md), [benchmark corpora](../benchmark/README.md)
and [consumer output](../output_graphs/README.md).


### Real Codex timeout configuration

The default timeout for each Codex label request is **180 seconds**
(instead of P4's 20-second library default). Override it from the
environment when genuinely required, e.g.
`$env:P4_LABELER_PROVIDER_TIMEOUT='300'` in PowerShell. One bounded
retry occurs only after `ProviderTimeout`, with a two-second delay;
other errors remain errors and `mock` is never substituted. Large
diagrams can trigger multiple independent Codex calls and therefore
take longer than this per-request limit. First test a small real subset.
