# Future directions

This document lists **optional future work**, without promised release dates.
Current supported features and limits are documented in the
[README](../README.md) and
[analysis rules](analysis-rules.md).

## Release engineering and quality

- Keep the wheel/sdist reproducible and free of benchmark, test, gallery,
  local-workspace and temporary files.
- Validate the installed command-line launcher, Python-module CLI, MCP and
  rendering on Windows, Ubuntu and macOS.
- Retain independent test banks, semantic oracles, adversarial regressions
  and mutation/metamorphic checks for future releases.
- Ensure GitHub Actions tests exactly the released commit, not a different
  local working tree.
- Evaluate optional real-provider labeling only with authorized synthetic or
  explicitly approved source and a separate quality rubric.

## Analysis and presentation improvements

Pursue only general Python-language counterexamples or broadly useful
presentation improvements:

- Improve navigation and readability of complex exception/context-manager
  diagrams without deleting legal routes.
- Extend conservative call resolution where sound static evidence exists.
- Make dynamic uncertainty, call-summary boundaries and source provenance
  easier to inspect.

Do **not** treat unavoidable runtime uncertainty as an open defect; the
analyzer should represent possible paths and document what it cannot know.

## Optional future capabilities

- Preserve and extend cross-platform tests for the three already-integrated
  diagram families without changing their conservative AST semantics.
- Audit all reachable history, old branches, CI logs and artifacts, licenses
  and third-party fixtures before making the repository public.
- Design a concise consumer-facing GitHub Pages site on an unrelated-root `gh-pages` branch; deploy only approved public assets, independently of the private benchmark gallery.
- Keep local wheel and source-distribution builds reproducible and verify
  compatible versions of the separately maintained local dependency wheels.
- Sequence, state, component and other context-dependent diagrams: distant roadmap only;
  no implementation commitment without evidence-based UML semantics.
- More flexible but bounded output navigation and serialization.
- Optional caching and efficiency controls for explicitly enabled labelers.

None of these ideas is a claim of present support.
See [diagram types](diagram-types.md) for the current type/view contract.

## Development policy

Each proposed feature must have a source-independent Python semantics
justification, regression tests, packaging checks, and clear documentation.
An independent evaluation bank must not be used to engineer domain-specific
special cases. Do not publish new capabilities solely because diagram files
were generated successfully.
