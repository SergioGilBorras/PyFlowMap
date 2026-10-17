# Historical distribution audit (2026-10-15)

**Archived audit record — not a description of the current release state.** This report was written before PyFlowMap became public, before the independent `gh-pages` website was published, and before synthetic fixture paths were renamed. Its original observations are preserved below for historical evidence. The source repository is now public, and the historical Git-object exposure described here remains a separate remediation task.

---

# Remote distribution audit — preliminary and private

**Candidate source commit:** `5aeb441aaf01ebb9ee036bfdc7178816eab2c742` (post-PR #14). **Decision: BLOCKED; NOT approved for export or publication.**

This is a **limited, non-destructive remote review** of selected current-tree files and repository-indexed search results. It is not the full SHA256 Git-tree inventory produced by `scripts/inventory_public_snapshot.py`, a complete path review, an all-ref audit, or a secrets certification. An empty GitHub code-search result is not proof that files or history are clean. Keep this audit inside the private repository.

| Group | Preliminary decision | Evidence and remaining work |
| --- | --- | --- |
| `src/` | REVIEW | Runtime code not exhaustively reviewed for rights, external communications, or security. |
| `tests/fixtures/references/` | REVIEW | Manifest schema 2 records 10 current synthetic samples with pinned Git blob IDs; tests maintain the regression contract. Original private blobs remain in ancestors. Review all references and redistribution permissions. |
| `tests/`, `benchmark/` | REVIEW | Existing regression suite passed CI before integration. Inspect every source bank, oracle, license and generated reference for provenance. |
| `site/`, `docs/`, `README.md` | REVIEW | Existing static site is not deployed. Review all diagrams, graphics, assets, external links, and private names before distribution. |
| `output_validacion/`, `output_graphs/` | EXCLUDE generated data | `.gitignore` excludes generated contents but tracks documentation. Outputs may include private source, logs or provider responses; verify tracked tree rather than relying on ignore rules. |
| `.github/` | REVIEW | Pages workflow is manual-only and bundles `site/`; review permissions and every workflow prior to public export. |
| `scripts/`, `pyproject.toml`, packaging | REVIEW | Build docs describe a restricted wheel/sdist allowlist, but public-source export is broader. Required `portable-tempdirs` is a Git URL; labeler extras point to a private Git repo. PyPI is blocked pending validated dependency solution. |
| Git refs/history, Actions logs, artifacts, PR discussions | BLOCKED | Full all-ref/blob/secret/license/CI-artifact review not performed. Original private fixture blobs in history prohibit publishing this existing Git repository. |

## Search scope and limitations

Limited current-default-branch GitHub code-search queries were made for `BEGIN PRIVATE KEY`, `ghp_` and `api_key`; no matching indexed result was returned. This is **not** evidence that there are no secrets. A `P4-Planning-Agent` query found historic-name references/legacy fixture paths. The synthetic fixture manifest explicitly warns that old private blobs remain reachable in history. Individual binary or unindexed content, ignored files, credentials under other names and all prior Git objects remain outside this search's coverage.

## Required next actions (all private)

1. Generate a candidate commit inventory (read-only), recording every tracked path/mode/size/SHA256. Keep the report **outside Git**; do not paste private filenames/hashes into public materials. Mark each path approved, excluded or needs review.
2. Independently inspect all tracked sources/benchmarks/images/website assets and license/provenance metadata, plus nested repositories, symlinks and large binaries.
3. Run a complete **all-ref** and historical content scan in an authorized isolated environment, including Actions logs and downloadable artifacts. Preserve all backups and evidence.
4. Validate a proposed allowlisted snapshot as a fresh root commit in a separate **private** repository only after approval. Run cross-platform CI, offline validation and build/install tests.
5. Obtain explicit owner approval separately for visibility, Pages, GitHub Release and PyPI. Never infer approval from merging this report.

The preliminary distribution decisions above are **not final file-by-file approvals**. No new repo, history rewrite, tag, release or publication is authorized.
