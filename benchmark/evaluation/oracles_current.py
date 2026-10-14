"""Canonical source-derived semantic evaluator for the regression runner."""

from .oracles_phase5_2 import evaluate_semantics

VERSION = "phase5.2"

__all__ = ["VERSION", "evaluate_semantics"]
