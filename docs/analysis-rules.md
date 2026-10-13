# Analysis rules and 1.0 scope decisions

This document records the current static-analysis contract and classifies the
known findings from Phase 5.2 and the available independent V1 review. The
review material is preserved in
`benchmark-results/phase5_2-consolidation-20261013/AUDIT-V1-REVIEW.md`.
No findings were derived from the reserved second independent battery.

## Current rules

1. **Entry and scope.** Use an explicit `MODULE:SYMBOL` when supplied. Otherwise
   accept a unique `main`, or a unique public callable. `--scope` narrows entry
   discovery; local project dependencies may still be indexed outside it.
2. **Calls.** Retain significant calls in source order. Resolve local functions,
   simple imports, `self` methods, inferred local instances, and supported
   `super()` cases when the AST provides enough evidence. A call node records
   its resolution state, caller, source location, candidate targets, and whether
   the callee body is expanded, summarized, or referenced.
3. **Expressions.** `and` and `or` use source order and short-circuit paths.
   Conditional expressions preserve both alternatives. Comprehensions retain
   source-located summaries for the expression, filters, and calls; they do not
   invent a fixed iteration count.
4. **Control flow.** `if`, `match/case`, `for`, `async for`, and `while` retain
   their selection and loop outcomes. `Assign`, `AnnAssign`, `AugAssign`, and
   named expressions remain source-linked activities inside the path that
   executes them. Assignment RHS and target expressions preserve Python's
   evaluation order and known calls. Different `match/case` bodies are never
   connected sequentially; later uses are reached only from normal branch
   exits. Paths that skip an assignment remain visible and are not treated as
   definitely initialized. Tuple/list unpacking is explicit and carries
   possible `TypeError`, `ValueError`, or iterator exceptions. `break`,
   `continue`, `return`, and `raise` terminate only their active path. `for/else`
   and `while/else` enter `else` only on normal exhaustion. `try/finally` and
   context managers carry pending transfers through cleanup. Closing a suspended
   generator injects `GeneratorExit` at the yield point, so lexical handlers and
   cleanup suites are traversed.
5. **Context and asynchronous operations.** `with` and `async with` show
   manager entry, body, reverse-order exit, and possible suppression. `await`
   shows suspension, a possible resume, and a possible exception. Asynchronous
   generator closure is represented as `aclose`/`GeneratorExit` and traverses
   lexical cleanup. Runtime scheduling and exception matching are not inferred.
6. **Definitions and statements outside expanded control flow.** Nested function
   definitions are explicit activities; their bodies remain deferred until a
   statically identified call is expanded. Class definitions, imports, deletes,
   and other unsupported executable statements remain source-located summary
   activities. Their contained calls are listed in metadata where applicable;
   internal behavior is not claimed to be expanded. `pass`, `global`, and
   `nonlocal` add no independent runtime activity.
7. **Expansion.** Expand a project-local callee only when the policy allows it,
   it is not recursive or already expanded, and its body has useful control
   flow. Depth and expansion boundaries never erase the call: source locations,
   body status, candidate calls, and limits remain available. A visible label
   indicates when additional call sites are available only in graph metadata.
8. **Contraction and views.** Simplify only linear activities when no decision,
   significant call, state change, or branch topology is lost. The node budget
   is soft. `process-summary` is a call outline, not UML activity. The
   hierarchical view summarizes phases and links to detailed activities.
9. **Provenance.** Activities and summaries retain source symbols and locations.
   A summary states its scope and does not claim that its internal statements
   were expanded.

## Known findings and decisions for 1.0

### Correctable defects

These were determinable from syntax but could be omitted or presented
ambiguously. They are now closed by explicit representation and regression
tests; they are not accepted permanent limitations.

