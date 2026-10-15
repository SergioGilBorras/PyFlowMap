# Regresiones adversarias Fase 4.1

Estas reproducciones son independientes de los quince fixtures históricos. Cada mutación conserva la arista correcta cuando agrega una arista imposible.

| Prueba | Mutación comprobada | Resultado esperado |
|---|---|---|
| `test_positive_pattern_path_cannot_gain_an_edge_to_a_later_case_body` | Se agrega un destino del cuerpo de un caso posterior a la arista Sí válida del patrón actual. | FAIL |
| `test_guard_true_cannot_skip_its_body_for_a_later_case` | Se agrega un destino del caso posterior a la rama Sí válida de la guarda. | FAIL |
| `test_terminal_return_cannot_gain_an_ordinary_successor` | Se agrega una continuación normal desde un resultado terminal, manteniendo su salida al final. | FAIL |
| `test_each_explicit_return_is_checked_even_when_it_is_not_a_distinct_value` | Se elimina del grafo el nodo de uno de dos retornos explícitos. | FAIL |
| `test_python_bytes_set_and_complex_literals_do_not_crash_the_evaluator` | Se evalúan retornos literales `bytes`, `set` y `complex`. | Sin excepción |
| `test_context_manager_with_multiple_exit_routes_remains_uncertain` | `__exit__` tiene varias rutas y devuelve `False` en ellas. | REVIEW conservador |
| `test_context_body_omission_is_rejected` | Se eliminan las actividades fuente enlazadas a una ruta de retorno del cuerpo protegido. | FAIL |
| `test_async_context_manager_keeps_entry_body_and_exit_visible` | Se inspecciona la secuencia de `async with` y sus actividades. | Entrada, cuerpo y salida visibles |

Ejecución local: `python -m pytest -q -p no:cacheprovider benchmark/test_phase4_1_oracle_adversarial.py` — 9 pruebas aprobadas.

El script de reproducciones de la auditoría independiente `Reproducir-Falsos-PASS-Fase4.py` y el informe `Auditoria-Independiente-PyFlowMap-Fase4.md` no estaban presentes en el árbol al preparar esta versión. Por ello, esta tabla documenta las mutaciones genéricas propias y no afirma haber ejecutado esos dos archivos externos.
