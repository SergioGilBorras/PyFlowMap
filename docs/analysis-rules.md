# Static analysis: supported evidence and limits

This is the **current scope contract**, not a record of past development
phases. PyFlowMap parses Python with `ast`. It does not import or execute the
source under analysis. Diagrams express statically identifiable operations
and possible paths, not which path will be taken in a particular execution.

## Flow rules

| Construction | Representation | Boundary |
| --- | --- | --- |
| `if`, conditional expressions, `and`/`or` | Truth branches and short-circuit evaluation in source order | Actual truth values are unknown |
| `match/case` and guards | Ordered selection, captures and separate case bodies | Actual match result and guards are dynamic |
| `for`, `async for`, `while` | Iteration tests, exit/`else`, `break` and `continue` | Iteration count and iterator outcomes are unknown |
| `Assign`, `AnnAssign`, `AugAssign`, `:=` | Activity in the executing branch with source location; possible expression calls | No whole-program value inference |
| Tuple/list unpacking | Explicit operation and possible iteration/arity errors | Iteration data are unknown |
| `return`, `raise` | Pending transfer and exception/return flow; no fabricated normal continuation | Dynamic exception identity may be unknown |
| `try`, `except`, `except*`, `finally` | Possible dispatch, subgroup handling for `except*`, pending returns/exceptions through cleanup | Matching subgroups and residual exceptions are runtime-dependent |
| `with`, `async with` | Acquisition, body, reverse-order exits and possible suppression | `__exit__`/`__aexit__` effects are dynamic |
| `assert` | Conditional failure; optimized Python may omit assertions | Build mode and condition outcomes are not predicted |
| `yield`, `yield from`, async generators | Suspension/resumption and possible close, `GeneratorExit`, lexical handlers and cleanup | Consumer `send`/`throw`, when/if closed, dynamic generator behavior |
| `await` | Suspension, possible resumption and exception | Scheduling, task interleaving, awaitable outcome |
| Comprehensions | Outer iterable evaluation plus bounded summaries of per-item/filter/result calls | Exact iteration count and effects are not expanded |
| Function/method calls | Resolved, possible or unresolved target; source and expansion status | Runtime dispatch, decorators, reflection and monkey-patching |

A local function's body may be expanded subject to recursion, depth, and
presentation budgets. Calls to coroutine or generator functions create
deferred computation; their bodies must **not** be described as executing
merely because the callable was invoked.

Definitions, imports, class statements, deletion and other executable AST
statements which are not expanded retain an operation/summary with
provenance and an indication of their abstraction. `pass`, `global` and
`nonlocal` do not independently execute meaningful runtime activities.

## Correctness requirements

1. Respect Python's evaluation order where determinable from syntax.
2. Keep assignments in the branches where they execute. Separate `case`
   bodies must never run in sequence in the graph by accident.
3. Do not connect normal flow past `return`, `raise` or an uncaught exception.
4. On generator close from a suspended point, represent applicable
   `GeneratorExit` handling and `finally` cleanup, including async cleanup.
5. For `except*`, permit multiple handlers to process distinct subgroups in
   order; represent a possible unhandled remainder.
6. Preserve cleanup and pending control transfers through lexical `finally`
   and `with` scopes, without claiming to know dynamic suppression.
7. Retain source symbols, locations and warnings for compressed nodes,
   unresolved calls and possible paths. Never suppress a source operation
   silently just to meet a diagram-size limit.

## Presentation and provenance

`--view detailed` presents activity-level flow. `--view overview` is a
process/call summary rather than a UML activity diagram. `--view hierarchical`
offers navigable summaries linked to detailed activity diagrams. A summarized
call or node is not evidence that every internal path was expanded.

`--max-nodes` is a soft presentation budget. Source provenance and topology
take priority over reducing node counts. Node/edge identifiers, warnings,
known candidate callees and source locations are held in JSON; image labels
may be shorter.

## What static analysis cannot decide

- Runtime values, branch outcomes, all loop iterations, recursion depth or
  termination in the general case.
- Reflection, `eval`/`exec`, dynamic imports, decorators that replace
  callables, monkey-patching, dynamic method dispatch and external library
  effects in full generality.
- Real I/O and exception values or types produced by opaque code.
- Concurrency scheduling, task interleavings and every generator consumer
  interaction.
- Whether a context manager suppresses an exception on a particular run.

When only part of a path is known, the diagram should show **possible**
behavior with an explanation, not invent a guaranteed route.

## Evaluation vocabulary

| Status | Meaning |
| --- | --- |
| `GENERATED` | Files were produced and passed structural checks |
| `PASS` | Specified semantic obligations were examined and satisfied |
| `REVIEW` | Requires judgment or contains justified static abstraction |
| `FAIL` | A reproducible, statically determinable semantic obligation was violated |
| `UNSUPPORTED` | Out of the declared scope |
| `NOT_EVALUATED` | No semantic judgment was performed |

Generation must never be counted as semantic PASS. Known regressions belong
in `tests/` or `benchmark/`; generated diagrams and old audit logs do not
form part of the product. See [reference testing](reference-testing.md).
