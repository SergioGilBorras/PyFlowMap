# Testing and reference cases

Test and benchmark code are **development tooling**. The installed
PyFlowMap application does not need them in order to analyze a Python
project. Generated diagrams, galleries, audit ZIPs and local manifests
must not be included in the wheel or source distribution.

## Sources of verification

- `tests/` contains unit, interface, generic semantic regression, packaging
  and protocol tests.
- `benchmark/` contains reusable programs, semantic criteria and runners
  used to assess behavior beyond individual units.
- Independent V1 (28 programs), V2 (30 programs) and the smaller smoke corpus
  are retained as **known regression banks**, not permanent hidden tests.
- Additional read-only reference snapshots under test fixtures must be
  identified by stable content or commit hashes. The analyzer must not
  overwrite their source.
- `.github/workflows/` runs cross-platform checks against a specific
  remote commit, not an uncommitted working tree.

These corpora are examples of Python semantics. They must never drive
hard-coded rules for application names, repositories or fixture identifiers.

## What results mean

| Result | Interpretation |
| --- | --- |
| `GENERATED` | An output file set exists; no semantic approval implied |
| `PASS` | The specified property was reviewed and satisfied |
| `REVIEW` | A judgment/abstraction remains, possibly because runtime data are unknown |
| `FAIL` | A reproducible semantic property is violated |
| `UNSUPPORTED` | Declared out-of-scope construction |
| `NOT_EVALUATED` | No semantic evaluation was carried out |

Separate structural validations (valid JSON/SVG/PNG, connected graph,
local links) from semantic decisions about executable paths.

## Running checks

```bash
python -m pip install -e '.[dev,mcp]'
python -m pytest -q
python -m ruff check src tests scripts
python -m pip check
```

Use the documented `benchmark.runners` module entry points for benchmark
programs. Do not silently substitute older oracles, or change an oracle merely
to turn a real FAIL into PASS. Verify both a correct graph and a deliberately
incorrect one when testing an evaluator fix.

## Clean reference run

Recreate an ignored output directory such as `pyflowmap-output/release-validation/`
from an empty folder when preparing a release candidate. Record the exact commit and local state,
parameters, Python/Graphviz versions, checksums, label-provider selection,
warnings and evaluation scope.

Results must be **newly generated** from that exact code. Keep reusable
program sources, fixture manifests and evaluators in Git; treat generated
validation images, galleries, temporary files and ZIPs as removable outputs
rather than runtime dependencies.

Cross-platform success is only established when Windows, Linux or macOS
jobs actually finish on the **same candidate commit**. Installing a wheel
outside the checkout tests packaging more effectively than importing a
source checkout.

Real `codex` labeling is optional and requires explicit authorization to
transmit selected code excerpts. `mock` exercises integration only.


## Complete fresh local validation

Use the developer-only `scripts/run_full_validation.py` runner rather than
manually reusing old `pyflowmap-output/` results. It generates a new
`%TEMP%\pyflowmap-output\full-*` directory on Windows with test logs, 15+8
canonical semantic evaluations, metamorphic regressions, V1/V2 generation
reports, a package build and a `semantic-review-queue.md`.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp]'
.\.venv\Scripts\python.exe scripts\run_full_validation.py
```

The second mode compares `disabled` with synthetic `mock` labels across the
15 baseline + 28 V1 + 30 V2 programs. It requires access to the optional
private P4 labeler dependency and does not execute real Codex inference:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler]'
.\.venv\Scripts\python.exe scripts\run_full_validation.py --with-labeler
```

The runner also redirects temp/cache variables for subprocesses, and
checks whether `pytest-cache-files-*` or `_avast_` **newly appeared** in
the repository root during its run. New paths are reported, never deleted
or attributed to PyFlowMap without evidence. For the standalone pytest
command, root `conftest.py` redirects temporary workspaces and disables
pytest's cache provider. OS/antivirus activity is not under Python control.

The scripts do **not** delete existing results: a fresh, unique target avoids
stale evidence without risking accidental deletion of user files or
protected ACL paths. Review old ignored results separately before cleanup.

An automatic `GENERATED` status for V1/V2 is not a complete semantic
assessment. The review queue records them as `NOT_EVALUATED`; a complete
semantic approval requires examining the graph's exact paths and assigning
independent obligations or conducting manual review, not simply generating
images.


## Actual live Codex inference — separate from mock

Use real inference for 81 retained regression cases (15 baseline, 8
control-flow, 28 V1, 30 V2), plus `examples/basic_pipeline.py`. This
requires the optional `.[labeler-codex]` extra, Codex CLI login, and
explicit permission to transmit selected source excerpts. The upstream
bridge isolates the filesystem workspace but permits inherited external MCP
tools, which may have side effects; inspect their configuration before use.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler-codex]'
codex login
.\.venv\Scripts\python.exe scripts\run_full_validation.py --with-real-labeler --acknowledge-source-transmission --output-parent .\pyflowmap-output
```

The earlier `--with-labeler` flag tests only `mock`; it is not a substitute
for this live run. Unit tests and offline oracles still use deterministic
execution for reproducibility. The live run saves `real-labeler-report.json`
plus `label-quality-review.csv` and separate `disabled/` and `codex/`
diagrams. These establish real provider provenance and invariant graph shape,
**not** automatically the factual correctness of generated labels. V1/V2
remain `NOT_EVALUATED` by an independent semantic oracle until reviewed.

Only **temporary internals** are forced below `%TEMP%`. Inspectable output
may be stored in the ignored repository `pyflowmap-output/` using
`--output-parent`, or in system TEMP by default. Existing results are not
overwritten or deleted.
