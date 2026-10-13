"""Run the transversal benchmark using the Phase 5 semantic evaluator."""
from __future__ import annotations

try:
    from . import run
    from .oracles_phase5 import evaluate_semantics
except ImportError:
    import run
    from oracles_phase5 import evaluate_semantics

run.evaluate_semantics = evaluate_semantics

if __name__ == "__main__":
    raise SystemExit(run.main())
