# UML 2.5.1 package diagrams (source-declared boundaries)

Package diagrams use a **separate** static AST model and Graphviz renderer.
They do not modify class diagrams, `FlowGraph`, or the 81-case activity corpus.

```powershell
pyflowmap analyze ./project --diagram-type package --format all --renderer graphviz --output ./output_graphs/packages
pyflowmap analyze ./project --diagram-type package --format dot --scope src/mypackage
```

No `--entry`, consumer metadata or Codex inference is necessary. Project-local
package boundaries are extracted from directories containing `__init__.py`;
PEP 420 namespace directories without a marker are intentionally not modeled
because the effective import environment cannot be validated from the AST.
A project with no declared packages fails rather than drawing fictitious ones.

## Faithful notation and limits

- Each **UML Package** is drawn as a tabbed-folder symbol (Graphviz `folder`).
  Qualified names such as `myapp::feature` retain nesting without claiming
  a special ownership relation. The JSON additionally provides `parent`,
  declared modules and source location.
- A source import resolved to another **project-local package** may be drawn
  as a UML **Dependency**: dashed line, open-chevron arrow toward the supplier
  package. Exact importing file/line evidence is recorded in JSON. The
  dependency reflects the *syntactic* import and not confirmed execution.
- Python `import` or `from ... import` is **not** automatically mapped to
  UML `PackageImport`, `ElementImport`, `PackageMerge`, or `«use»` stereotypes:
  those UML relationships have stronger metamodel semantics.
- Unresolved, dynamic and external imports are not invented as project-local
  package nodes. Dependencies that target the same containing package are
  omitted. A scoped view does not create out-of-scope phantom packages.

**Rendering choice:** package diagrams produce editable Graphviz `.dot`,
provenance `.json`, and optional SVG and PNG. They intentionally **do not**
produce Mermaid flowcharts: Mermaid currently has no UML package diagram
family with compliant tabbed packages and dependency notation. The global
`--format mmd` default does not apply; pass `--format all` or `--format dot`.
`--max-packages` (default 250) bounds output size without silently dropping
packages. Python source is never imported or executed.

References: [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/),
[Graphviz UML notation example](https://graphviz.org/Gallery/directed/UML_Class_diagram.html).

## Next stage

Build a **GitHub Pages** project site to publish installation instructions,
rendered UML class/package examples, activity examples, semantic limits,
testing evidence and an explicit development roadmap. Complex consumer-context
UML families remain distant roadmap only, not planned implementation work.


## Vector presentation of package outlines

Package symbols use a wider left tab adjoining the rectangular UML package
body; their name remains in the body because members are not displayed.
Dependency lines stay dashed, with an open arrow pointing to the supplier.
The offline gallery uses left-to-right layout for these compact examples.
SVG and PNG remain derived from the same DOT source with no external assets.


## Modern and strict package presentation

Use `--package-style modern` (the default) for one **large, elongated
vector folder silhouette**, with the full package name centered **inside**
its body. There is no outer card or separate miniature icon. Graphviz's
native folder path produces self-contained SVG and matching PNG, without
raster images, extra asset files, remote requests or emoji fonts.

Use `--package-style strict` for the traditional UML 2.5.1
upper-left-tab package symbol. Its original DOT silhouette is retained.

```powershell
pyflowmap analyze ./project --diagram-type package --format all --renderer graphviz --package-style modern
pyflowmap analyze ./project --diagram-type package --format all --renderer graphviz --package-style strict
```

Only the package-node presentation changes. Import-derived UML dependencies
and their source provenance are identical between modes, and both preserve
the same open-arrow dashed edges. The exported JSON and CLI result record
`package_style`; the offline gallery generates `modern` by default.

**Standards distinction:** `strict` follows the traditional UML package
shape; `modern` is a clearly identified visual alternative and does not
claim strict compliance of its pictogram with OMG glyph notation.

## Caption capitalization

The first letter of each displayed package namespace segment is capitalized:
`reports` → `Reports`; `myapp.feature` → `Myapp::Feature`.
This is **display only**, in both styles. Python module names, source
locations, JSON package identifiers, dependency endpoints and tooltips retain
their original case and are not modified.
