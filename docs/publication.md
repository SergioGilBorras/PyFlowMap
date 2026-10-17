# Local distribution and repository safety

PyFlowMap is a Python source-code analyzer that produces static activity, UML class and UML package diagrams with source references. The repository contains the application, tests and developer utilities; the installed package includes the runtime and its declared dependencies.

## Current distribution status

The source repository is currently **public**. The three-diagram reference gallery is in `benchmark/gallery-reference/`. The consumer website is published separately from the independent-root `gh-pages` branch at https://sergiogilborras.github.io/PyFlowMap/. The project's own Python packages are built and kept locally in each project's `dist/`; they are **not published to PyPI**. The Pages website is already public; no GitHub source release is created by these instructions.

The application supports Python 3.11+. Its essential dependency is `portable-tempdirs`, currently pinned in `pyproject.toml` to the reviewed Git commit. The optional semantic labeler is installed separately. Check actual package metadata and available wheels before changing version pins: the project's local wheels are separate artifacts and must be checked for compatible metadata and dependency versions.

Run `python scripts/build_release.py` in an approved development environment to generate and verify wheel and sdist artifacts locally. Building does not publish them. The developer test and benchmark banks do not ship in the installed distribution.

## Security and publishing prerequisites

The current branch contains synthetic reference fixtures. **Security warning:** earlier commits in this currently public repository still contain material from a separate private project. The current synthetic fixtures do not remediate exposed Git history. Preserve an access-controlled backup, then carry out a dedicated history and GitHub cached-object remediation. The restricted internal audit record is in `tests/fixtures/references/HISTORY-AUDIT.md`; it is not a public-distribution document.

Review every exported file's license and provenance, the clean source history, secrets, CI artifacts, website assets, dependency availability and installed-package contents. Preserve access-controlled backups and review all historical exposures.

## Publication approval

The owner has enabled the consumer website on an unrelated-root `gh-pages` branch. Further visibility changes, Git tags/releases and package uploads require explicit approval. Do not publish benchmark reports as the consumer website. Git references in the current metadata require access to their GitHub repositories for normal dependency resolution; local offline distribution requires an explicitly prepared compatible wheelhouse.

Future distribution improvements are in the [roadmap](roadmap.md).
