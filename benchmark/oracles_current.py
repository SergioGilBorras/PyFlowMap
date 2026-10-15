"""Canonical semantic evaluator used by the default benchmark runner.

Historical evaluator implementations remain available under their versioned
module names. Update this module only when deliberately promoting a reviewed
criteria version.
"""

try:
    from .oracles_phase5_2 import evaluate_semantics
except ImportError:  # Direct runner execution adds benchmark/ to sys.path.
    from oracles_phase5_2 import evaluate_semantics

VERSION = "phase5.2"

__all__ = ["VERSION", "evaluate_semantics"]
