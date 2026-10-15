# UML 2.5.1 class diagrams (static declarations)

The **class** diagram family is additive: the existing default `activity`
contract and `FlowGraph` remain unchanged. The parser uses Python ASTs via
`ProjectIndex`; project code is **never imported or executed**.

```powershell
pyflowmap analyze ./project --diagram-type class --format all --renderer graphviz --output ./output_graphs/classes
pyflowmap analyze ./project --diagram-type class --scope src/package --format mmd
```

Unlike an activity diagram, a class diagram describes the selected source
project and requires **no `--entry`**. You may use `--max-classes` (default
250), `--scope` and `--direction`. It exports readable Mermaid `classDiagram`,
provenance JSON, and optionally SVG/PNG. Graphviz is recommended for the UML
layout; `.mmd` can be rendered by a compatible Mermaid version.

## UML semantics (OMG UML 2.5.1)

- Classifier: each top-level `class` declared in a parsed Python module.
  The UML compartments separate name, declared attributes and operations.
  Qualifiers are preserved in JSON, while rendered class names include their
  module namespace to avoid collisions.
- Generalization: a **solid line with an unfilled triangular arrowhead
  pointing toward the superclass**. Only project-local, unambiguously
  resolved bases are drawn. Source supports multiple-inheritance edges.
  Unknown/external/metaclass/dynamic bases remain warnings, not invented nodes.
- Attributes: annotated class fields, explicit class bindings and direct
  `self.attribute` assignments in `__init__`. Types are shown **only when
  declared**, never guessed from values.
- Operations: declared methods with their AST parameter and return type
  annotations (when given). Static members are underlined in Graphviz; abstract
  members and abstract class names are italic. The Mermaid `*`/`$` markers
  encode method abstraction / static classification.
- Visibility marks `+`, `#`, `-` follow **Python naming conventions** for
  ordinary names, single underscore, double underscore; Python does not
  enforce UML access control. These are indications, not runtime guarantees.

The diagram **does not infer** UML association, aggregation, composition,
realization, multiplicity, interface, external class identity, instance
lifetime or dynamic monkey-patched members from imports or constructor calls.
Doing so would falsely assert relationships that a Python AST alone cannot
prove. Classes decorated by arbitrary metaclasses or wrappers can differ at
runtime; JSON contains file and line evidence, and warnings record omissions.

Class diagrams are deterministic: `--semantic-provider disabled` only. The
existing Codex labeler applies to activity captions, not UML declarations.

## Standard and renderer references

- [OMG UML 2.5.1 specification](https://www.omg.org/spec/UML/2.5.1/)
- [Mermaid class diagram grammar](https://mermaid.js.org/syntax/classDiagram)

Package diagrams are the next independent module, with no consumer-provided
configuration required for statically observed project-local dependencies.
Sequence, state, component and other uncertain families remain long-term
roadmap items; they are **not** implied by the class diagram command.
