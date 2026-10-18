# Synthetic reference fixtures and disclosure status

The ten Python files under `synthetic-activity-regression-v1/` are independently authored offline synthetic source-analysis examples. See `manifest.json`.

The fixtures are data for PyFlowMap's static analyzer: do **not** import or execute them as part of visual validation. They deliberately preserve tested shape, not real application logic: local calls, one decision on `NEEDS_CLARIFICATION`, affirmative/negative edges, returns, provenance symbols and the entrypoint call at line 12.

These fixtures are independently authored synthetic inputs used only for static-analysis regression tests.