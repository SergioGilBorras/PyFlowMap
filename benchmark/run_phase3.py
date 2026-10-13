"""Run the transversal benchmark with the versioned Phase 3 oracle."""
from __future__ import annotations

try:
    from . import run
    from .oracles_phase3 import evaluate_semantics
except ImportError:  # Direct execution as ``python benchmark/run_phase3.py``.
    import run
    from oracles_phase3 import evaluate_semantics

run.evaluate_semantics = evaluate_semantics


if __name__ == "__main__":
    raise SystemExit(run.main())
