# Contributing to PyFlowMap

Thank you for helping improve PyFlowMap. Bug reports, documentation fixes,
regression cases, and focused code contributions are welcome.

## Before you start

- Search existing [issues](https://github.com/SergioGilBorras/PyFlowMap/issues)
  and pull requests before opening a duplicate.
- For substantial changes, open an issue to discuss the design and scope first.
- Keep each pull request focused and describe user-visible behavior changes.
- Do not include private repositories, credentials, real customer code, or
  proprietary project history in issues, examples, fixtures, or commits.

## Development setup

PyFlowMap requires Python 3.11 or newer, Git access for pinned dependencies,
and optionally Graphviz for SVG/PNG rendering. Use a fresh virtual environment.

```bash
python -m venv .venv
# Activate the environment for your shell, then run:
python -m pip install -e '.[dev,mcp]'
python -m pip check
```

For PowerShell-specific instructions, see
[Windows local setup](docs/windows-local-setup.md).

## Run the checks

Before submitting a pull request, run:

```bash
python -m pytest -q
python -m ruff check src tests scripts
```

For diagram, parser, or renderer changes, add targeted regression tests using
small, independently written synthetic Python examples. Validate the relevant
diagram output and source evidence, not just whether a command exits successfully.

If Graphviz is installed, check `dot -V` before testing SVG/PNG output.
For a full offline validation pass (which can take longer):

```bash
python scripts/run_full_validation.py --output-parent ./output_validation
```

See [development guidance](docs/development.md) and
[static analysis rules](docs/analysis-rules.md) for project-specific details.

## What makes a good contribution

- Preserve PyFlowMap's static, non-executing analysis of target projects.
- Keep diagram claims conservative: unresolved runtime behavior must not be
  presented as a guaranteed execution path.
- Keep optional semantic labeling separate from deterministic graph topology.
  Never enable Codex or transmit source code to an external model by default.
- Document CLI changes and add or update tests and examples when appropriate.
- Do not commit generated environments, caches, local `dist/` artifacts,
  private validation results, or other secrets.

## Pull requests

1. Create a branch from the current `main`.
2. Commit a small, reviewable change with a clear description.
3. Explain the motivation, affected behavior, and how you tested it.
4. Link related issues and mention any limitations or trade-offs.
5. Wait for required CI checks and review before merging.

Windows and Linux/macOS checks run in GitHub Actions. Local success does not
replace cross-platform validation.

## Releases and security

The release script builds a local wheel and source distribution under `dist/`.
Contributions must **not** publish packages to PyPI or other registries.

**Do not open a public issue containing a vulnerability, exposed token, or
private source code.** Use GitHub's private vulnerability reporting feature
when enabled, or contact the maintainer privately via the repository's
GitHub profile instead. Do not attach private Git backups or bundles to
public issues.

## License and attribution

By contributing, you agree that your contribution is distributed under
the repository's [MIT License](LICENSE). Project attribution is recorded in
[AUTHORS.md](AUTHORS.md).
