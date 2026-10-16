# Synthetic reference fixtures and disclosure status

The ten Python files in `p4-planning-agent-v1/` were **replaced in the current branch** with independently authored, offline synthetic examples. The directory name is a fixture identifier, not an indication of source origin. See `manifest.json`.

The fixtures are data for PyFlowMap's static analyzer: do **not** import or execute them as part of visual validation. They deliberately preserve tested shape, not real application logic: local calls, one decision on `NEEDS_CLARIFICATION`, affirmative/negative edges, returns, provenance symbols and the entrypoint call at line 12.

**Publication remains blocked:** earlier commits in `main`, old feature branches and `backup/pre-main-20261015` may expose the original private Git blobs. Updating the tip does not eliminate reachable history or Actions logs/artifacts. Conduct a complete credentials/redistribution audit and a separately approved history remediation plan before changing repository visibility. Never delete the backup automatically.
