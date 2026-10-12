# Windows local setup — PowerShell, PyCharm, PyFlowMap and P4

This guide covers a local development setup using the PyFlowMap CLI and MCP
interfaces. The examples use these paths; adapt them to your workstation:

- **PyFlowMap:** `F:\ProyectosPYCHARM\PythonProject\PyFlowMap`
- **Read-only analysis source:** `F:\ProyectosPYCHARM\PythonProject\P4-Planning-Agent`

## Working from a ZIP or copied folder (no `.git`)

If running `Setup-PyFlowMap-Local.ps1` reports `fatal: not a git repository`
for the PyFlowMap directory, it means this is not a Git checkout. Check:

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap'
Test-Path -LiteralPath '.\.git'
git status
```

The **revised standalone setup script (V2)** accepts the local PyFlowMap source
without Git when `pyproject.toml` and `src\pyflowmap\cli.py` are present. It
does not attempt to change branches when `.git` is missing, and warns that the
code version cannot be verified or updated. Execute without
`-CheckoutFeatureBranch`:

```powershell
.\Setup-PyFlowMap-Local.ps1 -Action All
```

Replace your original unsigned script with the revised, inspected copy first
(and unblock that new file if Windows marks it as downloaded).

For **updatable, commit-pinned development**, clone PyFlowMap into a **new
sibling directory** without overwriting or resetting your existing work:

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject'
git clone --single-branch --branch feat/initial-static-flow-mvp `
  https://github.com/SergioGilBorras/PyFlowMap.git PyFlowMap-git

& '.\PyFlowMap\Setup-PyFlowMap-Local.ps1' `
  -PyFlowMapRoot 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git' `
  -Action All
```

This repository is private and requires working Git credentials. Do not
`git init`, `git reset --hard` or delete the original directory to repair
this error.

If **P4-Planning-Agent has no `.git` either**, the revised script can
analyze its existing working tree read-only when `-P4Ref HEAD` (the default),
but saves results under `p4-working-tree-<timestamp>` and records
`commit_sha: null`. This is **not** equivalent to a frozen Git version.
To analyze `-P4Ref <SHA>`, P4 must be available as a real Git clone.

## 1. Required tools

Install Python 3.11+, Git for Windows, and, for SVG/PNG rendering, Graphviz.
Install `uv` for `uvx` (used when launching the optional Serena MCP server).

From PowerShell:

```powershell
winget install -e --id Graphviz.Graphviz
winget install -e --id astral-sh.uv
```

Open a **new PowerShell terminal** so changes to `PATH` take effect:

```powershell
git --version
py -3 --version
dot -V
uv --version
uvx --version
```

`winget` packages do not install Python, Git, Codex CLI or PyCharm for you.
The installed Mermaid CLI (`mmdc`) is optional: PyFlowMap can use Graphviz
as its `--renderer graphviz` image backend.

## 2. Running an unsigned PowerShell setup script

If a downloaded `Setup-PyFlowMap-Local.ps1` produces the error
`cannot be loaded ... not digitally signed`, first inspect and trust its
contents. PowerShell may enforce `RemoteSigned` for downloaded scripts.

A **session-only** procedure (no permanent execution-policy setting):

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap'
Get-ExecutionPolicy -List
Get-Content -LiteralPath '.\Setup-PyFlowMap-Local.ps1' -TotalCount 60
Unblock-File -LiteralPath '.\Setup-PyFlowMap-Local.ps1'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Setup-PyFlowMap-Local.ps1
```

- `Unblock-File` clears the downloaded-from-Internet flag **on this file**; it
  does not sign the script or globally change execution policy.
- `-Scope Process` affects only the open terminal session. Closing the terminal
  ends this override.
