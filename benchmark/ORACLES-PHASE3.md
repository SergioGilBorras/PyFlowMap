# Oráculo semántico versionado de Fase 3

`oracles.py` permanece sin cambios y define los resultados históricos V4/Fase 2. La Fase 3 usa `oracles_phase3.py` mediante `run_phase3.py`; su identificador es `phase3-match-guard-v1`.

La versión corrige dos fallos genéricos del criterio de `match/case`:

1. Separa los selectores de patrones (`match_case_index`) de las decisiones de guardas (`match_guard_case_index`). Así, una guarda no se trata como otro selector ni se exige que desde ella puedan alcanzarse cuerpos de casos anteriores.
2. Comprueba que el rechazo de patrón y el resultado falso de una guarda avanzan al caso siguiente, que el resultado verdadero de la guarda llega al cuerpo correspondiente y que no se retrocede directamente a un caso anterior.
3. Comprueba el enlace de capturas antes de evaluar guardas que las leen.

Los casos de `oracle-audit/phase3/fixtures/` son reproducciones nuevas fuera de las quince entradas congeladas. `test_phase3_oracles.py` contiene mutaciones de polaridad, orden de casos y orden de capturas para comprobar que el oráculo corregido rechaza esos grafos. El código analizado no se ejecuta.

Ejecución:

```powershell
& '.\.venv\Scripts\python.exe' -m benchmark.run_phase3 --output '.\benchmark-results\phase3-match-audit-20261013\normal-final' --render
& '.\.venv\Scripts\python.exe' -m benchmark.run_phase3 --output '.\benchmark-results\phase3-match-audit-20261013\strict-final' --render --strict
```
