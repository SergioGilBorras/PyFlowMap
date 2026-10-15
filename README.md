# PyFlowMap

PyFlowMap extracts conservative, static activity diagrams from Python source.
It parses with `ast` and **never imports or executes the analyzed project**.
Diagrams retain source symbols and locations; inspect JSON warnings for
approximated or unsupported control flow.

## Install

Requires Python 3.11 or later. Graphviz is recommended for SVG and PNG output.

### Windows

Install Python, Git for Windows, and Graphviz (`winget install -e --id
Graphviz.Graphviz`), then open PowerShell in this checkout:

```powershell
Set-Location 'F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git'
.\Setup-PyFlowMap-Local.ps1 -Action All -SemanticProvider disabled
```

The installer creates or updates `.venv`, runs pytest and Ruff, and can render
the coordinator and entry-point diagrams from the read-only P4 source. Set
`-P4Root` if P4 is in a different location. Use `-Action Setup`, `Test`, or
`Diagrams` to run a single phase. `-SemanticProvider mock` exercises the
optional labeler without AI inference; `disabled` keeps deterministic labels.
Codex inference is never enabled implicitly. The script can also be run from
another directory with `-PyFlowMapRoot <checkout>`.

The installer pins `portable-tempdirs` to commit
`fd6dbd640630e6911a53b4d756089099ec870a8b`. Pytest allocates an owned,
per-run directory under this checkout for `--basetemp`; this applies to the
installer, direct pytest runs, and PyCharm. ZIP inputs use the same manager.
For direct CLI or MCP use, temporary files go under the current directory by
default; set `$env:PYFLOWMAP_TEMP_ROOT` to an existing writable directory when
the current directory is not an approved workspace.

### macOS and Linux

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,mcp]'
```

Install Graphviz with the operating system's package manager when image export
is needed. Mermaid CLI is an alternative renderer and requires Node.js.

## Use the CLI

```bash
pyflowmap inspect ./my_project
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --format mmd
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run \
  --format images --renderer graphviz --output ./diagrams
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --view overview --format images --renderer graphviz --output ./diagrams
pyflowmap analyze ./my_project --entry app.pipeline:Pipeline.run --view hierarchical --max-depth 2 --format all --renderer graphviz --output ./diagrams
```

Inputs can be a directory, a Python file, or a ZIP containing Python files.
Use the fully qualified entry ID returned by `inspect` when a name is
ambiguous. `--scope` restricts entry discovery; resolvable local dependencies
may still be examined outside that scope.

Each analysis writes editable Mermaid (`.mmd`) and a traceable graph (`.json`).
`--format svg`, `png`, `images`, or `all` adds rendered images. Graphviz SVG
uses UTF-8, including for Spanish labels. `max_nodes` is a soft limit: the
analyzer preserves branch topology and reports when a graph cannot be
simplified safely to the requested size.

`--view overview` produces a process-level call outline from statically
observed invocation boundaries. It is labeled `process-summary`, not UML
activity: its arrows show call nesting, and its warnings point to the detailed
activity for predicates and branch paths. JSON retains each call site's source
symbol, location, resolution status, and summarized internal call sites.

`--view hierarchical` selects the most structurally complex summarized
subprocess with known internal calls and presents its top-level decisions as a
compact activity phase outline. Each phase keeps source locations and call
references; nested conditions remain in the linked full-detail activity. The
index also lists each statically possible call target separately, so sibling
calls are not laid out as an unconditional sequence. It links back to the main
SVG and is useful when one activity is too dense to inspect as a single diagram.

When a summarized function contains uniquely identified possible project-local
dispatches, the output also includes an independent activity diagram per call
site. These diagrams show each possible target on its own; their order does
not imply that all targets run sequentially. Within one graph, a symbol is
expanded at most once; later calls remain visible as activities with source
and resolution metadata instead of duplicating its internal flow. Synchronous
`with` and asynchronous `async with` show manager entry, body, and exit. Since
context-manager suppression and exception behavior is dynamic, the graph marks
possible suppression and keeps an uncertainty warning.

## Use the MCP server

Install the MCP extra and set the roots the server may inspect or write:

```powershell
python -m pip install -e '.[mcp]'
$env:PYFLOWMAP_ALLOWED_ROOTS = 'F:\Work\MyProject;F:\Work\Diagrams'
pyflowmap-mcp
```

On Windows, separate roots with `;` (`os.pathsep`); on POSIX, use `:`. The
server defaults to the current directory if the variable is unset. Every
source and output path must resolve within an allowed root. Keep P4 outside
the allowlist when using MCP if it must remain read-only. Set
`PYFLOWMAP_TEMP_ROOT` to an existing writable approved workspace for ZIP inputs.

## Optional semantic labels

Normal analysis uses deterministic labels and makes no provider calls. The
optional P4-Semantic-Labeler integration can be checked with
`--semantic-provider mock`; mock labels are synthetic and do not assess
semantic quality. `--semantic-provider codex` requires the explicit Codex
extra and a deliberate command-line choice. Provider output can change node
text only; it cannot change decisions, edges, or source provenance.

## Development

Validation tools are development-only; installing PyFlowMap for ordinary use
does not install pytest, Ruff, benchmark fixtures, or evaluator code.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
pyflowmap --version
python scripts/build_release.py
```

