# Tests of the benchmark machinery

Run alongside `tests/` when invoking `python -m pytest -q`.

| Test module | Invariant |
| --- | --- |
| `test_harness.py` | Canonical evaluator selection and structural checks |
| `test_oracles.py` | Source-derived Python semantics, not generated artifacts |
| `test_phase3_oracles.py` | Ordered cases, guards, captures and invalid graphs |
| `test_phase4_oracle_adversarial.py` | Mutated match edges, module resolution and false paths |
| `test_phase4_1_oracle_adversarial.py` | Return, context and branch mutation obligations |
| `test_metamorphic_preconditions.py` | Preconditions of source transformations |

Names inherited from a regression criterion identify the property being
tested, not obsolete product APIs. Required fixture sources live in
`../regressions/`. Tests allocate temporary work under the operating
system's temp directory and do not mutate fixture sources.
