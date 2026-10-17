# Clean public snapshot plan (not a publication authorization)

**Status:** historical remediation planning. The existing `SergioGilBorras/PyFlowMap` repository is already **public**, and its independent `gh-pages` branch is deployed. `backup/pre-main-20261015` has been deleted. This document does not itself remediate the previously disclosed Git history.

## Why an ordinary visibility change is unsafe

Historic commits still contain ten verbatim source snapshots from a separate private repository. The current default branch contains independent synthetic replacements, but earlier Git objects remain reachable. Renaming or deleting paths in the latest commit does not solve that problem.

## Recommended historical remediation approach

The existing repository is already public. Before any history replacement, preserve a restricted, verified backup; prepare an independently reviewed clean-root replacement history; inspect GitHub PR refs, Actions artifacts, cached objects and forks; and coordinate removal of obsolete exposed objects with GitHub Support where required. Publishing a replacement root alone does not erase existing copies. The public `gh-pages` branch is already independent and should be preserved.

**Do not** use GitHub's fork, template-from-history, mirror, push --all, push --mirror, a normal checkout with existing `.git`, or history transplant for the clean repository. All of these may carry unwanted ancestry or refs. A new unrelated root commit is required. Preserve attribution/license notices and identify a release provenance record that maps the reviewed snapshot to its private source commit without copying private history.

## Preflight gates

1. Choose and record the exact reviewed `main` commit SHA; require successful Windows/Linux/macOS CI and the full offline validation report for that candidate.
2. Check all exported files and paths, including hidden files, workflow YAML, docs, site assets, test fixtures, benchmark data, build metadata and packaging inclusion/exclusion. Review copyrights and redistribution rights.
3. Run secret and sensitive-data scans against **both** the full private history and the clean snapshot; separately review GitHub Actions logs, artifacts and PR text. Keep logs and findings private.
4. Confirm the synthetic fixture hashes and source-linked regression results. Preserve AST-only semantics, 81 activity cases and the 21 focused family cases.
5. Assess the direct Git dependency on public `portable-tempdirs` and the optional public `P4-Semantic-Labeler` extras. PyPI upload is separately blocked; do not remove security-relevant tempdir behavior to bypass metadata restrictions.
6. Confirm the exact allowed public assets and the target repository name, license, branch-protection settings, GitHub Pages plan and release policy with the owner.

## Export manifest and provenance requirements

Before export, maintain a machine-checkable allowlist of paths and their SHA256 hashes for the selected private commit. Include a reviewer decision for **every** tracked path, not only a list of expected extensions. Do not ship the private audit report, backup bundles, logs, generated build outputs, local configuration, access tokens, or secret-scanning findings merely because they were tracked. GitHub Actions workflows need a separate permissions/trigger review before export.

Review the following groups explicitly:

| Group | Required review |
| --- | --- |
| `src/`, CLI and MCP entrypoints | Static-only behavior, paths, outbound connections and licensing |
| `tests/` including reference fixtures | Synthetic provenance, identifiers, Git blob hashes, and no historical original data |
| `benchmark/`, `output_graphs/`, `output_validacion/` | Rights to samples, archives, reports and any embedded private source |
| `benchmark/gallery-reference/`, `docs/`, `README.md` | SVG/asset rights, external links, paths, and disclosure of private upstream projects |
| `.github/`, packaging manifests and scripts | Least-privilege tokens, CI triggers, dependencies, and distribution file allowlists |

No single successful secrets scan is conclusive: also inspect large/binary files, Git LFS, submodules/symlinks, generated artifacts, author metadata and references in documentation. For the public snapshot, do not include a Git history audit log containing private filenames or original blob identifiers.

## Dependency-release blockers

Current required dependency: `portable-tempdirs` at a pinned Git commit. Verify an independently redistributable, indexed release and preserve its sandbox, ACL and temporary-directory protections before replacing the direct Git requirement. Optional `labeler` and `labeler-codex` extras reference publicly accessible Git repositories, but pip installations still depend on their pinned commit/tag and transitive requirements. They are not PyPI-distributed wheels.

Publishing a GitHub source release is distinct from PyPI. A public GitHub repository does **not** itself make this project's direct-URL distribution metadata eligible for PyPI.

## Controlled snapshot creation (separate approved action)

- Export the *approved tracked source tree only* from the selected commit, outside the existing Git working tree and without copying its `.git` directory.
- Reject unexpected files by an allowlist; validate there are no symlinks, nested repositories or unwanted large/binary assets. Run a fresh sensitive-file scan.
- Initialize an unrelated Git repository with a single initial commit of reviewed files. Verify `git rev-list --all --count` reflects only intended new commits and inspect `git ls-tree -r HEAD`.
- Create the new remote as **private first**; push only the clean root branch. Do not push tags, private backups or old feature branches. Check that no original private blob IDs are present or reachable.
- Re-run CI, isolated wheel/sdist installation, offline validations and a visual check of website diagrams on the new remote. Confirm docs contain no links implying the old private repository is public.
- Obtain **separate explicit approval** before changing visibility, deploying Pages, creating a GitHub Release, or publishing to PyPI. Audit the final remote after every transition.

## Rollback and preservation

Do not delete or rewrite `SergioGilBorras/PyFlowMap`, its historical branches, CI artifacts or `backup/pre-main-20261015` as part of snapshot preparation. Keep a verified restricted restore path. If verification fails, keep the clean target private and stop publication; do not attempt to hide issues by deleting evidence.
