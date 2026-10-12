#requires -Version 5.1
<#+
.SYNOPSIS
  Prepara PyFlowMap + P4 de forma reproducible en Windows/PowerShell.
.DESCRIPTION
  No modifica P4: usa git archive de un commit si hay Git; si no, analiza la carpeta de solo lectura.
  Permite ejecutar PyFlowMap desde archivos locales sin .git (sin cambio de rama).
  No ejecuta inferencia Codex salvo -SemanticProvider codex -AllowCodexInference.
  PyCharm MCP requiere activacion/Auto-Configure en el propio IDE.
.EXAMPLE
  .\Setup-PyFlowMap-Local.ps1 -CheckoutFeatureBranch -ConfigureSerena -ConfigurePyFlowMapMcp
.EXAMPLE
  .\Setup-PyFlowMap-Local.ps1 -Action Diagrams -P4Ref HEAD -SemanticProvider disabled
#>
[CmdletBinding()]
param(
    [ValidateSet('Setup','Test','Diagrams','All')]
    [string]$Action = 'All',
    [string]$PyFlowMapRoot = '',
    [string]$P4Root = 'F:\ProyectosPYCHARM\PythonProject\P4-Planning-Agent',
    [string]$P4Ref = 'HEAD',
    [string[]]$Entries = @('planning.coordinator:PlanningCoordinator.plan', 'planning_entrypoint:main'),
    [ValidateRange(2,100)][int]$MaxNodes = 9,
    [ValidateSet('disabled','mock','codex')][string]$SemanticProvider = 'disabled',
    [ValidateRange(1,80)][int]$SemanticMaxChars = 70,
    [ValidateSet('neutral','technical','formal','academic','concise')][string]$SemanticStyle = 'technical',
    [switch]$AllowCodexInference,
    [switch]$InstallCodexLabeler,
    [switch]$CheckoutFeatureBranch,
    [switch]$ConfigureSerena,
    [switch]$ConfigurePyFlowMapMcp,
    [switch]$LaunchCodex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$FeatureBranch = 'feat/initial-static-flow-mvp'

function Say([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Require-Tool([string]$Name) {
    $found = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $found) { throw "Falta '$Name'. Instalalo y abre una terminal nueva." }
    return $found.Source
}
function Run([string]$Exe, [string[]]$Params) {
    & $Exe @Params
    if ($LASTEXITCODE -ne 0) {
        throw "Error ($LASTEXITCODE): $Exe $($Params -join ' ')"
    }
}
function Git-Out([string[]]$Params) {
    $output = & $script:GitPath @Params
    if ($LASTEXITCODE -ne 0) { throw "Git fallo: $($Params -join ' ')" }
    return ($output | Out-String).Trim()
}
function Resolve-PythonLauncher {
    $py = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, '-3') }
    $python = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    throw 'Instala Python 3.11 o superior y habilita py.exe / python.exe en PATH.'
}
function Is-GitRepository([string]$Root) {
    # A downloaded ZIP or copied PyCharm project can contain valid source without .git.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $top = & $script:GitPath -C $Root rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $absoluteTop = [IO.Path]::GetFullPath(($top | Select-Object -Last 1).Trim()).TrimEnd('\', '/')
        $absoluteRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
        return [string]::Equals($absoluteTop, $absoluteRoot, [StringComparison]::OrdinalIgnoreCase)
    } finally {
        $ErrorActionPreference = $previous
    }
}
function Check-PyFlowMapSource {
    $projectToml = Join-Path $PyFlowMapRoot 'pyproject.toml'
    $entrypoint = Join-Path $PyFlowMapRoot 'src\pyflowmap\cli.py'
    if (-not (Test-Path -LiteralPath $projectToml -PathType Leaf) -or
        -not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
        throw "Falta el codigo fuente de PyFlowMap ($projectToml / $entrypoint). Descarga o clona el repositorio y revisa -PyFlowMapRoot."
    }
    if (Is-GitRepository $PyFlowMapRoot) {
        Check-Branch
        return
    }
    if ($CheckoutFeatureBranch) {
        throw "PyFlowMap NO es un repositorio Git: $PyFlowMapRoot. No puedo cambiar ramas. Si descargaste un ZIP, quita -CheckoutFeatureBranch o clona en otra carpeta: git clone --branch $FeatureBranch --single-branch https://github.com/SergioGilBorras/PyFlowMap.git PyFlowMap-git. Nunca sobrescribas la carpeta existente."
    }
    Write-Warning "PyFlowMap no contiene .git. Usare los archivos locales SIN actualizar rama; comprueba que incluyan la integracion reciente. Para sincronizar cambios futuros, clona el repositorio en una carpeta nueva."
}
function Check-Branch {
    $branch = Git-Out @('-C', $PyFlowMapRoot, 'branch', '--show-current')
    if ($branch -eq $FeatureBranch) {
        Write-Host "Rama PyFlowMap: $branch" -ForegroundColor Green
        if ($CheckoutFeatureBranch) {
            # Opt-in: actualizacion no destructiva a la rama remota de la PR.
            $dirty = Git-Out @('-C', $PyFlowMapRoot, 'status', '--porcelain')
            if ($dirty) { throw 'Hay cambios locales en PyFlowMap: no puedo hacer ff-only. Guarda o confirma los cambios primero.' }
            Run $script:GitPath @('-C', $PyFlowMapRoot, 'fetch', 'origin', $FeatureBranch)
            Run $script:GitPath @('-C', $PyFlowMapRoot, 'merge', '--ff-only', "origin/$FeatureBranch")
        }
        return
    }
    if (-not $CheckoutFeatureBranch) {
        throw "PyFlowMap esta en '$branch', pero la integracion esta en '$FeatureBranch'. Vuelve a ejecutar con -CheckoutFeatureBranch (solo si quieres cambiar de rama)."
    }
    $dirty = Git-Out @('-C', $PyFlowMapRoot, 'status', '--porcelain')
    if ($dirty) {
        throw 'PyFlowMap tiene cambios locales. Guardalos o haz commit antes de cambiar a la rama de integracion.'
    }
    Say "Cambiar PyFlowMap a $FeatureBranch (sin reset ni force)"
    Run $script:GitPath @('-C', $PyFlowMapRoot, 'fetch', 'origin', $FeatureBranch)
    & $script:GitPath -C $PyFlowMapRoot show-ref --verify --quiet "refs/heads/$FeatureBranch"
    if ($LASTEXITCODE -eq 0) {
        Run $script:GitPath @('-C', $PyFlowMapRoot, 'switch', $FeatureBranch)
    } else {
        Run $script:GitPath @('-C', $PyFlowMapRoot, 'switch', '--track', "origin/$FeatureBranch")
    }
    Run $script:GitPath @('-C', $PyFlowMapRoot, 'merge', '--ff-only', "origin/$FeatureBranch")
}
function Setup-Python {
    Say 'Crear / actualizar entorno virtual en PyFlowMap'
    $launcher = @(Resolve-PythonLauncher)
    $executable = [string]$launcher[0]
    $prefix = @()
    if ($launcher.Count -gt 1) { $prefix = @($launcher[1..($launcher.Count - 1)]) }
    # Avoid embedded double quotes in python -c: Windows PowerShell 5.1 strips them.
    Run $executable ($prefix + @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'))
    $envDir = Join-Path $PyFlowMapRoot '.venv'
    $pyvenv = Join-Path $envDir 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pyvenv -PathType Leaf)) {
        Run $executable ($prefix + @('-m','venv',$envDir))
    }
    Run $pyvenv @('-m','pip','install','--upgrade','pip')
    if ($InstallCodexLabeler -or $SemanticProvider -eq 'codex') {
        $extras = 'dev,mcp,labeler-codex'
    } else {
        # pip resolves a direct Git URL again even when its distribution is
        # installed. Reuse a valid local labeler for mock/disabled workflows;
        # fetch the optional extra only when it is absent.
        & $pyvenv -m pip show p4-semantic-labeler *> $null
        if ($LASTEXITCODE -eq 0) { $extras = 'dev,mcp' }
        else { $extras = 'dev,mcp,labeler' }
    }
    Push-Location $PyFlowMapRoot
    try {
        Say "pip install -e .[$extras] (dependencias GitHub privadas: requiere credenciales Git)"
        Run $pyvenv @('-m','pip','install','-e',".[$extras]")
        Run $pyvenv @('-m','pip','check')
        Say 'Verificar importacion de P4-Semantic-Labeler v0.1.0'
        # Keep Python -c free of quoted string literals: PS 5.1 native argument
        # passing may remove nested quotes before Python receives them.
        $installedVersion = & $pyvenv -c 'import p4_semantic_labeler as pkg; print(pkg.__version__)'
        if ($LASTEXITCODE -ne 0) { throw 'No se puede importar p4_semantic_labeler. Revisa pip install y sus errores.' }
        $installedVersion = ($installedVersion | Out-String).Trim()
        if ($installedVersion -ne '0.1.0') { throw "Version inesperada de P4-Semantic-Labeler: '$installedVersion' (se esperaba v0.1.0)." }
        Write-Host "P4-Semantic-Labeler: $installedVersion" -ForegroundColor Green
    } finally { Pop-Location }
}
function Test-PyFlowMap {
    Say 'Pruebas y lint PyFlowMap (sin inferencia real de Codex)'
    $py = Join-Path $PyFlowMapRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { throw 'Falta el entorno .venv; ejecuta -Action Setup o -Action All primero.' }
    Push-Location $PyFlowMapRoot
    try {
        # Use workspace scratch storage on managed Windows profiles whose
        # default Temp directory does not grant pytest directory-list access.
        $testTemp = Join-Path $PyFlowMapRoot ('.pytest-tmp-' + [Guid]::NewGuid().ToString('N'))
        Run $py @('-m','pytest','-q','-p','no:cacheprovider',"--basetemp=$testTemp")
        Run $py @('-m','ruff','check','src','tests')
    } finally { Pop-Location }
}
function Generate-Diagrams {
    if ($SemanticProvider -eq 'codex' -and -not $AllowCodexInference) {
        throw 'Codex real NO autorizado. Usa -AllowCodexInference para ejecutar inferencia en este equipo, o -SemanticProvider mock/disabled.'
    }
    $py = Join-Path $PyFlowMapRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { throw 'Falta Python del entorno .venv; ejecuta -Action Setup primero.' }
    $dot = Get-Command 'dot.exe' -ErrorAction SilentlyContinue
    if (-not $dot) {
        throw 'Falta Graphviz (dot.exe) en PATH. Instalar: winget install -e --id Graphviz.Graphviz. Abre una terminal nueva.'
    }
    if ($SemanticProvider -eq 'codex') {
        [void](Require-Tool 'codex')
        Say 'Codex REAL habilitado explicitamente; podria consumir cuota y enviar fragmentos de P4 al proveedor.'
    }
    # Prefer a Git archive pinned to an exact SHA. If the user only has a
    # downloaded/copied P4 tree, parse it read-only and report NO commit SHA.
    $hasP4Git = Is-GitRepository $P4Root
    $sha = $null
    $zip = $null
    $digest = $null
    $inputSource = $P4Root
    $sourceMode = 'local working tree (not a reproducible Git snapshot)'
    $gitRef = $null
    if ($hasP4Git) {
        Say "Leer P4 desde ref Git $P4Ref sin modificar el repositorio"
        $sha = Git-Out @('-C',$P4Root,'rev-parse','--verify',"${P4Ref}^{commit}")
        if ($sha -notmatch '^[a-f0-9]{40}$') {
            throw "No se pudo resolver P4Ref '$P4Ref' a SHA completo: $sha"
        }
        $short = $sha.Substring(0,12)
        $resultRoot = Join-Path (Join-Path $PyFlowMapRoot 'pyflowmap-output') "p4-$short"
        New-Item -ItemType Directory -Force -Path $resultRoot | Out-Null
        $zip = Join-Path $resultRoot "p4-$short.git-archive.zip"
        Run $script:GitPath @('-C',$P4Root,'archive','--format=zip',"--output=$zip",$sha)
        $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
        # Analyze an extracted snapshot directory. PyFlowMap's ZIP input
        # adapter needs a temporary directory, which can be denied by managed
        # Windows Temp ACLs even when this workspace is writable.
        $snapshotDirectory = Join-Path $resultRoot 'source'
        New-Item -ItemType Directory -Force -Path $snapshotDirectory | Out-Null
        Expand-Archive -LiteralPath $zip -DestinationPath $snapshotDirectory -Force
        $inputSource = $snapshotDirectory
        $sourceMode = 'git archive extracted snapshot; P4 repository remains untouched'
        $gitRef = $P4Ref
    } else {
        if ($P4Ref -ne 'HEAD') {
            throw "P4 no es repositorio Git: $P4Root. No puedo resolver -P4Ref '$P4Ref'. Para comparar commits, clona P4 por separado; no modificare su carpeta actual."
        }
        Write-Warning 'P4 no contiene .git. Analizare los archivos locales de SOLO LECTURA; este resultado NO corresponde a un SHA verificable.'
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $resultRoot = Join-Path (Join-Path $PyFlowMapRoot 'pyflowmap-output') "p4-working-tree-$timestamp"
        New-Item -ItemType Directory -Force -Path $resultRoot | Out-Null
    }
    $manifest = [ordered]@{
        source_repo = $P4Root; git_ref = $gitRef; commit_sha = $sha
        source_mode = $sourceMode; archive = $zip; archive_sha256 = $digest
        semantic_provider = $SemanticProvider
        allowed_codex_inference = [bool]$AllowCodexInference
        generated_utc = (Get-Date).ToUniversalTime().ToString('o')
        entries = $Entries
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $resultRoot 'manifest.json') -Encoding UTF8
    $json = & $py -m pyflowmap 'inspect' $inputSource
    if ($LASTEXITCODE -ne 0) { throw 'Fallo pyflowmap inspect sobre el origen de P4.' }
    [System.IO.File]::WriteAllText((Join-Path $resultRoot 'inspect.json'),($json -join "`n"),[System.Text.UTF8Encoding]::new($false))

    foreach ($entry in $Entries) {
        $safe = $entry -replace '[^a-zA-Z0-9_-]','_'
        $dir = Join-Path $resultRoot ("activity-" + $safe)
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Say "UML activity: $entry"
        $params = @('analyze',$inputSource,'--entry',$entry,'--diagram-type','activity',
                    '--max-nodes',"$MaxNodes",'--max-depth','2',
                    '--language','es','--direction','TD',
                    '--format','images','--renderer','graphviz',
                    '--semantic-provider',$SemanticProvider,
                    '--semantic-max-chars',"$SemanticMaxChars",
                    '--semantic-style',$SemanticStyle,
                    '--output',$dir)
        $response = & $py -m pyflowmap @params
        if ($LASTEXITCODE -ne 0) { throw "Fallo la generacion para $entry" }
        [System.IO.File]::WriteAllText((Join-Path $dir 'result.json'),($response -join "`n"),[System.Text.UTF8Encoding]::new($false))
        $parsed = ($response -join "`n") | ConvertFrom-Json
        Write-Host "Salida: $dir" -ForegroundColor Green
        if ($parsed.warnings -and $parsed.warnings.Count -gt 0) {
            Write-Warning "El analizador ha reportado $($parsed.warnings.Count) advertencias. Consultar result.json y grafo JSON."
        }
    }
    Say "Resultados P4 ($sourceMode): $resultRoot"
}
function Configure-Mcp {
    if (-not ($ConfigureSerena -or $ConfigurePyFlowMapMcp)) { return }
    $codex = Require-Tool 'codex'
    if ($ConfigureSerena) {
        $uvx = Require-Tool 'uvx'
        & $codex mcp get serena *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Warning 'Ya existe MCP serena en Codex. No lo sobrescribo; revisa: codex mcp get serena'
        } else {
            Say 'Registrar Serena MCP en Codex (configuracion global)'
            # Serena arranca por stdio con contexto codex, activado en PyFlowMap.
            Run $codex @('mcp','add','serena','--',$uvx,'--from',
                           'git+https://github.com/oraios/serena','serena',
                           'start-mcp-server','--context','codex','--project',$PyFlowMapRoot)
        }
    }
    if ($ConfigurePyFlowMapMcp) {
        $mcp = Join-Path $PyFlowMapRoot '.venv\Scripts\pyflowmap-mcp.exe'
        if (-not (Test-Path -LiteralPath $mcp)) { throw 'Primero instala .[mcp] con -Action Setup.' }
        & $codex mcp get pyflowmap *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Warning 'Ya existe MCP pyflowmap en Codex; no lo sobrescribo.'
        } else {
            Say 'Registrar MCP local de PyFlowMap en Codex'
            # Solo el arbol de PyFlowMap queda autorizado: los snapshots ZIP de P4
            # se guardan alli. No damos permiso de escritura MCP en el repo P4.
            Run $codex @('mcp','add','pyflowmap','--env',"PYFLOWMAP_ALLOWED_ROOTS=$PyFlowMapRoot",'--',$mcp)
        }
    }
    Run $codex @('mcp','list')
}
function Save-CodexTask {
    $prompt = @'
# Tarea Codex local - PyFlowMap + P4-Semantic-Labeler

Proyecto modificable: __PYFLOWMAP__
Proyecto SOLO LECTURA: __P4__

1. Activa Serena en PyFlowMap y revisa el MCP de PyCharm si esta habilitado.
2. Lee docs/p4-semantic-labeler-integration.md y la API del tag v0.1.0.
3. Verifica la instalacion del extra labeler-codex, el adaptador Python,
   las herramientas CLI/MCP y el manejo de advertencias y errores.
4. Corrige SOLO PyFlowMap, con pruebas nuevas cuando correspondan. No copiar
   P4-Semantic-Labeler ni modificar P4-Planning-Agent ni P4-Codex-Bridge.
5. No ejecutes Codex como proveedor de etiquetas sin mi autorizacion explicita.
   Usa provider=mock para las pruebas. No inicies servidores adicionales.
6. Comprueba que el enriquecimiento cambia textos pero no nodos, ramas,
   etiquetas Si/No, aristas ni procedencia. Conserva trazabilidad JSON.
7. Ejecuta pytest y ruff. Verifica la generacion de SVG+PNG del snapshot Git
   de P4 mediante este script. Conserva avisos de truncado.
8. Resume cambios, pruebas y pendientes. No hagas push ni merge salvo orden.

Con PyCharm: activar MCP en Settings > Tools > MCP Server, Auto-Configure Codex;
no activar Brave Mode / comandos sin confirmacion.
'@
    $prompt = $prompt.Replace('__PYFLOWMAP__',$PyFlowMapRoot).Replace('__P4__',$P4Root)
    $path = Join-Path (Join-Path $PyFlowMapRoot 'pyflowmap-output') 'CODEX-TASK.md'
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    [IO.File]::WriteAllText($path,$prompt,[System.Text.UTF8Encoding]::new($false))
    Write-Host "Instrucciones Codex: $path" -ForegroundColor Green
}

