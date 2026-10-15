# Clean public snapshot plan (not a publication authorization)

**Status:** preparation only. The existing `SergioGilBorras/PyFlowMap` repository must stay **private**, preserving all its original refs and the `backup/pre-main-20261015` branch. No public repository, Git tag, Pages deployment, or package upload is created by these instructions.

## Why an ordinary visibility change is unsafe

Historic commits still contain ten verbatim source snapshots from a separate private repository. The current default branch contains independent synthetic replacements, but earlier Git objects remain reachable. Renaming or deleting paths in the latest commit does not solve that problem.

## Recommended publication architecture

Keep this development repository private as the restricted archive. Make a **separate, initially private** repository for a **single clean-source snapshot** once content review is complete, and only then seek explicit approval to switch the new repository public.

**Do not** use GitHub's fork, template-from-history, mirror, push --all, push --mirror, a normal checkout with existing `.git`, or history transplant for the clean repository. All of these may carry unwanted ancestry or refs. A new unrelated root commit is required. Preserve attribution/license notices and identify a release provenance record that maps the reviewed snapshot to its private source commit without copying private history.

## Preflight gates

1. Choose and record the exact reviewed `main` commit SHA; require successful Windows/Linux/macOS CI and the full offline validation report for that candidate.
2. Check all exported files and paths, including hidden files, workflow YAML, docs, site assets, test fixtures, benchmark data, build metadata and packaging inclusion/exclusion. Review copyrights and redistribution rights.
3. Run secret and sensitive-data scans against **both** the full private history and the clean snapshot; separately review GitHub Actions logs, artifacts and PR text. Keep logs and findings private.
4. Confirm the synthetic fixture hashes and source-linked regression results. Preserve AST-only semantics, 81 activity cases and the 21 focused family cases.
5. Assess the direct Git dependency on `portable-tempdirs`, and the optional private `P4-Semantic-Labeler` extras. PyPI upload is separately blocked; do not remove security-relevant tempdir behavior to bypass metadata restrictions.
6. Confirm the exact allowed public assets and the target repository name, license, branch-protection settings, GitHub Pages plan and release policy with the owner.

## Controlled snapshot creation (separate approved action)

- Export the *approved tracked source tree only* from the selected commit, outside the existing Git working tree and without copying its `.git` directory.
- Reject unexpected files by an allowlist; validate there are no symlinks, nested repositories or unwanted large/binary assets. Run a fresh sensitive-file scan.
- Initialize an unrelated Git repository with a single initial commit of reviewed files. Verify `git rev-list --all --count` reflects only intended new commits and inspect `git ls-tree -r HEAD`.
- Create the new remote as **private first**; push only the clean root branch. Do not push tags, private backups or old feature branches. Check that no original private blob IDs are present or reachable.
- Re-run CI, isolated wheel/sdist installation, offline validations and a visual check of website diagrams on the new remote. Confirm docs contain no links implying the old private repository is public.
- Obtain **separate explicit approval** before changing visibility, deploying Pages, creating a GitHub Release, or publishing to PyPI. Audit the final remote after every transition.

## Rollback and preservation

Do not delete or rewrite `SergioGilBorras/PyFlowMap`, its historical branches, CI artifacts or `backup/pre-main-20261015` as part of snapshot preparation. Keep a verified restricted restore path. If verification fails, keep the clean target private and stop publication; do not attempt to hide issues by deleting evidence.