- An alternative that launches a separate PowerShell process is:

  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Setup-PyFlowMap-Local.ps1"
  ```

- If the device is governed by `MachinePolicy` or `UserPolicy` Group Policy,
  session-level changes may be ineffective; request the administrator's
  approved execution method, rather than bypassing organizational restrictions.
- Avoid `Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy Unrestricted`
  or any permanent weakening of policy just to run the setup script.

The standalone setup script was distributed separately from the GitHub
repository. It is **not** automatically created when cloning PyFlowMap.
For repeatable usage, save it outside the Git checkout (for example,
`F:\ProyectosPYCHARM\PythonProject\Setup-PyFlowMap-Local.ps1`), and invoke it
from that location. If it is placed untracked inside PyFlowMap, its own
clean-working-tree guard may prevent `-CheckoutFeatureBranch`; inspect
`git status --short` and move that standalone file outside the checkout.
Never discard other local changes to satisfy a setup step.

## 3. Prepare PyFlowMap

The current activity diagram and semantic labeler integration are on the
`feat/initial-static-flow-mvp` branch in PR #1, pending merge.

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap'
git status --short
git branch --show-current
```

Do not overwrite uncommitted work. If a fresh checkout is required, select
the feature branch only after confirming a clean working tree.

To install dependencies manually without a setup script:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e '.[dev,mcp,labeler]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

The `labeler` extra installs the private P4-Semantic-Labeler `v0.1.0` from
GitHub and requires Git credentials with repository access. If you only need
deterministic activity diagrams, use `'.[dev,mcp]'` instead. To opt in to
real Codex generation later, use `'.[dev,mcp,labeler-codex]'` and authenticate
with `codex login`. Merely installing the dependency does **not** trigger inference.

## 4. Generate activity diagrams from P4

**Do not edit or execute P4-Planning-Agent.** The PyFlowMap AST analysis does
not import the analyzed project. Keep generated files within PyFlowMap.

```powershell
$pyflowmap = 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap'
$p4 = 'F:\ProyectosPYCHARM\PythonProject\P4-Planning-Agent'
$python = Join-Path $pyflowmap '.venv\Scripts\python.exe'
$output = Join-Path $pyflowmap 'pyflowmap-output\p4-local'

& $python -m pyflowmap inspect $p4

& $python -m pyflowmap analyze $p4 `
  --entry planning.coordinator:PlanningCoordinator.plan `
  --diagram-type activity --language es `
  --renderer graphviz --format images `
  --output $output

& $python -m pyflowmap analyze $p4 `
  --entry planning_entrypoint:main `
  --diagram-type activity --language es `
  --renderer graphviz --format images `
  --output $output
```

The result directory contains editable Mermaid `.mmd`, traceable `.json`,
and Graphviz-rendered `.svg` and `.png`. `--format images` exports both
image formats. This directly analyzes the **current working tree** of P4.
To compare **exact commit versions**, use `git archive` to a ZIP snapshot
and pass that ZIP to `pyflowmap analyze`, rather than resetting/changing P4.
The separately distributed setup script supports `-P4Ref <SHA>` to automate
this. The original reference commit is
`8e68c720bef75e24acd6b3ed8a237b41fa3a838d`.

To test the labeler integration **without any AI inference**, install the
`labeler` extra and add `--semantic-provider mock`. Mock output is synthetic
and is *not* a semantic-quality evaluation. Real Codex inference is
**explicit opt-in** via `--semantic-provider codex` once configured.

## 5. PyCharm, Serena, and MCP

In PyCharm, open the PyFlowMap folder and select
`PyFlowMap\.venv\Scripts\python.exe` as the project interpreter.
Enable/configure the PyCharm MCP server from the IDE's MCP settings;
the actual menus vary by PyCharm version. Configure Serena separately through
`uvx` and its current upstream instructions.

PyFlowMap itself offers an MCP stdio server:

```powershell
$env:PYFLOWMAP_ALLOWED_ROOTS = 'F:\ProyectosPYCHARM\PythonProject'
& 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap\.venv\Scripts\pyflowmap-mcp.exe'
```

Allowlisted roots cover both source and output workspaces. Restrict them further
if you move outputs; MCP must not write into P4. Avoid using unrestricted
filesystem tools or bypassing the repository's read-only requirement in Codex.

## Official PowerShell references

- [Execution policies](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_execution_policies)
- [Unblock-File](https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/unblock-file)
