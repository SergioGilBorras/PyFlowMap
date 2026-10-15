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
