# Regression bank V1

**28 cases across 33 Python source modules.** The original source bank is
kept in this repository with `cases.json`, `source-hashes.json`, fixtures,
and its independent runner.

Run from the PyFlowMap repository root:

```bash
python benchmark/independent-v1/run.py --list
python benchmark/independent-v1/run.py --validate-only
python benchmark/independent-v1/run.py --project-root . --output pyflowmap-output/bank-v1
```

Install PyFlowMap in the Python environment used by the runner first.
If it runs in another environment, pass `--python` with the absolute
path of the Python interpreter containing PyFlowMap.

The runner only parses fixtures and invokes PyFlowMap against them;
it does not import or execute these programs. It writes diagrams and
records `GENERATED` or generation errors, **not an automatic semantic PASS**.
The paths and parameters are controlled by `cases.json`.

This is a **known regression bank**. Do
not change input fixtures to hide analyzer defects. New outputs belong
in the ignored `pyflowmap-output/` directory, not in the source bank.

See the [benchmark overview](../README.md).
