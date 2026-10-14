# Regression bank V2

**30 cases across 38 Python source modules.** The retained source bank
includes `cases.json`, `source-hashes.json`, multi-module fixtures and
its runner. It covers exception groups, generators, assignment
placement, context managers, pattern matching and several call-resolution
patterns.

Run from the repository root:

```bash
python benchmark/independent-v2/run.py --list
python benchmark/independent-v2/run.py --validate-only
python benchmark/independent-v2/run.py --project-root . --output pyflowmap-output/bank-v2
```

Install PyFlowMap in the environment running the command, or specify
`--python` with the interpreter containing the installed package.

The runner parses source and launches PyFlowMap as a subprocess. It
does not execute fixture programs. `GENERATED` proves that the output
files were produced; the bank is `NOT_EVALUATED` semantically unless
a separate semantic assessment is performed.

This is a **known regression bank**.
Its fixtures are retained as developer assets and are never shipped
inside wheel or sdist. Write all outputs below ignored
`pyflowmap-output/`. Do not change sources to force a PASS.

See the [benchmark overview](../README.md).
