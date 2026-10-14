# Generated output contract

`examples/` is **input code**. `pyflowmap-output/` is **generated output**
(JSON control-flow graphs, Mermaid sources, optionally rendered images and
developer evaluation reports). They are intentionally different:
`examples/` must remain clean and tracked; generated artifacts are
disposable and must never be committed or packaged.

This README is the **only tracked file** in `pyflowmap-output/`. Running
`pyflowmap analyze` without `--output` defaults to a subpath here *when the
working directory is the checkout*; for repeatable local validation ALWAYS
specify an output under `%TEMP%` instead.

## Exact per-diagram output (PyFlowMap 1.0.0)

For `pyflowmap analyze SOURCE --entry module:main --output DEST --format all
--renderer graphviz`, `DEST/` contains:

```text
DEST/
  <stem>.mmd         # editable Mermaid, always written
  <stem>.json        # nodes, edges, locations, warnings: always written
  <stem>.svg         # rendered image for all/images/svg
  <stem>.png         # rendered image for all/images/png
  <stem>.subdiagrams/          # only if nested diagrams exist
    index.html                 # links to nested diagrams
    <child-id>.mmd
    <child-id>.json
    <child-id>.svg             # according to selected format
    <child-id>.png             # according to selected format
```

The sanitized `<stem>` comes from the resolved entry symbol (not necessarily
the input file name). Consult the CLI's `files` map for exact paths.
Selecting `mmd` saves `.mmd` plus `.json` even when images are not requested.
A file path in `--output` is allowed only for a single-format invocation.
`inspect` prints entry candidates to stdout, not diagram files.

## Fresh complete-validation output (TEMP by default, optional repository results)

The developer utility `scripts/run_full_validation.py` creates a **unique
new** output directory in `%TEMP%\pyflowmap-output\full-*` on Windows
(or the system temp directory on POSIX):

```text
full-<unique>/
  validation-summary.json          # Git SHA, commands, statuses, output locations
  semantic-review-queue.md         # items that cannot be claimed as semantic PASS
  logs/
    *.log                          # stdout/stderr per step; optional mock example
  # No work/ here with --output-parent: scratch stays in %TEMP%
  disabled/
    baseline/
      report.json                  # per-case structural + semantic findings
      report.csv
      REPORT.md
      gallery.html
      cases/<id>/<stem>.{mmd,json,svg,png}
    control-flow/
      report.json
      report.csv
      REPORT.md
      gallery.html
      cases/<id>/<stem>.{mmd,json,svg,png}
    independent-v1/
      run-report.json              # generation, hashes, NOT_EVALUATED semantics
      run-report.csv
      REPORT.md
      gallery.html
      cases/c01/...                # diagrams, stdout.txt and stderr.txt
    independent-v2/
      run-report.json
      run-report.csv
      REPORT.md
      gallery.html
      cases/v01/...
    metamorphic/
      report.json                  # transformations and topology checks
  mock/                            # only with --with-labeler
    comparison/
      labeler-comparison.json      # disabled vs mock invariants, all 73 cases
      disabled/<id>/<stem>.{mmd,json}
      mock/<id>/<stem>.{mmd,json}
  packages/
    pyflowmap-1.0.0-py3-none-any.whl
    pyflowmap-1.0.0.tar.gz
    release-build-report.json
```

The diagrams shown in each `cases/` subdirectory use the sanitized resolved
symbol stem. Nested views may create extra `<stem>.subdiagrams/` directories.
The comparator's individual `.mmd/.json` filenames are also derived from
entries, not fixed by the case ID.

**Statuses:** `PASS` means an evaluated obligation passed; `REVIEW` means
conservative uncertainty; `FAIL` means an evidenced failure. V1/V2 currently
generate diagrams and check structural properties/source hashes, but their
semantic status is `NOT_EVALUATED`. Mock labeler output confirms integration
and topology invariance only, **not factual quality or real Codex inference**.

Existing ignored outputs in the checkout may be legacy files. The runner
does not delete them, overwrite them, or change ACL permissions: inspect them
before any targeted cleanup. Do not delete `_avast_` or protected folders
without confirming their origin.

See [example inputs](../examples/README.md),
[developer scripts](../scripts/README.md),
and [testing policy](../docs/reference-testing.md).


## What was in the previous local ZIP

The old `final-validation-1.0/` (candidate `eeb1133`) and the older
`history/final-validation-1.0-candidate-pre-exception-dispatch-20261013/`
were historical **developer validation bundles**. They are not the program
sources in `examples/` and are not reports from a production customer
application. The folders contain pytest and Ruff logs, per-fixture activity
diagrams, reports, two kinds of historical regression banks, a gallery,
and archived wheel/sdist outputs.

The diagrams named `pipeline_main_start.{json,mmd,svg,png}` describe the
*multi-module pipeline test fixture*. It is not the result of executing a
business/data pipeline. Most diagram outputs were already present under
`02-benchmarks/*/cases/`; the old `04-diagrams/` was only a navigation index.
The older 15-case labeler section is strictly `disabled/mock`, **not live
Codex**.

## Live validation organization

Run `scripts/run_full_validation.py --with-real-labeler
--acknowledge-source-transmission --output-parent .\pyflowmap-output` to
create a NEW ignored `full-<unique>/` directory under this folder:

```text
pyflowmap-output/
  README.md                           # only tracked file
  final-validation-1.0/               # pre-existing, historical, DO NOT mix
  history/                            # pre-existing, historical, DO NOT mix
  full-<unique>/
    validation-summary.json
    semantic-review-queue.md
    logs/
    disabled/
      baseline/                       # 15 evaluated cases and diagrams
      control-flow/                   # 8 evaluated cases and diagrams
      independent-v1/                 # 28 generated cases
      independent-v2/                 # 30 generated cases
      metamorphic/                    # independent transformation checks
    real-labeler/
      real-labeler-report.json
      label-quality-review.csv        # manual truthfulness/semantic review
      disabled/                       # baseline for 82 sources
      codex/                          # REAL Codex diagrams for 82 sources
    packages/                         # local release outputs
```

Each generated diagram set contains editable Mermaid (`.mmd`), graph JSON
(`.json`), SVG and PNG. Existing historical folders are left untouched;
all temporary execution directories/cache files are created in `%TEMP%`.
The real provider transmits bounded source excerpts and may incur usage
charges. This does not replace semantic oracles or human review.
