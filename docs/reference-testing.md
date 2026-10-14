# Complete testing and semantic assessment

This guide is for repository maintainers, not installed-wheel consumers.
PyFlowMap analyzes benchmark Python sources without importing or executing
them. Regression fixtures and independent oracles are retained in Git;
reports, rendered diagrams and binary packages are generated locally.

## What gets tested

| Source | Count | Deterministic | Real Codex | Meaning |
| --- | ---: | --- | --- | --- |
| `benchmark/fixtures/` | 15 | Structural + existing semantic oracles | Real labels, topology/provenance | REVIEW remains if an oracle cannot settle behavior |
| `benchmark/control-flow/fixtures/` | 8 | Structural + existing semantic oracles | Real labels, topology/provenance | Exceptions, cleanup, loop transitions |
| `benchmark/independent-v1/fixtures/` | 28 | Generation, sources hashes, diagrams | Real labels, topology/provenance | `GENERATED` is not a semantic PASS |
| `benchmark/independent-v2/fixtures/` | 30 | Generation, sources hashes, diagrams | Real labels, topology/provenance | `GENERATED` is not a semantic PASS |

Unit tests, lint, pip dependency checks, portable-tempdirs verification,
metamorphic graph invariants and clean wheel/sdist installation additionally
run in the same invocation. All **81** retained benchmark cases are covered
in both disabled and real-Codex diagram modes. No `mock` provider is used
by the global command.

## One-command full run on the authorized local workstation

Set up the Python development environment with the optional real labeler
and Graphviz (`dot`). Authenticate the Codex CLI (`codex login`) first.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler-codex]'
.\.venv\Scripts\python.exe scripts\validate_all.py --acknowledge-source-transmission
```

This command **transmits selected source excerpts to real Codex**, can
consume provider usage, and requires explicit acknowledgement. The upstream
bridge may inherit external MCP tools, which can cause side effects even
with its read-only filesystem sandbox: inspect that configuration and only
run on code you are authorized to transmit.

The validator uses one dated directory beneath
[`output_validacion/`](../output_validacion/README.md):

```text
output_validacion/validation-YYYY-MM-DD_HH-MM-SS_<id>/
  validation-summary.json
  semantic-review-queue.md
  logs/
  benchmark/disabled/{baseline,control-flow,independent-v1,independent-v2,metamorphic}/
  benchmark/codex/{disabled,codex}/
  benchmark/codex/real-labeler-report.json
  benchmark/codex/label-quality-review.csv
  packaging/
```

The `benchmark/codex/disabled` and `benchmark/codex/codex` folders
include direct per-case comparisons of the same 81 programs. The canonical
deterministic benchmark oracles run in `benchmark/disabled`; any semantic
gaps must be addressed through independent oracles or manual review, not
by changing labels or lowering criteria.

All caches and scratch work remain in the OS temporary directory
(`%TEMP%` on Windows). Output directories are ignored by Git. On a
technically successful replacement, only previously **marked, recognized**
generated validation runs are pruned; unknown directories, symlinks and
protected paths are preserved. If a step fails, the failed reports remain
inspectable and the previous successful evidence is not deleted. No
unknown or legacy `pyflowmap-output/` directory is automatically cleaned.
The running old Windows validation is not modified.

## Report statuses

- `PASS`: a specified structural or semantic property has passed.
- `FAIL`: a reproducible test, real-provider request or asserted property
  failed; it must be investigated, not hidden.
- `REVIEW`: unresolved static uncertainty or real-label quality requiring
  judgment.
- `NOT_EVALUATED`: no independent semantic test has yet been applied.
- `GENERATED`: diagram creation succeeded, but no semantic verdict follows.
- `UNSUPPORTED`: outside the documented static semantics contract.

**Technical PASS is not equivalent to complete semantic approval.** Real
Codex cannot magically determine every runtime branch, dispatch result or
external side effect. Closing REVIEW / NOT_EVALUATED requires written
review or an appropriate independent oracle. Re-running until all labels
look nice is not a reliable way to prove the graph correct.

## CI and packaging boundaries

GitHub Actions must remain offline with respect to real Codex inference:
pytest, deterministic bank runs and package smoke only. Cross-platform PASS
requires finishing on the same exact source SHA. The release builder
creates local artifacts; it does not merge, tag or publish a release. The
current Git-pinned dependencies remain an outstanding obstacle to
conventional public PyPI publication.

See [static analysis semantics](analysis-rules.md),
[benchmark contracts](../benchmark/README.md),
[developer utilities](../scripts/README.md), and
[consumer graph outputs](../output_graphs/README.md).
