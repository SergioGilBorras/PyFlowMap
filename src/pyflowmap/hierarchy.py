"""Compact, source-traceable activity phase outlines for dense functions."""

import ast
from collections import Counter

from .analysis import NOISE, call_name
from .diagrams.labeling import describe_unresolved
from .models import FlowGraph
from .project import Symbol


def _calls(statements: list[ast.stmt]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            return

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node):
            return

        def visit_Lambda(self, node):
            return

        def visit_Call(self, node):
            expression = call_name(node)
            if expression.split(".")[-1] not in NOISE:
                found.append({"expression": expression, "location": str(node.lineno)})
            self.generic_visit(node)

    visitor = Visitor()
    for statement in statements:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        visitor.visit(statement)
    return sorted(found, key=lambda item: int(item["location"]))


def _definitely_abrupt(statements: list[ast.stmt]) -> bool:
    """Whether every path through this statement list ends abruptly."""
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        if (isinstance(statement, ast.If) and statement.orelse
                and _definitely_abrupt(statement.body)
                and _definitely_abrupt(statement.orelse)):
            return True
    return False


def _phase_label(calls: list[dict[str, str]], language: str, *, conditional: bool) -> str:
    if not calls:
        if language == "es":
            return "Procesar rama condicional" if conditional else "Procesar fase"
        return "Process conditional branch" if conditional else "Process phase"
    ordered_calls = sorted(calls, key=lambda item: (
        "." not in item["expression"], int(item["location"])))
    actions = [describe_unresolved(item["expression"].split(".")[-1], language)
               for item in ordered_calls]
    if len(actions) == 1:
        return ("Invocar " if language == "es" else "Call ") + actions[0]
    preview = "; ".join(actions[:3])
    if len(actions) > 3:
        preview += "; …"
    prefix = ("Fase condicional" if conditional else "Fase") if language == "es" else (
        "Conditional phase" if conditional else "Phase")
    return f"{prefix}: {preview}"


def build_hierarchical_outline(symbol: Symbol, language: str = "en") -> FlowGraph:
    """Summarize one function as phases, retaining its top-level decisions.

    Each branch body is a traceable subprocess summary. Nested decisions and
    control effects are counted in metadata and remain available in the linked
    full activity graph; the outline never claims that summarized calls run in
    a particular order.
    """
    if language not in ("en", "es"):
        raise ValueError("language must be 'en' or 'es'")
    graph = FlowGraph(entry=symbol.id)
    start = graph.add("", "initial")
    end = graph.add("", "final")
    yes, no = (("Sí", "No") if language == "es" else ("Yes", "No"))
    cursor: list[tuple[str, str]] = [(start, "")]
    nested_decisions = 0

    def emit_phase(statements: list[ast.stmt], incoming: list[tuple[str, str]],
                   *, conditional: bool) -> str:
        calls = _calls(statements)
        phase = graph.add(_phase_label(calls, language, conditional=conditional), "activity",
                          symbol.id, f"{symbol.path}:{statements[0].lineno}")
        source_references = [
            {"symbol": symbol.id, "location": f"{symbol.path}:{item['location']}",
             "expression": item["expression"]}
            for item in calls
        ]
        statements_with_decisions = [
            item for statement in statements for item in ast.walk(statement)
            if isinstance(item, ast.If)
        ]
        for source, edge_label in incoming:
            graph.connect(source, phase, edge_label)
        graph.nodes[phase].label_metadata.update({
            "phase_summary": True,
            "phase_kind": "conditional-branch" if conditional else "statement-block",
            "source_symbol": symbol.id,
            "source_locations": list(dict.fromkeys(
                f"{symbol.path}:{node.lineno}" for statement in statements
                for node in ast.walk(statement) if hasattr(node, "lineno"))),
            "source_references": source_references,
            "summarized_call_count": len(calls),
            "call_resolution": "not-resolved-in-outline",
            "summarized_nested_decisions": len(statements_with_decisions),
            "summarized_control_effects": dict(Counter(
                type(node).__name__ for statement in statements for node in ast.walk(statement)
                if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue)))),
            "detail_symbol": symbol.id,
        })
        return phase

    statements = [statement for statement in symbol.node.body
                  if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    index = 0
    while index < len(statements):
        statement = statements[index]
        if isinstance(statement, ast.If):
            question = (f"¿{ast.unparse(statement.test)}?" if language == "es"
                        else f"{ast.unparse(statement.test)}?")
            decision = graph.add(question, "decision", symbol.id,
                                 f"{symbol.path}:{statement.lineno}")
            for source, edge_label in cursor:
                graph.connect(source, decision, edge_label)
            graph.nodes[decision].label_metadata.update({
                "predicate": ast.unparse(statement.test),
                "source_symbol": symbol.id,
                "hierarchical_outline": True,
            })
            yes_phase = emit_phase(statement.body, [(decision, yes)], conditional=True)
            if not _definitely_abrupt(statement.body):
                cursor = [(yes_phase, "")]
            else:
                cursor = []
            if any(isinstance(node, (ast.Return, ast.Raise))
                   for item in statement.body for node in ast.walk(item)):
                graph.connect(yes_phase, end, "may return or raise")
            if statement.orelse:
                no_phase = emit_phase(statement.orelse, [(decision, no)], conditional=True)
                if not _definitely_abrupt(statement.orelse):
                    cursor.append((no_phase, ""))
                if any(isinstance(node, (ast.Return, ast.Raise))
                       for item in statement.orelse for node in ast.walk(item)):
                    graph.connect(no_phase, end, "may return or raise")
            else:
                cursor.append((decision, no))
            nested_decisions += sum(
                isinstance(node, ast.If)
                for branch in (statement.body, statement.orelse)
                for item in branch for node in ast.walk(item)
            )
            if any(isinstance(node, (ast.Return, ast.Raise))
                   for branch in (statement.body, statement.orelse)
                   for item in branch for node in ast.walk(item)):
                graph.warnings.append(
                    f"Nested branch exits summarized at {symbol.path}:{statement.lineno}; "
                    "open the detailed subprocess activity for exact paths")
            index += 1
        else:
            block = []
            while index < len(statements) and not isinstance(statements[index], ast.If):
                block.append(statements[index])
                index += 1
            phase = emit_phase(block, cursor, conditional=False)
            abrupt = _definitely_abrupt(block)
            if abrupt:
                graph.connect(phase, end)
                cursor = []
            else:
                cursor = [(phase, "")]

    for source, edge_label in cursor:
        graph.connect(source, end, edge_label)
    graph.warnings.append(
        "Hierarchical activity outline: top-level decisions are retained; phase bodies summarize "
        "nested control flow and link by source locations to the detailed activity graph")
    graph.nodes[end].label_metadata.update({
        "source_symbol": symbol.id,
        "summarized_nested_decisions": nested_decisions,
        "detailed_graph_symbol": symbol.id,
    })
    return graph
