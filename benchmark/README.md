# Banco de pruebas transversal — PyFlowMap

**Objetivo:** medir la calidad de los diagramas de actividad sobre *código Python arbitrario*, no adaptar PyFlowMap a P4-Planning-Agent ni a ningún dominio.

Este paquete contiene **15 casos independientes** y un ejecutor de evaluación sin dependencias adicionales. **No importa ni ejecuta el código analizado:** solamente hace `ast.parse` como comprobación de sintaxis y llama al CLI de PyFlowMap. Ejecuta siempre `--semantic-provider disabled` para evitar inferencias de modelos.

## Uso en el proyecto Windows

Extrae la carpeta `benchmark/` en la raíz de `F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git` y, desde esa carpeta de PowerShell, ejecuta:

```powershell
& '.\.venv\Scripts\python.exe' '.\benchmark\run.py' --list
& '.\.venv\Scripts\python.exe' '.\benchmark\run.py' --output '.\benchmark-results' --render
```

El segundo comando necesita Graphviz `dot` en PATH; genera un SVG y un PNG por caso, los JSON de grafo, Mermaid y los informes `report.json`, `report.csv`, `REPORT.md`, `gallery.html`. Abre `benchmark-results/gallery.html` en tu navegador y examina las figuras.

Para una evaluación más estricta que rechace las llamadas críticas ocultas en metadatos, los call sites ausentes y las decisiones esperadas omitidas:

```powershell
& '.\.venv\Scripts\python.exe' '.\benchmark\run.py' --output '.\benchmark-results-strict' --render --strict
```

**Importante:** no ejecutes `--strict` esperando necesariamente verde en la versión actual: si encuentra problemas, esa es precisamente su función. Deja que Codex reporte primero el baseline sin modificar el analizador.

Para ejecutar dos casos concretos:

```powershell
& '.\.venv\Scripts\python.exe' '.\benchmark\run.py' --only cli scheduling --output '.\benchmark-results-smoke' --render
```

La salida se crea fuera de `benchmark/fixtures`. Añade `benchmark-results*/` a `.gitignore` en el repositorio: los informes de exploración no son código fuente. **No borres resultados locales preexistentes**, porque son evidencia comparativa.

## Cobertura

| ID | Ámbito | Construcciones Python |
|---|---|---|
| commerce | Comercio | Condicionales y devoluciones tempranas |
| etl | Ingeniería de datos | `for`, `continue`, `break`, `try/except/else` |
| cli | Línea de comandos | Inyección de dependencias, receptor condicional, códigos de retorno |
| network | Servicios | `async/await`, excepciones |
| iot | Dispositivos | `match/case`, patrones y guards |
| resources | Gestión de recursos | `with`, retornos tempranos |
| logic | Lógica genérica | `and/or`, operador condicional, efectos laterales |
| scheduling | Gestión de tareas | Funciones anidadas y cierres léxicos |
| algorithms | Algoritmos | Recursión y caso base |
| security | Autorización | `raise`, `try/finally` |
| workflow | Procesos administrativos | Decisiones y estados |
| multimodule | Proyecto modular | Importación relativa, llamadas entre módulos |
| plugins | Plugins | Decoradores y despacho de receptor dinámico |
| analytics | Analítica | Comprensiones |
| library | OO | Herencia, sobreescritura y `self` |

## Criterios estructurales y semanticos

`benchmark/run.py` usa el evaluador canónico `benchmark/oracles_current.py`
(actualmente `phase5.2`). Las implementaciones históricas permanecen disponibles
como `oracles.py`, `oracles_phase3.py`, `oracles_phase4.py`, `oracles_phase4_1.py`
y `oracles_phase5.py`; para reproducir una matriz antigua se debe usar el runner
versionado que la produjo, no cambiar la importación del runner por parcheo.

El ejecutor separa los errores estructurales del dictamen semantico. La estructura cubre JSON, nodos inicial/final, endpoints validos, alcance y posibilidad de alcanzar un final. Tambien informa los minimos manuales de decisiones y los marcadores de llamada; estos ultimos solo se consideran visibles si existe un nodo de llamada (`significant_call`) con expresion concordante. Una actividad que comparte ubicacion o que contiene llamadas solo en metadatos no cuenta como llamada visible.

