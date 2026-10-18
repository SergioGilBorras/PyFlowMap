# Developer validation output

This directory is NOT an application graph destination. The one-command
validator `python scripts/validate_all.py --acknowledge-source-transmission`
generates a dated `validation-YYYY-MM-DD_HH-MM-SS_<id>/` with complete
regression evidence, both deterministic and **real Codex** runs:

```text
output_validacion/
  README.md                            # only tracked file
  validation-YYYY-MM-DD_HH-MM-SS_<id>/
    validation-summary.json           # provenance, exact commit, step statuses
    semantic-review-queue.md          # unresolved semantic obligations
    logs/                             # stdout/stderr per verification step
    benchmark/
      disabled/
        baseline/                     # 15 cases: diagrams, oracle reports, gallery
        control-flow/                 # 8 cases: diagrams, oracle reports, gallery
        independent-v1/              # 28 cases: generation, hash reports, gallery
        independent-v2/              # 30 cases: generation, hash reports, gallery
        metamorphic/                  # transformation and graph invariants
      codex/
        real-labeler-report.json      # 81 real-model cases and provider evidence
        label-quality-review.csv      # per-node generated text awaiting review
        disabled/                     # same case set, baseline diagram comparison
        codex/                        # same 81 cases with real labels
    packaging/
      pyflowmap-1.0.0-py3-none-any.whl
      pyflowmap-1.0.0.tar.gz
      release-build-report.json
```

The exact labels, filenames and nested subdiagram sets depend on each entry.
Every diagram includes JSON and Mermaid; SVG/PNG are requested for the global
validation. This is a test/report directory, not a pip distribution payload.

The runner creates its caches and scratch work only below OS TEMP. Results
are ignored by Git; **only this README is tracked**. A validated, successful
new run **preserves every historical run by default**, including earlier
failed diagnostics. The optional `--prune-managed-history` flag explicitly
authorizes pruning only earlier recognized, generated runs after full PASS;
it should not be used when retaining evidence. Unknown directories, symlinks,
Windows reparse points and protected ACL paths are never deleted.

**Semantic quality:** actual Codex responses are verified for provenance and
unchanged graph structure. Their meaning requires manual review. V1/V2
generation is not an independent semantic PASS; unresolved cases remain
NOT_EVALUATED or REVIEW. The global command will not pretend otherwise.
