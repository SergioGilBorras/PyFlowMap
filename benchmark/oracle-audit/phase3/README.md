# Fixtures de reproducción P0 para match/case

Estos programas son fixtures nuevos e independientes del banco transversal. El benchmark los analiza estáticamente; no ejecuta sus funciones.

- `fixtures/ordered_dispatch.py` reproduce el falso FAIL del oráculo V4/Fase 2: una guarda comparte línea con el selector de caso en el grafo y el oráculo confundía ambos como selectores de patrones.
- `fixtures/capture_guard.py` reproduce la evaluación de una guarda antes de enlazar las capturas que la guarda lee.

Los fixtures se conservan fuera de las quince entradas y sus oráculos existentes.