The release builder creates a wheel and source distribution locally, checks
their contents, installs the wheel in a temporary clean environment, and
smoke-tests CLI, MCP, JSON, Mermaid, SVG, and PNG. It does not publish packages.
GitHub Actions runs the test matrix and the Ubuntu release smoke check; Linux is
considered validated only after that workflow completes successfully.

Technical details are kept in focused documents:

- [Architecture](docs/architecture.md)
- [Analysis rules and limitations](docs/analysis-rules.md)
- [Diagram type roadmap](docs/diagram-types.md)
- [P4 labeler integration API](docs/p4-semantic-labeler-integration.md)
- [Reference snapshot and hash policy](docs/reference-testing.md)
- [Semantic labeling details](docs/semantic-labeling.md)

Historical result README files under `examples/results/` document earlier
outputs and remain alongside their artifacts.

## Alcance y limitaciones del análisis estático

PyFlowMap lee el AST y muestra rutas posibles; no ejecuta ni importa el
programa analizado. Corrige los defectos cuando el código fuente determina el
flujo, las operaciones o su procedencia. Cuando los datos o el entorno deciden
el resultado, conserva las alternativas visibles y explica qué no puede
determinar.

- **CORREGIBLE**: un error verificable del grafo, una operación omitida sin
  resumen, procedencia incorrecta o navegación rota.
- **PARCIAL**: el AST identifica parte del comportamiento, pero el resultado
  exacto depende de datos, objetos o del entorno en ejecución.
- **LIMITACIÓN ESTÁTICA**: no existe una respuesta general exacta sin ejecutar
  código o conocer el entorno. Se muestra la llamada, las rutas posibles y el
  límite; no se trata como un defecto abierto.

`yield` y `yield from` muestran suspensión, reanudación y cierre. El cierre
inyecta `GeneratorExit` en el punto suspendido y recorre los `except` y
`finally` presentes en el código. En un generador asíncrono se representa
`aclose` y la limpieza que contiene; no se predicen los valores de `send` o
`throw`, el consumo futuro, el scheduling ni los efectos dinámicos de un
manejador. `except*` conserva el orden de las cláusulas, permite que se
ejecuten para subgrupos distintos y representa la posible propagación de un
remanente. No afirma qué tipos contendrá un grupo en ejecución.

Las sentencias de asignacion admitidas (`Assign`, `AnnAssign`, `AugAssign` y
expresiones `:=`) aparecen en la rama donde se ejecutan, con sentencia y
procedencia. Sus llamadas se conservan en el orden de evaluacion de Python;
las asignaciones en cuerpos `match/case` conectan con usos posteriores sin
encadenar casos diferentes. Las rutas que omiten una asignacion siguen
visibles, por lo que no se afirma que una variable este inicializada en todas
las rutas. Las asignaciones que alimentan un sujeto de `match` aparecen con su
procedencia. El desempaquetado se muestra como operación y conserva una ruta
posible para errores de iterabilidad o cantidad de elementos. Las rutas de
`with`, `await`, despacho, recursión y comprensiones conservan sus alternativas
y límites estáticos. Las actividades resumidas mantienen ubicación y
metadatos; las vistas jerárquicas ayudan a leer grafos densos sin quitar
caminos. La clasificación detallada está en [reglas y alcance del análisis](docs/analysis-rules.md).

MIT License.
