# PyFlowMap product tests

The `tests/` directory tests the actual source package: analyzer flow,
Python language constructs, CLI and MCP contracts, layout/renderers,
package hygiene and optional label integration.

Run `python -m pytest -q` from the repository root. It discovers both
these tests and `benchmark/tests/` through `pyproject.toml`.

Pytest automatically loads `../conftest.py` to place disposable test
workspaces in the system temp directory. On Windows this is explicitly
the `%TEMP%` environment variable; on POSIX it follows the configured
system temp directory. The cache provider is disabled to avoid creating
`.pytest_cache` in the checkout.

Avoid writing temporary data under fixtures, source directories or the
repository root. Keep pinned source fixtures unchanged and generate
output only in isolated temp workspaces. `dist/` is for deliberate local
release artifacts, not per-test scratch.
