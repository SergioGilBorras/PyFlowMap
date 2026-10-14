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

## Fresh complete-validation output (always in TEMP)

The developer utility `scripts/run_full_validation.py` creates a **unique
new** output directory in `%TEMP%\pyflowmap-output\full-*` on Windows
(or the system temp directory on POSIX):

```text
full-<unique>/
  validation-summary.json          # Git SHA, commands, statuses, output locations
  semantic-review-queue.md         # items that cannot be claimed as semantic PASS
  logs/
    *.log                          # stdout/stderr per step; optional mock example
  work/                            # runtime/pytest/bytecode/pip/ruff temporary caches
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