| Finding / Python construction | Evidence | Correction scope and decision |
|---|---|---|
| Assignments in branch-local blocks were omitted when their later use appeared outside that block, including assignments in `match/case` arms followed by another `match`. Augmented-assignment target calls could also disappear or appear after the RHS. | `src/pyflowmap/analysis.py::_block`, `_match`, `_expression`; regressions in `tests/test_statement_representation.py`. | **CORREGIBLE — closed.** Emit assignment activities in their executing branch with statement metadata and source location; preserve RHS/target call order, and keep normal exits separate from `return`/`raise`. No value-flow or definite-initialization claim is made. |
| Executable AST statements without an analyzer branch: imports, deletes, nested definitions, class definitions, and future statement nodes. | The statement dispatcher in `src/pyflowmap/analysis.py::_block`; generic regression in `tests/test_analysis_scope.py`. | **CORREGIBLE — closed.** Preserve an activity, source location, statement kind, contained call expressions when available, and a warning describing what remains summarized. Import, delete, and class construction retain possible exception routes. |
| Per-item calls in comprehensions and the outer iterable were kept only in nested metadata; the outer iterable was not emitted as its own evaluation activity. | Historical `analytics` graph and the `comprehension-calls` / `call-visibility` findings; regression `test_comprehensions_show_outer_iterable_and_per_item_calls_without_fake_paths`. | **CORREGIBLE — closed.** Evaluate the outer iterable as an expression activity. Show per-item call names grouped by filter/iterable/result role, with call phases and locations in JSON. Do not invent one iteration or a fixed call count. |
| Internal calls beyond the first six in a summarized callee were present in JSON but silently absent from the activity label. Unresolved call nodes also lacked a readable explanation of resolution limits. | `src/pyflowmap/analysis.py::_call`; regressions `test_summarized_call_label_discloses_calls_kept_only_in_metadata` and `test_unresolved_call_explains_known_expression_and_unknown_target`. | **CORREGIBLE — closed.** The label states how many calls remain in metadata; the graph records displayed/undisplayed counts. Each call node explains whether its target was resolved, is only a candidate, or remains unknown. |
| Warnings said only “approximated” or “dynamic,” without distinguishing known paths from runtime-dependent outcomes. | `src/pyflowmap/analysis.py` warnings for `try/except`, `with`, `await`, generators, comprehensions, iterator advancement, and summarized calls; assertions in `tests/test_analysis_scope.py` and existing language tests. | **CORREGIBLE — improved.** Warnings now state the represented fact, possible alternatives, and the part that cannot be determined. This does not change an oracle or turn uncertainty into certainty. |
| Relative navigation from detail indexes back to parent diagrams. | `tests/test_activity_uml.py` checks generated index links; Phase 5.2 `artifact-validation.json` records gallery checks. | **CORREGIBLE — no open failure.** Existing generation and navigation regressions pass; no broken relative route is recorded in the preserved validation. |
| Demonstrable impossible routes or lost `return`/`raise`/loop-transfer paths within modeled syntax. | `tests/test_analysis.py`, `tests/test_activity_uml.py`, `tests/test_match_and_loop_semantics.py`, `tests/test_phase5_1_closure.py`, and `tests/test_phase5_1_language_constructs.py`. | **CORREGIBLE — no reproducible open defect found.** Keep the existing path-specific regressions. A future counterexample is a new defect, not a static-analysis limitation. |

### Partial static information

The analyzer can identify source operations, possible routes, or candidate
targets. The exact runtime outcome is not generally knowable from the AST.

| Finding / construction | Evidence in the available reviews | Scope and decision |
|---|---|---|
| Exception occurrence and `except` / `except*` selection. | Historical `etl`; V1 `c07` and `c22`; `AUDIT-V1-REVIEW.md` records handler and propagated routes. | **PARCIAL.** Keep the try-success route and every declared handler. Ordinary `except` alternatives remain runtime-dependent. For `except*`, preserve source order, allow multiple handler bodies for distinct subgroups, and represent the possible unhandled remainder. Do not predict which exception values match. |
| `with` / `async with` entry, exit, and suppression. | Historical `resources`; V1 `c23`; tests cover body, exit, and possible suppression. | **PARCIAL.** Preserve entry/body/exit and pending transfers. `__exit__` or `__aexit__` can suppress or replace an exception depending on runtime behavior. |
| Awaited calls and asynchronous iteration. | Historical `network`; V1 `c07` and `c22`. | **PARCIAL.** Show the await/iteration operation, resume or exhaustion, and possible exception. Awaitable outcomes, exception types, and scheduler ordering remain unknown. |
| Injected constructors, receiver dispatch, decorators, and inherited methods. | Historical `cli`, `resources`, `security`, and `plugins`; V1 `c19` resolves a `super()` candidate. | **PARCIAL.** Keep statically supported candidates and mark dynamic/decorated targets as possible or referenced. Do not claim a unique runtime callable where injection or dispatch can replace it. |
| Callee bodies at recursion or configured depth boundaries. | Historical `scheduling` and `algorithms`; V1 `c11` records a resolved local function with a summarized body. | **PARCIAL.** Keep the call, target, source interval, nested call references, and expansion reason. Do not duplicate recursive bodies or imply that a summary is complete execution detail. |
| The historical evaluator defines call visibility as a standalone `significant_call` node, so it can say “metadata-only” even when a call name is printed inside a source-linked summary activity. | Historical `scheduling` (`notify`) and `analytics` (`normalize`); marker rules are in `benchmark/run.py` and findings in `historical-15-comparison.csv`. | **PARCIAL — evaluator boundary, not a lost call.** The activity label names the possible child/per-item call and JSON gives its target/location. Conditional or repeated execution remains summarized, so REVIEW is appropriate. Do not alter the historical oracle to force PASS. |
| Generator `yield` / `yield from` and asynchronous generator closure. | V1 `c14`; `tests/test_phase5_1_language_constructs.py`; `tests/test_semantic_v2_audit_regressions.py`. | **PARCIAL.** Yield, suspension, resume, injected `GeneratorExit`, and source-visible `except`/`finally` cleanup are represented. Concrete `send`, `throw`, iteration count, delegation protocol, cleanup outcomes, and dynamic exception handling depend on the caller and runtime. |
| List, set, dictionary, and generator comprehensions. | Historical `analytics`; V1 `c26`; `tests/test_analysis_scope.py` verifies immediate outer-iterable evaluation and visible grouped per-item call names. | **PARCIAL.** Keep the expression and source locations in a summary. The input size, actual iterations, per-item predicate results, and lazy consumption cannot be inferred. |
| Branch values and return values derived from runtime data. | `if`, pattern guards, loops, and non-literal `return` expressions in the historical graphs. | **PARCIAL.** Preserve both feasible static outcomes and the return expression. Only literal values are reported as known; do not invent a concrete result. |
| Dense exception detail in V1 `c26`. | `AUDIT-V1-REVIEW.md` records the diagnostic aggregation from 130 nodes / 194 edges to 66 / 95 while preserving six source IDs and locations. | **CORREGIBLE — presentation only, mitigated.** The detailed graph remains complete and may be dense. Use the hierarchical view and metadata to navigate; do not remove exception routes to make the image smaller. |

