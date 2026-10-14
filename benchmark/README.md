# PyFlowMap semantic regression banks

This directory contains **developer-only verification assets**. It is
not part of the installed wheel or sdist, and the source examples are
**parsed, not imported or executed**.

| Corpus | Coverage | Runner | What it proves |
| --- | --- | --- | --- |
| Cross-domain baseline | 15 programs | `benchmark/runners/run.py` | Structural checks and selected Python semantic oracles |
| Control-flow regression | 8 programs | `benchmark/control-flow/` (same canonical runner) | Known semantic edge cases; no longer a blind holdout |
| Independent-bank V1 | 28 cases / 33 Python modules | `benchmark/independent-v1/run.py` | Generates inspectable outputs and preserves source hashes |
| Independent-bank V2 | 30 cases / 38 Python modules | `benchmark/independent-v2/run.py` | Generates inspectable outputs and preserves source hashes |

V1 and V2 originally served as unseen input but are now **known regression
banks**. Their `GENERATED` result **does not imply semantic PASS**; evaluate
the control flow separately before making a correctness claim.

## Run from the repository root

Install the development extras and Graphviz first (see
[development setup](../docs/development.md)).

```bash
python -m pytest -q
python -m ruff check src tests scripts

python -m benchmark.runners.run --output pyflowmap-output/baseline --render
python -m benchmark.runners.run --cases-file benchmark/control-flow/cases.json --fixtures-root benchmark/control-flow/fixtures --output pyflowmap-output/control-flow --render
python -m benchmark.runners.metamorphic --output pyflowmap-output/metamorphic
python benchmark/independent-v1/run.py --project-root . --output pyflowmap-output/bank-v1
python benchmark/independent-v2/run.py --project-root . --output pyflowmap-output/bank-v2
```

Add `--python /path/to/python` to either independent-bank runner if the
interpreter running the runner differs from the installed PyFlowMap
interpreter. On PowerShell use the virtual environment's
`.\.venv\Scripts\python.exe` instead of `python` where appropriate.
Use `--list` or `--validate-only` to check the retained bank before
running it. Source hashes are recorded in each bank's
`source-hashes.json`.

The baseline runner also supports `--only`, `--language en|es` and `--strict`. Strict mode
can return a nonzero status for **REVIEW**: that is a stricter policy
choice, not necessarily a semantic defect.

## Evaluation status

- `GENERATED`: JSON/Mermaid/images were written.
- `PASS`: specified structural and semantic obligations passed.
- `REVIEW`: uncertainty or a manual review is needed.
- `FAIL`: a reproducible obligation was violated.
- `NOT_EVALUATED`: no semantic judgment was made.
- `UNSUPPORTED`: construction beyond the declared contract.

The canonical evaluator is `benchmark/evaluation/oracles_current.py`, currently
delegating to `oracles_phase5_2.py`. The `oracles_phase*` modules
are **actively used** as components of the composed evaluator and in
mutation tests. Keep them until equivalence with a consolidated
replacement is demonstrated. Their names do not indicate that the
production analyzer exposes old versions.

Fixtures under `benchmark/regressions/` provide mutation/regression
counterexamples. They are intentionally retained without past-result
reports or duplicate launchers.

## Isolation and output policy

- Do not alter fixture source or semantic criteria just to obtain PASS.
- Do not hardcode fixture IDs, specific project names, or test domains
  into `src/pyflowmap/`.
- Do not automatically activate `--semantic-provider codex` or transmit
  private source code.
- Generated outputs go to ignored `pyflowmap-output/`; do not commit ZIPs,
  PNGs, SVGs, JSON results, or local validation manifests.
- Development scripts and banks are never requirements for using the
  installed PyFlowMap package.

See [test and release policy](../docs/reference-testing.md).

## Folder map

| Directory | Responsibility |
| --- | --- |
| `evaluation/` | Canonical semantic oracles and their dependencies; [details](evaluation/README.md) |
| `runners/` | CLI benchmark/metamorphic evaluation runners; [details](runners/README.md) |
| `tests/` | Tests of evaluators, mutated graphs and regression conditions; [details](tests/README.md) |
| `fixtures/` | 15 cross-domain Python programs; [details](fixtures/README.md) |
| `control-flow/` | 8 existing Python control-flow regression programs; [details](control-flow/README.md) |
| `regressions/` | Oracle negative/positive mutation fixtures; [details](regressions/README.md) |
| `independent-v1/` | 28-case bank with original source hashes and own runner |
| `independent-v2/` | 30-case bank with original source hashes and own runner |

The top level is intentionally limited to the source manifest, this guide,
and the `__init__.py` for running developer tools with `python -m`.
