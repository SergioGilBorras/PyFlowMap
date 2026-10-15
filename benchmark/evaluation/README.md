# Static semantic evaluators

These are **developer test oracles**, not PyFlowMap runtime modules. The
canonical import is `benchmark.evaluation.oracles_current.evaluate_semantics`
and its criteria version is `phase5.2`.

The evaluator is composed as
`oracles_current -> oracles_phase5_2 -> oracles_phase5 ->
oracles_phase4_1`, with additional source-semantic helpers tested independently.
The `oracles_phase*` components are imported by the canonical evaluator
or its mutation/regression tests.

| Module | Responsibility |
| --- | --- |
| `oracles_current.py` | Single chosen evaluator entry point and version |
| `oracles_phase5_2.py` | Exception dispatch and valid exceptional edges |
| `oracles_phase5.py` | Summary-specific criteria |
| `oracles_phase4_1.py` | Python semantic obligations reused by current evaluator |
| `oracles_phase4.py` | Additional match/dispatch checks under mutation tests |
| `oracles_phase3.py` | Match/guard checks under mutation tests |
| `oracles.py` | Base evaluator and negative-control comparison |

Do not change criteria to turn genuine FAIL results into PASS. Changes to the
canonical evaluator require both valid and deliberately invalid graph tests.
Generated results belong outside this directory.
