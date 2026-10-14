"""Tests for semantic preconditions behind expression metamorphic comparisons."""

from benchmark.runners.metamorphic import empty_list_len_equivalence_preconditions


def test_list_truthiness_and_builtin_len_zero_have_proven_preconditions():
    original = """def run(values):
    selected = [value for value in values]
    if not selected:
        return 0
    return 1
"""
    variant = original.replace("if not selected:", "if len(selected) == 0:")
    valid, reason, variable = empty_list_len_equivalence_preconditions(original, variant)
    assert valid and not reason and variable == "selected"


def test_equivalence_precondition_rejects_rebound_builtin_len():
    original = """def run(values):
    selected = [value for value in values]
    if not selected:
        return 0
    return 1
"""
    variant = original.replace("if not selected:", "if len(selected) == 0:")
    variant = "len = custom_length\n" + variant
    valid, reason, _ = empty_list_len_equivalence_preconditions(original, variant)
    assert not valid and "rebound" in reason


def test_equivalence_precondition_rejects_unknown_object_and_different_predicate():
    original = """def run(value):
    if not value:
        return 0
    return 1
"""
    variant = original.replace("if not value:", "if len(value) == 0:")
    valid, _, _ = empty_list_len_equivalence_preconditions(original, variant)
    assert not valid
