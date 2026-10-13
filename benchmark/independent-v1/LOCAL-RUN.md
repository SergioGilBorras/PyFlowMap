# Independent V1 bank — local use

This is the preserved source bank: 28 cases across 33 Python modules. Fixture
files are parsed as source and are never imported or executed by the runner.

From the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe benchmark\independent-v1\run.py --list
& .\.venv\Scripts\python.exe benchmark\independent-v1\run.py --validate-only
& .\.venv\Scripts\python.exe benchmark\independent-v1\run.py `
  --python (Resolve-Path .\.venv\Scripts\python.exe).Path `
  --project-root (Get-Location).Path `
  --output pyflowmap-output\independent-v1
```

The runner uses the original `cases.json`, fixture tree and default analysis
parameters. Its `GENERATED` status is not a semantic pass. `source-hashes.json`
records the fixture SHA-256 values.
