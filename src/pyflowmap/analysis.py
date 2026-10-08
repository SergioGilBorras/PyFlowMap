"""Conservative static activity-flow extraction and topology-safe contraction."""

import ast
import re
from collections import Counter

from .models import Edge, FlowGraph
from .project import ProjectIndex, Symbol

NOISE = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple", "range",
    "enumerate", "zip", "sorted", "sum", "min", "max", "all", "any", "isinstance",
    "getattr", "setattr", "hasattr", "type", "super", "repr", "abs", "round", "id",
    "debug", "info", "warning", "error", "exception", "log", "append", "extend",
    "keys", "values", "items", "strip", "lower", "upper", "format", "join",
}


def words(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return re.sub(r"[_\s]+", " ", value).strip().capitalize()


def display_call(call: ast.Call, target: Symbol | None) -> str:
    if target:
        return f"{words(target.name)} ({target.owner})" if target.owner else words(target.name)
    func = call.func
    if isinstance(func, ast.Name):
        return words(func.id)
    if isinstance(func, ast.Attribute):
        return words(func.attr)
    return "Dynamic call"


def call_name(call: ast.Call) -> str:
    try:
        return ast.unparse(call.func)
    except (TypeError, ValueError):
        return "unknown"


def expr_text(expr: ast.AST, limit: int = 54) -> str:
    try:
        text = ast.unparse(expr)
    except (TypeError, ValueError):
        return "condition"
    if isinstance(expr, ast.Call):
        text = display_call(expr, None)
    return (text[:limit - 1] + "…") if len(text) > limit else text


class FlowBuilder:
    def __init__(self, index: ProjectIndex, max_depth: int = 2):
        if max_depth < 0 or max_depth > 10:
            raise ValueError("max_depth must be between 0 and 10")
        self.index = index
        self.max_depth = max_depth
        self.graph: FlowGraph | None = None
        self.total_steps = 0

    def build(self, entry: Symbol) -> FlowGraph:
        self.graph = FlowGraph(entry=entry.id, warnings=list(self.index.warnings))
        self.total_steps = 0
        self._block(entry.node.body, [], entry, {}, (entry.id,))
        if not self.graph.nodes:
            self._emit(words(entry.name), [], entry, entry.node)
            self.graph.warnings.append("No significant calls; represented the entry as one activity")
        return self.graph

    def _emit(self, label: str, prior: list[tuple[str, str]], current: Symbol,
              node: ast.AST, kind: str = "activity", symbol: Symbol | None = None) -> list[tuple[str, str]]:
        assert self.graph is not None
        self.total_steps += 1
        if self.total_steps > 1000:
            raise ValueError("Flow is too large (>1000 steps). Choose a narrower entry point")
        origin = symbol or current
        location = f"{origin.path}:{getattr(node, 'lineno', origin.node.lineno)}"
        key = self.graph.add(label, kind, origin.id, location)
        for source, edge_label in prior:
            self.graph.connect(source, key, edge_label)
        return [(key, "")]

    def _infer_constructor(self, call: ast.Call, current: Symbol) -> str | None:
        if not isinstance(call.func, ast.Name):
            return None
        return self.index.class_id(call.func.id, current.module)

    def _inlineable(self, target: Symbol) -> bool:
        """Only inline orchestrators, not ordinary implementation-detail methods."""
        significant_calls = 0
        for stmt in target.node.body:
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.Try)):
                return True
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Return)):
                expression = getattr(stmt, "value", None)
                if isinstance(expression, ast.Call) and call_name(expression).split(".")[-1] not in NOISE:
                    significant_calls += 1
        return significant_calls >= 2

    def _call(self, call: ast.Call, prior: list[tuple[str, str]], current: Symbol,
              types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        name = call_name(call).split(".")[-1]
        if name in NOISE:
            return prior
        target = self.index.resolve_call(call, current, types)
        if target and target.id not in stack and len(stack) - 1 < self.max_depth and self._inlineable(target):
            return self._block(target.node.body, prior, target, {}, stack + (target.id,))
        return self._emit(display_call(call, target), prior, current, call, symbol=target)

    def _block(self, statements: list[ast.stmt], prior: list[tuple[str, str]],
               current: Symbol, types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, ast.If):
                prior = self._branch(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                prior = self._loop(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                prior = self._block(stmt.body, prior, current, types, stack)
            elif isinstance(stmt, ast.Try):
                prior = self._try(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                value = stmt.value
                if isinstance(value, ast.Call):
                    ctor = self._infer_constructor(value, current)
                    names = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    if ctor:
                        for item in names:
                            if isinstance(item, ast.Name):
                                types[item.id] = ctor
                        continue
                    prior = self._call(value, prior, current, types, stack)
            elif isinstance(stmt, (ast.Expr, ast.Return, ast.Raise, ast.AugAssign)):
                value = getattr(stmt, "value", None)
                if isinstance(value, ast.Call):
                    prior = self._call(value, prior, current, types, stack)
                if isinstance(stmt, ast.Return):
                    if value is not None and not isinstance(value, ast.Call):
                        prior = self._emit("Return result", prior, current, stmt)
                    # Return terminates only the current branch, never jumps into the next activity.
                    return []
                if isinstance(stmt, ast.Raise):
                    self._emit("Raise exception", prior, current, stmt)
                    return []
            elif isinstance(stmt, ast.Match):
                # Explicit conservative fallback: don't fabricate edges for match/case.
                assert self.graph is not None
                self.graph.warnings.append(f"match/case collapsed at {current.path}:{stmt.lineno}")
                prior = self._emit("Match cases (collapsed)", prior, current, stmt)
        return prior

    def _branch(self, stmt: ast.If, prior: list[tuple[str, str]], current: Symbol,
                types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        decision = self._emit(f"{expr_text(stmt.test)}?", prior, current, stmt, kind="decision")[0][0]
        yes = self._block(stmt.body, [(decision, "Yes")], current, types.copy(), stack)
        no = self._block(stmt.orelse, [(decision, "No")], current, types.copy(), stack) if stmt.orelse else [(decision, "No")]
        return yes + no

    def _loop(self, stmt: ast.For | ast.AsyncFor | ast.While,
              prior: list[tuple[str, str]], current: Symbol, types: dict[str, str],
              stack: tuple[str, ...]) -> list[tuple[str, str]]:
        condition = f"More items in {expr_text(stmt.iter, 30)}?" if isinstance(stmt, (ast.For, ast.AsyncFor)) else f"{expr_text(stmt.test)}?"
        identifier = self._emit(condition, prior, current, stmt, kind="decision")[0][0]
        tail = self._block(stmt.body, [(identifier, "Yes")], current, types.copy(), stack)
        assert self.graph is not None
        for end, _ in tail:
            self.graph.connect(end, identifier, "Next")
        if stmt.orelse:
            self.graph.warnings.append(f"loop-else approximated at {current.path}:{stmt.lineno}")
        return [(identifier, "No")]

    def _try(self, stmt: ast.Try, prior: list[tuple[str, str]], current: Symbol,
             types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        if stmt.handlers:
            assert self.graph is not None
            self.graph.warnings.append(f"try/except is approximated at {current.path}:{stmt.lineno}")
            decision = self._emit("Try succeeds?", prior, current, stmt, kind="decision")[0][0]
            success = self._block(stmt.body + stmt.orelse, [(decision, "Yes")], current, types.copy(), stack)
            failures = []
            for handler in stmt.handlers:
                failures += self._block(handler.body, [(decision, "No")], current, types.copy(), stack)
            prior = success + failures
        else:
            prior = self._block(stmt.body + stmt.orelse, prior, current, types, stack)
        return self._block(stmt.finalbody, prior, current, types, stack)


def simplify(graph: FlowGraph, max_nodes: int = 8) -> FlowGraph:
    """Contract only linear activity edges. Never delete a decision or change branch topology."""
    if not 2 <= max_nodes <= 100:
        raise ValueError("max_nodes must be between 2 and 100")
    while len(graph.nodes) > max_nodes:
        incoming = Counter(e.target for e in graph.edges)
        outgoing = Counter(e.source for e in graph.edges)
        choice = None
        for edge in graph.edges:
            a, b = graph.nodes[edge.source], graph.nodes[edge.target]
            if (a.kind == b.kind == "activity" and outgoing[a.id] == 1
                    and incoming[b.id] == 1 and not edge.label):
                choice = (a, b)
                break
        if not choice:
            graph.warnings.append(
                f"Kept {len(graph.nodes)} nodes (budget {max_nodes}) to preserve branch topology"
            )
            break
        first, second = choice
        labels = first.label.split(" → ") + second.label.split(" → ")
        first.label = " → ".join(labels[:3]) if len(labels) <= 3 else f"{labels[0]} → … → {labels[-1]}"
        first.symbols = list(dict.fromkeys(first.symbols + second.symbols))
        first.locations = list(dict.fromkeys(first.locations + second.locations))
        graph.edges = [Edge(first.id if e.source == second.id else e.source,
                            first.id if e.target == second.id else e.target, e.label)
                       for e in graph.edges if not (e.source == first.id and e.target == second.id)]
        del graph.nodes[second.id]
    return graph