# ------------ Inicio ------------
# Works when installed in scripts/ inside the Git checkout, copied into
# the checkout root, or launched externally from the checkout directory.
# Do not assume the old non-Git PyFlowMap directory exists.
if (-not $PyFlowMapRoot) {
    $candidates = @($PSScriptRoot, (Split-Path -Parent $PSScriptRoot), (Get-Location).Path)
    foreach ($candidate in $candidates) {
        if ($candidate -and
            (Test-Path -LiteralPath (Join-Path $candidate 'pyproject.toml') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $candidate 'src\pyflowmap\cli.py') -PathType Leaf)) {
            $PyFlowMapRoot = $candidate
            break
        }
    }
    if (-not $PyFlowMapRoot) {
        throw 'No se encuentra el codigo de PyFlowMap. Indica -PyFlowMapRoot F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git.'
    }
}
$PyFlowMapRoot = [IO.Path]::GetFullPath($PyFlowMapRoot)
$P4Root = [IO.Path]::GetFullPath($P4Root)
if ($PyFlowMapRoot -eq $P4Root) { throw 'Las rutas de PyFlowMap y P4 deben ser distintas.' }
if (-not (Test-Path -LiteralPath $PyFlowMapRoot -PathType Container)) { throw "No existe PyFlowMap: $PyFlowMapRoot" }
if (-not (Test-Path -LiteralPath $P4Root -PathType Container)) { throw "No existe P4: $P4Root" }
$GitPath = Require-Tool 'git'
Check-PyFlowMapSource
if ($Action -in @('Diagrams','All') -and -not (Test-Path -LiteralPath (Join-Path $P4Root 'planning') -PathType Container)) {
    Write-Warning 'No encuentro la carpeta planning en P4. Revisa -P4Root y usa pyflowmap inspect para ver entradas disponibles.'
}
if ($Action -in @('Setup','All')) { Setup-Python }
if ($Action -in @('Test','All')) { Test-PyFlowMap }
if ($Action -in @('Diagrams','All')) { Generate-Diagrams }
Configure-Mcp
Save-CodexTask
Say 'Paso manual PyCharm: abrir PyFlowMap, seleccionar .venv\Scripts\python.exe, habilitar MCP Server y Auto-Configure Codex.'
if ($LaunchCodex) {
    $codex = Require-Tool 'codex'
    Say 'Iniciando Codex interactivo en el repo modificable (no inicia generacion semantica automaticamente)'
    Push-Location $PyFlowMapRoot
    try { & $codex } finally { Pop-Location }
} else {
    Write-Host "Para iniciar Codex: Set-Location '$PyFlowMapRoot'; codex" -ForegroundColor Yellow
}
