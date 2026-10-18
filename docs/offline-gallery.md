# Offline gallery: activity, classes, and packages

This developer command produces three diagram families from Python source
**without Codex, another LLM, or a mock semantic provider**. Graphviz (`dot`)
is required for SVG and PNG generation. Analyzed source is never imported
or executed.

```powershell
.\.venv\Scripts\python.exe scripts\offline_diagram_gallery.py
.\.venv\Scripts\python.exe scripts\offline_diagram_gallery.py --source .\my-project --entry module:main
```

Each run creates a new directory under `output_graphs/`:

```text
<timestamp>-<identifier>/
  index.html                 # standalone local index
  README.md
  activity/                  # .mmd, .json, .svg, .png
  classes/                   # UML classes: .mmd, .json, .svg, .png
  packages/                  # UML packages: .dot, .json, .svg, .png
  common/
    manifest.json            # artifacts, warnings, provenance
    gallery.css              # shared presentation
```

The three diagram families use separate models and source-backed evidence.
PyFlowMap does not invent UML relationships: properties that cannot be
established statically are omitted. Package links indicate dependencies,
not UML `«import»` relationships. Activity diagrams retain their established
representation.

Open the generated `index.html` to inspect the three renderings and
access editable sources. The page needs no JavaScript, CDN, or network
connection. Existing output runs are not overwritten or removed.

## Package style

The default `modern` package style draws one broad vector folder with
its name inside, without an outer card or miniature icon. Display names
are title-cased without altering the underlying Python identifiers.

The traditional tabbed UML `strict` style is also available:

```bash
pyflowmap analyze ./my-project --diagram-type package --package-style strict
```

Both styles represent the same dependencies. The manifest records which
style was rendered; no duplicate output directories are created.