#### Case-level review evidence

The historical cases below were the nine REVIEW rows in the Phase 5.2
15-case matrix. The source locations and graph paths make each classification
auditable; they do not turn runtime-dependent behavior into a failed graph.

| Case | Source evidence | Graph evidence | Classification and decision |
|---|---|---|---|
| `etl` | `benchmark/fixtures/etl/transform.py:14,17` | `historical-normal-final7/cases/etl/transform_process_batch.json`: `n2` iterator error alternative, `n9` exception dispatch, `n12` uncaught propagation; `n7` and `n15` summarized local calls. | **PARCIAL** — exhaustion and exception paths remain separate; iterator and handler types are runtime-dependent. |
| `cli` | `benchmark/fixtures/cli/entrypoint.py:13-19` | `historical-normal-final7/cases/cli/entrypoint_main.json`: `n5` unresolved constructor; `n6` possible `Worker.execute` candidate; `n11` exception dispatch. | **PARCIAL** — injected receiver/candidate is visible; the runtime object and handler match are unknown. |
| `network` | `benchmark/fixtures/network/service.py:10-15` | `historical-normal-final7/cases/network/service_handle.json`: `n4`/`n7` await and resume paths; `n12` dispatch; `n15` propagation. | **PARCIAL** — await/resume and exception alternatives are visible; scheduling and exception type are unknown. |
| `resources` | `benchmark/fixtures/resources/io.py:16-19` | `historical-normal-final7/cases/resources/io_store.json`: `n2` unresolved manager constructor; warning records dynamic context suppression. | **PARCIAL** — manager entry/body/exit are modeled; runtime `__exit__` behavior is not inferred. |
| `scheduling` | `benchmark/fixtures/scheduling/scheduler.py:11-18` | `historical-normal-final7/cases/scheduling/scheduler_schedule.json`: `n4` shows `run_one`, its `notify` call, and the target source interval. | **PARCIAL** — the call and conditional child call are retained; body paths are summarized at the expansion boundary. |
| `algorithms` | `benchmark/fixtures/algorithms/recursion.py:8-16` | `historical-normal-final7/cases/algorithms/recursion_walk_tree.json`: `n9` lists `transform` and recursive `walk_tree` candidates with source locations. | **PARCIAL** — the recursive call is visible; finite expansion cannot represent arbitrary recursion. |
| `security` | `benchmark/fixtures/security/permission.py:10-13` | `historical-normal-final7/cases/security/permission_check_permission.json`: `n5` is the unresolved `resource.startswith` call; the expression remains visible. | **PARCIAL** — the method invocation is known, but receiver type and implementation are unresolved. |
| `plugins` | `benchmark/fixtures/plugins/registry.py:18-19` | `historical-normal-final7/cases/plugins/registry_dispatch.json`: entry decorator metadata and `n2` unresolved `handler.execute` call. | **PARCIAL** — the source callable is visible; decorator replacement and receiver dispatch remain possible. |
| `analytics` | `benchmark/fixtures/analytics/metrics.py:9-12` | `historical-normal-final7/cases/analytics/metrics_summarize.json`: `n2` comprehension summary; `n5`/`n6` calls using the summarized result. | **PARCIAL** — expression/calls are retained; cardinality and per-item outcomes depend on data. |

