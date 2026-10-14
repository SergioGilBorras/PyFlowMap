# Benchmark executors

These scripts operate on **developer test data only**. They never import or
execute analyzed fixture programs; they call the installed PyFlowMap CLI to
build diagrams, then inspect their results.

| Module | Purpose |
| --- | --- |
| `run.py` | Structural checks, 15-case canonical semantic evaluation and optional eight-case control-flow source bank |
| `metamorphic.py` | Domain-neutral graph invariance under safe source transformations |

Run modules from the repository root:

```bash
python -m benchmark.runners.run --output pyflowmap-output/baseline --render
python -m benchmark.runners.run --cases-file benchmark/control-flow/cases.json --fixtures-root benchmark/control-flow/fixtures --output pyflowmap-output/control-flow --render
python -m benchmark.runners.metamorphic --output pyflowmap-output/metamorphic
```

The `--strict` flag is stronger than ordinary semantic checking: an
uncertain REVIEW may become a nonzero exit even if no reproducible FAIL is
present. Source corpora remain unmodified. Temporary transformation
workspaces use the OS temporary directory; durable outputs go under
ignored `pyflowmap-output/`.
