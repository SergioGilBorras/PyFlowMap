# Public repository, Pages and release checklist

The activity, UML class and package diagram implementations, the offline
gallery and the focused validation bank are already integrated into `main`.
Being in `main` does **not** mean the repository is public, the website is
deployed, or a GitHub/PyPI release exists.

## Before making this repository public

GitHub exposes the full reachable history and all branches, not only the
latest source tree. Review **every reachable branch**, including
`backup/pre-main-20261015` and former feature branches, for credentials,
personal data, proprietary files, generated evaluation artifacts and source
code that should remain private. GitHub Actions logs, history and artifacts
also become visible to everyone. This checklist does not certify that old
commits are free of sensitive information.

**Important redistributability blocker found in the current `main` tree:**
`tests/fixtures/references/p4-planning-agent-v1/` contains ten verbatim
Git blobs identified in `tests/fixtures/references/manifest.json` as coming
from the **private** `SergioGilBorras/P4-Planning-Agent` repository.
A simple current-tree scan did not detect familiar literal credential markers
in these ten files, but that neither grants redistribution rights nor proves
the full Git history/CI logs are clear. Before making PyFlowMap public,
obtain explicit approval to disclose these reference files or replace them
with licensed/synthetic, functionally equivalent regression fixtures and
rerun tests. Simply deleting them from the tip of `main` would **not**
erase them from earlier reachable commits or branches.

Also verify permission to redistribute benchmark fixtures and examples,
check the MIT license, and review whether any private Git dependency in the
installation instructions should be public and available to consumers.
Do not assume private third-party projects become available when PyFlowMap
is made public.

For inspection on an authorized local clone, you may list refs and tracked
paths **without modifying data**:

```powershell
git branch -a
git log --all --oneline --decorate -30
git ls-tree -r --name-only HEAD
```

After completing an independent source/history/CI-log audit, the repository
owner can choose **Settings → General → Danger Zone → Change repository
visibility → Public** in GitHub. This step is not automated by PyFlowMap.
GitHub documents that making a repository public exposes its Git history and
Actions logs, and can affect push rulesets.

## GitHub Pages: deliberate manual deployment

The self-contained website lives in `site/`. GitHub's branch-source
publishing supports the branch root or `/docs`, not `/site`.
[The Pages workflow](../.github/workflows/deploy-pages.yml) uses an artifact
containing **only `site/`** and is declared with `workflow_dispatch`
only; it is not triggered by push or pull requests.

1. Review source, all three SVGs, external links, and the target commit.
2. Set **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. When authorized, run **Actions → Deploy PyFlowMap Pages (manual) → Run
   workflow** from `main`.
4. Verify the URL shown in Pages settings, all three diagrams and HTTPS.

The intended GitHub Pages project URL, once deployed, is ordinarily
`https://sergiogilborras.github.io/PyFlowMap/`; do **not** assume it is
live until GitHub confirms the deployment.

## GitHub source release: after final approval

The Windows full validation passed on integrated commit
`8ae451525a3991d736f9ab856c2965123a11d770`, with
`semantic_provider=disabled`. Linux, macOS and Windows CI checks also passed
for this commit. **If a documentation or packaging PR is merged afterward,
validate the new candidate commit again** before tagging.

Build and verify with `python scripts/build_release.py`; review the report,
the exact commit, wheel/sdist file list and SHA256 hashes. Tag exactly the
verified release commit and attach the validated artifacts to the GitHub
release. Do not create a tag or release automatically merely because CI passed.

## PyPI is separately blocked by direct Git dependencies

`pyproject.toml` contains a mandatory `portable-tempdirs @ git+...`
dependency pinned to a commit, and optional `labeler` and `labeler-codex`
extras referring to a separate Git repository. Public PyPI upload does not
accept direct URL requirements in distribution metadata. A wheel being
installable locally via pip is **not** sufficient for PyPI.

Do not remove the temporary-directory dependency (ZIP sandbox/ACL safety)
or the optional labeler to bypass the check. Choose distributable versioned
dependencies or another independently tested arrangement and repeat security,
Windows/Linux/macOS, wheel/sdist and isolated-install verification.
Until then, source/Git installation with accessible prerequisites and a
GitHub release are separate viable milestones; `pip install pyflowmap`
from PyPI is **not yet supported**.

## Status at the time this checklist was prepared

- Three-family code and tests integrated on `main`: yes.
- Deterministic Windows full validation: PASS, without Codex.
- Repository visibility: private; **not changed by this PR**.
- Pages hosted: no; workflow is deliberately manual.
- GitHub release or tag: not created.
- PyPI publication: not performed.
