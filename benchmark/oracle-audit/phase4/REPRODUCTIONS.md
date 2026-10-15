# Adversarial reproductions of the Phase 3 oracle

The four cases use the new generic fixture `adversarial_match.py`. None of the fifteen historical fixtures was modified.

## Before the evaluator correction

`benchmark/test_phase4_oracle_adversarial.py` was first run while importing `benchmark.oracles_phase3.evaluate_semantics`. It produced **4 failures**:

1. Adding a No edge from the selector to its own body still returned PASS.
2. Adding a No edge from a guard to its own body still returned PASS.
3. Keeping the valid route and adding selector Yes -> guard still returned PASS, although it bypassed a required capture.
4. Two `match` statements reused case indices and caused a correct graph to return FAIL.

The first three mutations retained the correct route as well. They demonstrate that checking only for the existence of a valid route is insufficient.

## After versioning Phase 4

The same tests import `benchmark.oracles_phase4.evaluate_semantics`: the three additive mutations are rejected and the two correct matches no longer collide. Further tests cover nested matches, matches inside a loop, homonymous functions in different modules, compound guards, and warning categories.

Reproduce with:

```powershell
python -m pytest -p no:cacheprovider -q benchmark/test_phase4_oracle_adversarial.py
```

The adversarial suite result is **9 passed**.
