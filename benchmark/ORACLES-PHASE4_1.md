# Oráculo semántico PyFlowMap Fase 4.1

Fase 4.1 versiona un evaluador independiente en `oracles_phase4_1.py`. El oráculo anterior y sus baselines se conservan sin cambios. El wrapper `run_phase4_1.py` usa el harness transversal existente y mantiene el proveedor semántico deshabilitado.

## Criterios añadidos

- Para cada `match`, revisa rutas posibles y prohibidas por polaridad dentro de esa ejecución concreta. Un éxito no puede saltar a un caso posterior; el fallo de patrón o de guarda no puede entrar en su propio cuerpo. La búsqueda se detiene en el cuerpo del caso para no confundir el siguiente ciclo de un bucle con un retroceso de casos.
- Cada `return` explícito necesita un resultado o transferencia fuente enlazados. Si solo hay una expresión de llamada visible, el criterio queda en REVIEW; la actividad de llamada por sí sola no demuestra que se haya conservado el retorno.
- Un resultado o `raise` terminal no puede continuar por una arista normal. Se permiten el nodo final, el despacho del gestor de contexto y las actividades del `finally` asociado.
- `with` y `async with` comprueban entrada, líneas ejecutables del cuerpo, salida y transferencias `return`, `raise`, `break` y `continue`. La supresión permanece en REVIEW ante comportamiento dinámico; una ruta que devuelve `False` no basta para probar todas las rutas.
- Las claves internas de literales distinguen bytes, conjuntos, complejos y contenedores sin depender de que JSON pueda serializarlos directamente.

## Pruebas y resultados

Las regresiones nuevas están en `test_phase4_1_oracle_adversarial.py`, con fuente genérica en `oracle-audit/phase4_1/fixtures/python_semantics.py`. Las ejecuciones normales y estrictas, la comparación Fase 4/Fase 4.1 y los hashes se guardan en `benchmark-results/phase4.1-oracle-20261013/`.

El oráculo solo puede comprobar evidencia estática serializada. No ejecuta fixtures ni resuelve de forma general despacho dinámico, efectos laterales de patrones/guardas, ni todos los efectos de `finally` y gestores de contexto.
