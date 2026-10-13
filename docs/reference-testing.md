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

Use the canonical evaluation entry points under `benchmark/` for benchmark
programs. Do not silently substitute older oracles, or change an oracle merely
to turn a real FAIL into PASS. Verify both a correct graph and a deliberately
incorrect one when testing an evaluator fix.

## Clean reference run

Recreate `pyflowmap-output/final-validation-1.0/` from an empty output folder
when preparing a release candidate. Record the exact commit and local state,
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
