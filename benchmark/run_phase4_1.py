"""Run the transversal benchmark with the independent Phase 4.1 oracle."""
from __future__ import annotations

try:
    from . import run
    from .oracles_phase4_1 import evaluate_semantics
except ImportError:  # Direct execution as ``python benchmark/run_phase4.py``.
    import run
    from oracles_phase4_1 import evaluate_semantics

run.evaluate_semantics = evaluate_semantics


if __name__ == "__main__":
    raise SystemExit(run.main())
