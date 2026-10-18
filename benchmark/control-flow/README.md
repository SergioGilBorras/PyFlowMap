# Python control-flow regression corpus

Eight retained generic Python examples test: ordered match/guards,
loop termination, pending return in finally, async context, generator close,
exception-group dispatch, comprehension filtering and nested calls.

This is **source data** (not an output directory). `cases.json` defines
the cases and `fixtures/` holds their Python source. The programs are
only parsed, never imported/executed.

```bash
python -m benchmark.runners.run --cases-file benchmark/control-flow/cases.json --fixtures-root benchmark/control-flow/fixtures --output output_validation/control-flow --render
```

This is now a *known* regression corpus; it cannot serve as a blind
independent evaluation. REVIEW can represent unavoidable runtime-dependent
uncertainty. Do not rewrite the fixtures to improve evaluation scores.
