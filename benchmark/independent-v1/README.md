# Banco transversal independiente V1 — PyFlowMap

**Objetivo:** medir generalización, **después** de congelar la versión corregida de Fase 5, con 28 casos inéditos y 33 módulos Python. No es una colección de reglas de P4 ni reutiliza los quince fixtures anteriores. No fue utilizado para implementar Fase 5.

## Protocolo de primera ejecución ciega

1. Registrar y congelar los hashes de todos los `.py` en `src/pyflowmap`, la configuración y el estado Git real, incluyendo las modificaciones locales sin commit. No basta con el SHA del HEAD.
2. Extraer esta carpeta **fuera** del repositorio PyFlowMap. No editar los fixtures para facilitar resultados. Mantener el proveedor semántico deshabilitado.
3. Ejecutar el runner sobre esa versión congelada. El runner **solo analiza sintácticamente** los fixtures y llama a la CLI PyFlowMap como subprocess; no importa ni ejecuta el código de ejemplo.
4. No introducir parches entre ejecuciones ni interpretar los informes de generación como PASS semánticos. Guardar la primera ejecución, incluso si algunos casos dan error.
5. Entregar a un evaluador independiente el ZIP de resultados, que incluirá los programas originales, JSON, SVG, PNG, Mermaid, advertencias, salida estándar y huellas de producción.
6. Revisar qué es fallo demostrado, incertidumbre razonable, límite de profundidad o problema de visualización. Los problemas nuevos pasan a regresión conocida después de la primera auditoría.

## Comandos desde PowerShell

En la carpeta que contenga este `run.py` (adaptar la ruta del Python virtual si fuera necesario):

```powershell
& "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git\.venv\Scripts\python.exe" ".\run.py" --list
& "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git\.venv\Scripts\python.exe" ".\run.py" --validate-only
& "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git\.venv\Scripts\python.exe" ".\run.py" --project-root "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-git" --output "F:\ProyectosPYCHARM\PythonProject\PyFlowMap-Blind-Results-V1" --package
```

La tercera orden creará `PyFlowMap-Blind-Results-V1/` y `PyFlowMap-Blind-Results-V1.zip`. El ZIP resultante es lo que debe enviarse para una revisión semántica independiente.

Los parámetros quedan fijados en `cases.json`: `max_nodes=30`, `max_depth=3`, español, Graphviz, `format=all`, proveedor deshabilitado y timeout de 180 segundos. Los resultados son comparables a esta configuración, **no necesariamente** a cualquier otra.

## Interpretación responsable

- `GENERATED`: la CLI terminó correctamente y se encontró un JSON con nodos y aristas. No significa que el diagrama sea correcto.
- `RUN_ERROR`, `TIMEOUT`, `MISSING_GRAPH_JSON`: requieren diagnóstico independiente de las reglas del lenguaje.
- `NOT_EVALUATED`: toda la semántica queda intencionadamente sin puntuar hasta revisar el ZIP.
- Las advertencias no implican automáticamente FAIL y su ausencia no implica corrección.
- Los casos con recursión, métodos dinámicos, decoradores, async y generadores pueden necesitar REVIEW justificado si el análisis es necesariamente conservador.

## Áreas examinadas

Patrones anidados y de clase; capturas y guardas; `for/else`, `while/else` y `async for`; `break` y `continue`; retornos y excepciones a través de `with`, `async with` y `finally`; reemplazo de transferencias en `finally`; comprensión eager frente a generadores perezosos; `yield` y `yield from`; funciones locales y `nonlocal`; decoradores; herencia y `super`; recursión; importaciones entre módulos; expresiones condicionales, cortocircuito y `:=`; despacho dinámico.

**Los fixtures contienen código Python para análisis AST. No deben ejecutarse como aplicaciones.** Para proyectos reales independientes será necesaria una fase complementaria: estos 28 programas sintéticos no representan por sí solos todas las arquitecturas reales.
