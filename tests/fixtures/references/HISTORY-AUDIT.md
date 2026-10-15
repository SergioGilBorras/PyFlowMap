# Private source disclosure: audit status

**Status: BLOCKED for public visibility.** This audit is deliberately non-destructive. It is not a certification that the repository contains no secrets.

## Verified on 2026-10-15

- The previous `main` commit `8ae451525a3991d736f9ab856c2965123a11d770` contains ten Git blobs copied from a separate private planning repository, identified by the previous manifest. Replacing their contents at the current branch tip does not remove those blobs from previous commits.
- The synthetic replacement lives on `security/synthetic-reference-fixtures`, originally branched from `main`; the original blobs are therefore still reachable in its ancestry.
- `backup/pre-main-20261015` exists and diverges from `main` (comparison reported one commit ahead, 36 behind). **Keep this backup.**
- Other feature branches are still present on GitHub. Merely checking their latest filenames cannot certify their ancestry, and public repository access would expose reachable history.
- GitHub Actions logs and archived artifacts need separate examination for secrets and redistributable source; no complete historical log review has been carried out.
- This synthetic-fixture PR does not change repository visibility or create tags/releases.

## Required gate before public visibility

1. With authorization, enumerate **all refs** (branches, tags and other retained refs) and perform credential/personal-data/proprietary-file scanning through **all reachable commits**, including packed objects and large files.
2. Inspect historical Actions logs, artifacts, PR discussions, release assets and CI-generated outputs; apply appropriate retention and removal controls only after identifying their impact.
3. Decide on safe long-term preservation of the private backup *outside every public ref*, with confirmed restricted access and a verified restorable copy. Do not delete it as an incidental cleanup action.
4. Develop a separately approved history-rewrite / clean-public-repository migration strategy. Rewriting only `main` or committing a deletion is insufficient while other public refs expose the old objects.
5. Verify on a fresh clone that no private fixture or sensitive data is reachable, then repeat full CI and verify protected GitHub settings and repo visibility before release.

No history rewrite, ref deletion, backup transfer, visibility change or publication is authorized by this document. The old repository may need to remain private while a clean new public repository is prepared.
