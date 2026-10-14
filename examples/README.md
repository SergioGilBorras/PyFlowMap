# Example inputs (not generated results)

This directory holds **small Python source programs to analyze or demonstrate
an optional integration**. PyFlowMap reads input source through `ast` rather
than executing it. The files here are examples, not test or benchmark
oracles, and they must not receive generated diagrams or temporary files.

| File | What it demonstrates | What it produces |
| --- | --- | --- |
| `basic_pipeline.py` | A small flow: load → normalize → conditionally train and save | When analyzed with `--entry basic_pipeline:main`, PyFlowMap writes Mermaid, JSON and requested SVG/PNG to the *output directory*; analyzing does not run any Python function |
| `semantic_labeler_integration.py` | The optional `SemanticLabelerTools` Python adapter using the **mock** provider | When executed explicitly with the optional `.[labeler]` extra installed, it prints synthetic label and summary objects on stdout; it does **not** save diagrams or invoke Codex |

## Generate example diagrams without polluting the repository

From the project root in PowerShell:

```powershell
$dest = Join-Path $env:TEMP 'pyflowmap-output\examples\basic-pipeline'
.\.venv\Scripts\python.exe -m pyflowmap.cli analyze .\examples\basic_pipeline.py --entry basic_pipeline:main --format all --renderer graphviz --semantic-provider disabled --output $dest
```

This produces `basic_pipeline_main.mmd`, `basic_pipeline_main.json`,
`basic_pipeline_main.svg` and `basic_pipeline_main.png` (actual stem is
derived from the resolved entry ID; refer to the CLI `files` object for
authoritative names). For hierarchy or subprocess views, extra
`<stem>.subdiagrams/` files may appear.

To exercise only the optional mock labeler adapter (not a diagram run):

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler]'
.\.venv\Scripts\python.exe .\examples\semantic_labeler_integration.py
```

Do not execute this demo as a proxy for semantic-flow testing. Use the
[full validation guide](../docs/reference-testing.md) for oracles and
[output layout](../pyflowmap-output/README.md) for all report formats.
