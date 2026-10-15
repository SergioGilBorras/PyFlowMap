# Independent semantic oracle - Phase 4

`oracles_phase4.py` preserves source-derived checks from previous versions and strengthens evaluation of `match/case`. Analyzed programs are parsed as AST and are never imported or executed.

## Evaluation rules

The evaluator checks valid routes and excludes impossible routes. Selectors, guards, and captures are identified by their local case index, AST pattern location, and entry symbol. Reachability stops when it returns to a selector from the same `match`, so a later loop iteration is not mistaken for backtracking within one execution.

For each decision, the oracle validates Yes/No labels and their permitted destinations. A successful pattern route must bind all captures required by that pattern before guard evaluation or body execution. Compound guards remain REVIEW when the graph does not identify the aggregate short-circuit result.

Entry and target resolution use the qualified module and definition path to avoid selecting a homonymous function from another module.

## Warnings

Warnings are classified by consequence: data-dependent branching (informational), dynamic resolution (REVIEW), approximation (REVIEW), unrepresented activities (REVIEW), and expansion limits (REVIEW). An unknown warning does not change the semantic status by itself.

## Adversarial tests

`test_phase4_oracle_adversarial.py` retains a valid route while adding an invalid route to test rejected patterns, false guards, and bypassed captures. It also tests multiple `match` statements in one function, nesting, loops, homonymous functions, compound guards, and warning classification.

Run:

```powershell
python -m pytest -p no:cacheprovider -q benchmark/test_phase3_oracles.py benchmark/test_phase4_oracle_adversarial.py
python -m benchmark.run_phase4 --output benchmark-results/phase4-oracle-20261013/normal-final
python -m benchmark.run_phase4 --output benchmark-results/phase4-oracle-20261013/strict-final --strict
```

Results use a new directory and do not replace V4, Phase 2, or Phase 3.