Los oraculos semanticos se derivan del AST de Python y comprueban match/case (alternativas, guardas y cuerpos), for/else (agotamiento frente a break), valores de retorno literales diferenciados, terminacion por raise, orden y cortocircuito and/or, entrada/salida de with y async with, resolucion/expansion de llamadas, y visibilidad de llamadas dentro de comprensiones. No se ejecutan las muestras ni se usa IA.

Cada caso obtiene uno de estos estados semanticos:

- `PASS`: satisface los oraculos semanticos verificables del caso.
- `FAIL`: incumple un criterio semantico verificable.
- `REVIEW`: hay destinos dinamicos, aproximaciones o expansion incompleta que requiere revision.
- `UNSUPPORTED`: el oraculo declara expresamente que la construccion no esta cubierta.

Los CSV/JSON separan `semantic_status`, `structural_status`, advertencias, conteos y metadatos de llamadas. El modo normal devuelve error si hay un `FAIL`; `--strict` devuelve error si algun caso no es `PASS`. Un resultado verde no equivale a una prueba formal del CFG: revisar `benchmark/oracles.py` y `benchmark/test_oracles.py` antes de interpretar el alcance.

Pruebas independientes del evaluador:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest benchmark.test_harness benchmark.test_oracles -v
& '.\.venv\Scripts\python.exe' benchmark/metamorphic.py --output '.\benchmark-results\metamorphic'
```

El ejecutor metamorf simple compara topologia normalizada tras renombrar variables/funciones, clases/metodos, modulos/importaciones relativas, reescribir una condicion equivalente y mover el proyecto de ruta. Los nombres y ubicaciones no forman parte de la firma topologica.

## Protocolo anti-overfitting

1. **Congelar este conjunto de datos como baseline** antes de tocar el analizador. Conservar los informes de la versión actual.
2. Evaluar por **construcción sintáctica** (AST) y por **dominio**, nunca por coincidencia con nombres comerciales, estados concretos o métodos de P4.
3. Añadir a futuro proyectos de código real independientes como **holdout**, no visibles durante el desarrollo. Mantener P4 solo como regresión de integración y no como objetivo de optimización.
4. Implementar pruebas *metamórficas*: renombrar variables, mover el proyecto a otra ruta, cambiar literales equivalentes, ordenar funciones independientes, cambiar LF/CRLF, sustituir nombres de clases o dominios. Las propiedades del control de flujo que no dependen de esos nombres deben permanecer invariantes.
5. Comprobar las propiedades reales de Python: un `return` no continúa, `raise` no cae a la rama normal, `break` sale del bucle, `continue` salta a la siguiente iteración, los operadores booleanos cortocircuitan, `finally` conserva sus rutas y las llamadas sin resolución deben estar identificadas como incertidumbre.
6. Separar métricas de **fidelidad** (cobertura, errores semánticos, falsos positivos) de **presentación** (tamaño, cruces, densidad). Nunca «arreglar» una regresión haciendo pasar una imagen más bonita.
7. Prohibir condicionales productivos basados en IDs/nombres de fixtures. El lugar de las expectativas concretas es `benchmark/cases.json` y los tests, **no `src/pyflowmap`**.
8. Ejecutar en Windows y Linux, como mínimo; mantener tolerancias para diferencias visuales de Graphviz. No comparar PNG bit a bit.

## Criterio de avance para Codex

Pide una tabla con **los 15 resultados antes y después de cada cambio** (fallos estructurales, call sites visibles, decisiones, advertencias, nodos y aristas) y un resumen de regresiones. Una mejora para un caso que perjudique otro no debe aceptarse sin análisis. No transformar las muestras en tests que simplemente verifican el resultado actual del propio programa (oráculo circular).

## Compatibilidad y límites

- El benchmark está diseñado para `pyflowmap analyze` con el CLI de actividad del proyecto; la rama local no publicada podría requerir ajustes menores de nombres de parámetros.
- Para generar SVG/PNG se necesita Graphviz. Sin `--render`, solo se generan Mermaid y JSON.
- El ejecutor se ha comprobado sintácticamente y se han parseado los 15 fixtures, pero **no se ha ejecutado contra tu copia local de PyFlowMap**, a la que no tenemos acceso en este entorno. No se atribuyen resultados de calidad inexistentes.
- El benchmark se centra en Python; admitir otros lenguajes es otra ampliación del producto.