The separate V1 audit examples use different fixture IDs. Its available source
and node evidence is recorded in
`benchmark-results/phase5_2-consolidation-20261013/AUDIT-V1-REVIEW.md`:
`c07` (`jobs.py:2,4-5`; `n2`, `n3`, `n9`, `n13`, `n16`), `c11`
(`ticket.py:3-13`; `n4`), `c14` (`queue.py:5,7`; `n6`, `n10`), `c19`
(`vehicles.py:17`; `n2`), `c22` (`batch.py:3,7-8`; `n2`, `n8`, `n12`),
`c23` (`emergency.py:3,5-8`; `n4`, `n10`, `n13`, `n26`), and `c26`
(`records.py:2-8`; `n17`, `n23`). They map to the partial exception,
expansion, generator, inheritance, asynchronous, context-manager, and
comprehension limits above.


### V2 closure regressions

Four source-determinable omissions reproduced with new, domain-neutral fixtures
are closed by `tests/test_semantic_v2_audit_regressions.py`:

- Generator and asynchronous generator close events now inject `GeneratorExit`
  at the suspended yield and flow through lexically visible `except` and
  `finally` blocks. `send`, `throw`, delegated iterator behavior, and runtime
  cleanup outcomes remain partial.
- `except*` is modeled as ordered subgroup dispatch. Multiple clauses may run
  for different portions of an exception group; handler-raised exceptions,
  an unhandled remainder, and `finally` remain possible routes.
- Assignments whose targets feed a `match` subject appear as source-linked
  activities. Destructuring assignments and loop/context targets carry possible
  unpacking failures instead of silently continuing.
- Calls reached through `finally` retain the caller symbol and call-site line;
  resolved target summaries retain their own source interval.

These changes describe static alternatives. They do not choose an exception,
subgroup, generator input, or cleanup outcome at runtime.

### Accepted static-analysis limits

These are not permanent defects. PyFlowMap must not guess an exact result when
it requires program execution or environmental knowledge.

| Finding / construction | Evidence | Decision |
|---|---|---|
| Arbitrary dispatch through reflection, `getattr`, monkey patching, dependency injection, higher-order values, or runtime subclass selection. | Historical `cli`, `security`, `plugins`; `src/pyflowmap/project.py` indexes syntax and simple relationships rather than executing object state. | **LIMITACIÓN ESTÁTICA.** Show the call expression and any defensible candidates; exact target selection is unavailable without runtime state. |
| `eval`, `exec`, import hooks, external module initialization, and effects of third-party libraries. | Import and unresolved-call summaries in `src/pyflowmap/analysis.py`; external source is not imported or executed. | **LIMITACIÓN ESTÁTICA.** Preserve the syntactic operation and possible exception; external behavior is outside the analyzed source. |
| Actual task scheduling, thread interleavings, network responses, and data-dependent exception values. | Historical `network` and `resources`; the graph marks await and exception dispatch as runtime-dependent. | **LIMITACIÓN ESTÁTICA.** Represent alternatives only; do not select a concrete schedule or result. |
| Exact termination of arbitrary recursion or execution of an unbounded loop/generator. | Historical `algorithms`; configured depth and generator warnings in `analysis.py`. | **LIMITACIÓN ESTÁTICA.** Bound expansion and preserve the recursive/yielding call with provenance. No finite static unrolling can represent every execution. |
| Exact behavior of a class body, metaclass, descriptor, or context-manager protocol when its implementation is dynamic. | Class-definition summaries and `with` warnings in `src/pyflowmap/analysis.py`. | **LIMITACIÓN ESTÁTICA.** Retain the definition/manager activity, calls, and source; leave dynamic protocol outcomes uncertain. |

### Audit evidence that remains incomplete

The independent V1 aggregate is 13 bounded PASS, 15 REVIEW, and 0 confirmed
FAIL. Its per-case matrix was not included in the repository. The available
review supports the specific examples above, but the other REVIEW IDs cannot
be assigned reliably. This is an evidence gap, not a PyFlowMap semantic defect;
no labels have been inferred for the missing cases.

## How to read warnings

A warning should identify the source location, the fact represented, possible
routes or targets, and the runtime-dependent part. The JSON node metadata is
the detailed record for candidates, transfer type, source locations, and
summary scope. A warning about dynamic behavior alone does not imply that a
graph is wrong; a missing operation or impossible edge with a reproducible
source counterexample remains a correctable defect.
