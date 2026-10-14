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

## Live Codex timeout correction (14 October 2026)

A partial Windows run on the pre-fix build processed 51/82 cases before
manual interruption: 14 provider PASS and 37 `ProviderTimeout` failures.
The 14 successful cases produced 100 genuine Codex labels; 31 replaced
the explicit `Propagate exception` transfer caption with a general
function summary. These are not 37 independent graph-semantic failures.

The cause of the unexpectedly short provider timeout was in
`SemanticLabelerTools._client()`: it instantiated P4 `Settings` directly,
thereby discarding `P4_LABELER_PROVIDER_TIMEOUT`. P4's built-in default is
20 seconds. The adapter now constructs validated settings from the
environment, retaining the explicitly requested provider and reduction
attempts. The previous runner tried to supply 120 seconds, but that value was
discarded by the adapter. The corrected real-provider default is 180 seconds,
with an explicit environment override and one bounded timeout retry; this
alone does not prove provider reliability.

External labels also no longer replace source-derived control-transfer or
generator-event labels. Such nodes retain deterministic descriptions of
`raise`, propagated exceptions, `break`, `continue` and `yield`.

Before launching another full suite, diagnose with a small *real* Codex
subset, using a fresh TEMP result directory and
`scripts/compare_real_labeler.py --only CASE_ID ...` and the required
`--acknowledge-source-transmission` flag. A complete re-run and factual
label review are still necessary; never turn timeouts into semantic PASS.

## Node-specific P4 label requests

An additional pre-fix semantic issue was that PyFlowMap sent the **enclosing
function** as P4's subject for every graph activity. A real model often then
returned a complete function summary for assignment/call nodes, even after
the transfer-caption protections. P4 requests now use the actual activity
node as subject (`kind=activity`), keep the function's source as context,
and explicitly ask for a faithful *single-node* label. This change is
covered by a contract regression test but still needs checking against
real Codex responses; it is not evidence of factual-semantic PASS yet.


## Live Codex timeout policy and transient retries

PyFlowMap applies a **180-second default per Codex label request**, rather
than inheriting P4's 20-second default. The environment variable
`P4_LABELER_PROVIDER_TIMEOUT` overrides that number explicitly, including
for the full validation runner. The configured value is forwarded through
P4 `Settings.from_env()` to the bridge's `timeout_seconds`.

On a genuine `ProviderTimeout`, PyFlowMap waits two seconds and retries
**once** with the real provider. It does not retry non-timeout errors and
never falls back to `mock`. Retried success adds
`pyflowmap_codex_timeout_retried` to the label warnings; a second timeout
remains a reported failure. Each timeout applies per label, not per graph;
a large graph can legitimately take longer than 180 seconds total.

Avoid raising this ceiling without limit: a longer timeout and retry can
consume substantial time and provider quota across 81 benchmark programs.
Verify one formerly successful and one previously timed-out case on the
local Codex-authenticated workstation before another complete run. This
change is covered by offline contract/regression tests, not by live Codex CI.


## Call-site specificity in the October 2026 Codex pilot

The two real-provider pilot programs passed graph invariants (23 nodes/31
edges for `independent-v1-c02`; 5 nodes/5 edges for `c19`), but `c02`
exposed a semantic presentation defect. Four different calls to `emit`
were all labeled "Return the supplied code unchanged": the label described
the callee implementation, not the distinctive arguments of the individual
match branches (`north_east`, `other_quadrant`, `halt`, `unreadable`).

PyFlowMap now extracts each call-site expression from the original source
AST (never executes it), bounded and matched by source line and callee.
Ambiguous same-line calls are not guessed. The P4 label request explicitly
identifies the expression as the action to label, while retaining the
callee source as reference context. JSON external-label provenance and the
real-provider CSV both expose `source_call_expression` for review.
This is verified by deterministic regression tests; full semantic approval
requires a new **real Codex** pilot rather than assuming that better context
guarantees an accurate model output.

## Pilot review: exact literals and malformed quotes

The second authenticated Codex pilot (`independent-v1-c02` and `c19`)
completed without timeouts. Both graphs retained the same nodes and edges.
All four `c02` call-site activities now refer to their distinct arguments.
However, Codex returned two labels missing the terminal apostrophe:
`Call emit with the literal argument 'halt` and the analogous
`'unreadable` label. Technical graph PASS must not imply that these
captions have passed independent human-semantic review.

PyFlowMap now closes **only that precise missing quote** if the original
call-site expression AST contains exactly one positional *string literal*,
its quote is balanced in the source, and the model output ends with its
verbatim opening-quote-and-value suffix. Ambiguous or mismatched cases are
not modified. The adjustment emits the explicit per-node warning
`pyflowmap_source_literal_quote_closed`, exposed in the real Codex review
CSV. A correction that would exceed the diagram label limit fails instead.
This deterministic repair does not change graph topology, execute source,
or falsely claim independent semantic validation.


## October 2026 full real-Codex comparison-operator regression

The authenticated full Windows run processed all 81 programs. Its original
real-inference results were 75 technical PASS and six FAIL, each reporting
`Invalid external semantic label` (cases: `iot`, `workflow`,
`independent-v1-c10`, `independent-v1-c12`, `independent-v1-c28`,
`independent-v2-v02`). The six programs contain comparisons, but the
report did not capture the precise rejected label or rule.

Previously PyFlowMap rejected *any* `<` or `>` in model output. Ordinary
comparison labels such as `x < 0`, `temperature > 90`, `x <= threshold`
are now accepted; Mermaid and DOT renderers already escape such text.
Markup-looking `<tag` prefixes, multiline labels, control characters,
invalid types and excessive length still fail closed. An invalid label
carries a safe categorical reason, and the real comparison report uses
`INVALID_EXTERNAL_LABEL` instead of generic `ANALYSIS_ERROR`.

This is a candidate fix, not a claim that the six historical failures
were comparisons. Re-run those six cases only with **real Codex**, keeping
the original results untouched. Treat all new provider/model errors as
failures; retain semantic REVIEW on technical PASS.
