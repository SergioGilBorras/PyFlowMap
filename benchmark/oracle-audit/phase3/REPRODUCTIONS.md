# Reproducción previa de los dos P0

Los dos fixtures son deliberadamente pequeños y genéricos; no pertenecen al conjunto transversal congelado.

## Falso FAIL del oráculo histórico

fixtures/ordered_dispatch.py es un match ordenado válido con cuatro alternativas y una guarda. El grafo actual del analizador satisface el flujo: el rechazo de "closed" pasa al caso "ready"; si enabled(value) es falso, la búsqueda continúa al siguiente caso "ready"; y cada cuerpo seleccionado queda separado. benchmark/test_phase3_oracles.py::test_valid_guarded_ordered_match_no_longer_gets_false_fail comprueba el mismo grafo con ambas versiones: el oráculo histórico declara FAIL, mientras phase3-match-guard-v1 declara PASS para la característica match-case.

La causa está en la selección del oráculo histórico por línea: recoge tanto el selector case "ready" como la decisión enabled(value) como selectores de patrones y exige que cada uno alcance todos los cuerpos. Una decisión de guarda no puede alcanzar cuerpos de casos anteriores, así que ese requisito rechaza un grafo correcto. La Fase 3 usa el índice de caso del selector y metadatos separados para decisiones de guarda.

## Capturas disponibles antes de evaluar la guarda

fixtures/capture_guard.py enlaza payload en un patrón mapping y lo usa en usable(payload). Antes de la corrección, _match llamaba primero a _condition_paths para la guarda y creaba el nodo de enlace después: el grafo situaba la llamada/decisión usable(payload) antes de Bind pattern captures: payload. Python enlaza las capturas de un patrón exitoso antes de evaluar su guarda.

La implementación mueve el enlace entre la selección positiva del patrón y la evaluación de la guarda. La prueba de análisis comprueba esa secuencia; la prueba de mutación mueve artificialmente la llamada de guarda antes del enlace y verifica que el oráculo versionado detecta FAIL.

Las demás mutaciones invierten las polaridades Sí/No de la guarda y redirigen el rechazo de un caso a uno anterior. El oráculo debe marcar ambos grafos FAIL. Para expresiones de guarda compuestas con and/or, el oráculo se abstiene con REVIEW hasta disponer de evidencia de salida agregada que permita distinguir los cortocircuitos internos del resultado final de la guarda.
