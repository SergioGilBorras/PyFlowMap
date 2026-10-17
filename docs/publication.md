# Local distribution and repository safety

PyFlowMap is a Python source-code analyzer that produces static activity, UML class and UML package diagrams with source references. The repository contains the application, tests and developer utilities; the installed package includes the runtime and its declared dependencies.

## Current distribution status

The development repository is **private**. The existing three-diagram reference gallery is retained in `benchmark/gallery-reference/`. A consumer-facing website has not been deployed. The eventual Pages website must live in a separate orphan `gh-pages` branch containing only approved public assets. The project's own Python packages are built and kept locally in each project's `dist/`; they are **not published to PyPI**. No public hosting or GitHub release is authorized by this document.

The application supports Python 3.11+. Its essential dependency is `portable-tempdirs`, currently pinned in `pyproject.toml` to the reviewed Git commit. The optional semantic labeler is installed separately. Check actual package metadata and available wheels before changing version pins: the project's local wheels are separate artifacts and must be checked for compatible metadata and dependency versions.

Run `python scripts/build_release.py` in an approved development environment to generate and verify wheel and sdist artifacts locally. Building does not publish them. The developer test and benchmark banks do not ship in the installed distribution.

## Security and publishing prerequisites

The current branch contains synthetic reference fixtures. **The original development repository must remain private**: some reachable historical Git objects contain material from a separate private project. A public distribution must use an independently reviewed clean snapshot without importing this repository's Git ancestry. The restricted internal audit record is in `tests/fixtures/references/HISTORY-AUDIT.md`; it is not a public-distribution document.

Review every exported file's license and provenance, the clean source history, secrets, CI artifacts, website assets, dependency availability and installed-package contents. Preserve the restricted development repository and backups.

## Publication approval

Visibility changes, GitHub Pages deployment, Git tags/releases and PyPI uploads require **separate explicit owner approval**. Do not deploy from the private development tree. A separate, explicitly approved and clean `gh-pages` branch is required. Git references in the current metadata require access to their GitHub repositories for normal dependency resolution; local offline distribution requires an explicitly prepared compatible wheelhouse.

Future distribution improvements are in the [roadmap](roadmap.md).
