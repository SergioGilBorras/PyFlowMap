# PyFlowMap — Segunda batería independiente V2

Banco transversal **nuevo** de 30 casos y 38 módulos Python, independiente de la primera batería de 28 casos y del benchmark histórico.

## Protocolo

1. Congelar previamente la versión exacta del analizador y los oráculos; guardar SHA-256 del código, estado Git y configuración.
2. Extraer esta carpeta **fuera** de `PyFlowMap-git` y no modificar fixtures ni parámetros.
3. Ejecutar `run.py` con el Python de la `.venv` de PyFlowMap, `--project-root` apuntando al checkout y `--package`.
4. Conservar los JSON, Mermaid, SVG y PNG de los 30 casos junto con warnings y stdout/stderr.
5. Entregar el ZIP resultante para auditoría semántica **antes de corregir el analizador**.

## Ejemplo PowerShell

```powershell
& "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git\.venv\Scripts\python.exe" "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-Banco-Independiente-V2\run.py" --project-root "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git" --output "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-Blind-Results-V2" --package
```

**No ejecutar los fixtures.** El runner solo los parsea y ejecuta PyFlowMap en un proceso separado. Los fixtures no hacen llamadas a red ni requieren paquetes instalados.

El informe del runner marca `GENERATED` o error de generación y deja `semantic_status=NOT_EVALUATED`. **No existe oráculo que otorgue PASS automáticamente**. Los nombres y dominios de estos casos son decorativos: los criterios se basan exclusivamente en la semántica de Python.

Las nuevas combinaciones incluyen `match` múltiples, `except*`, MRO múltiple, generadores asíncronos, contextos, cierres, recursión mutua, imports con alias y funciones homónimas entre módulos, expresiones con llamadas, `for/else` y `while/else`.

**Importante:** El segundo banco deja de ser independiente después de utilizar sus resultados para corregir PyFlowMap. En ese momento pasa a ser un banco de regresión, y hará falta una tercera evaluación inédita.
