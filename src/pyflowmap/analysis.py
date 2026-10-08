"""Conservative static activity-flow extraction and topology-safe contraction."""

import ast
from collections import Counter

from .diagrams.labeling import describe_symbol, describe_unresolved, words
from .models import Edge, FlowGraph
from .project import ProjectIndex, Symbol

NOISE = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple", "range",
    "enumerate", "zip", "sorted", "sum", "min", "max", "all", "any", "isinstance",
    "getattr", "setattr", "hasattr", "type", "super", "repr", "abs", "round", "id",
    "debug", "info", "warning", "error", "exception", "log", "append", "extend",
    "keys", "values", "items", "strip", "lower", "upper", "format", "join",
}


def display_call(call: ast.Call, target: Symbol | None, language: str = "en") -> str:
    if target:
        return describe_symbol(target, language)
    func = call.func
    if isinstance(func, ast.Name):
        return describe_unresolved(func.id, language)
    if isinstance(func, ast.Attribute):
        return describe_unresolved(func.attr, language)
    return "Dynamic call" if language == "en" else "Llamada dinámica"


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
    def __init__(self, index: ProjectIndex, max_depth: int = 2, language: str = "en"):
        if max_depth < 0 or max_depth > 10:
            raise ValueError("max_depth must be between 0 and 10")
        self.index = index
        self.max_depth = max_depth
        if language not in ("en", "es"):
            raise ValueError("language must be 'en' or 'es'")
        self.language = language
        self.graph: FlowGraph | None = None
        self.total_steps = 0
        self._return_frames: list[list[tuple[str, str]]] = []
        self._exception_tails: list[tuple[str, str]] = []

    def build(self, entry: Symbol) -> FlowGraph:
        self.graph = FlowGraph(entry=entry.id, warnings=list(self.index.warnings))
        self.total_steps = 0
        self._return_frames = [[]]
        self._exception_tails = []
        start = self.graph.add("", "initial")
        tails = self._block(entry.node.body, [(start, "")], entry,
                            self.index.instance_types(entry), (entry.id,))
        if len(self.graph.nodes) == 1:
            tails = self._emit(words(entry.name), tails, entry, entry.node)
            self.graph.warnings.append("No significant calls; represented the entry as one activity")
        returned = self._return_frames.pop()
        # A return from either branch is the same *operation*, not two
        # independent boxes. The branches converge before the activity final.
        if returned:
            result_label = "Devolver resultado" if self.language == "es" else "Return result"
            returned = self._emit(result_label, returned, entry, entry.node, kind="result")
        end = self.graph.add("", "final")
        for source, label in tails + returned + self._exception_tails:
            self.graph.connect(source, end, label)
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
        if target.name in {"from_dict", "to_dict", "validate", "__post_init__"}:
            return False
        significant_calls = {
            (call_name(call), call.lineno)
            for stmt in target.node.body
            for call in ast.walk(stmt)
            if isinstance(call, ast.Call)
            and call_name(call).split(".")[-1] not in NOISE
        }
        return len(significant_calls) >= 2

    def _call(self, call: ast.Call, prior: list[tuple[str, str]], current: Symbol,
              types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        name = call_name(call).split(".")[-1]
        if name in NOISE:
            return prior
        target = self.index.resolve_call(call, current, types)
        if target and target.id not in stack and len(stack) - 1 < self.max_depth and self._inlineable(target):
            self._return_frames.append([])
            end = self._block(target.node.body, prior, target, self.index.instance_types(target),
                              stack + (target.id,))
            return end + self._return_frames.pop()
        return self._emit(display_call(call, target, self.language), prior, current, call,
                          symbol=target)

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
                if isinstance(value, ast.Call) and not (
                    isinstance(stmt, ast.Return) and self.index.class_id(
                        call_name(value).split(".")[-1], current.module)
                ):
                    prior = self._call(value, prior, current, types, stack)
                if isinstance(stmt, ast.Return):
                    # An inlined callee returns to its caller, not the overall
                    # activity final. Each call has its own return frame.
                    self._return_frames[-1].extend(prior)
                    return []
                if isinstance(stmt, ast.Raise):
                    failure = self._emit("Raise exception", prior, current, stmt)
                    self._exception_tails.extend(failure)
                    return []
            elif isinstance(stmt, ast.Match):
                # Explicit conservative fallback: don't fabricate edges for match/case.
                assert self.graph is not None
                self.graph.warnings.append(f"match/case collapsed at {current.path}:{stmt.lineno}")
                prior = self._emit("Match cases (collapsed)", prior, current, stmt)
        return prior

    def _branch(self, stmt: ast.If, prior: list[tuple[str, str]], current: Symbol,
                types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        condition, yes_text, no_text = self._describe_condition(stmt.test)
        decision = self._emit(condition, prior, current, stmt, kind="decision")[0][0]
        yes = self._block(stmt.body, [(decision, yes_text)], current, types.copy(), stack)
        no = (self._block(stmt.orelse, [(decision, no_text)], current, types.copy(), stack)
              if stmt.orelse else [(decision, no_text)])
        return yes + no

    def _describe_condition(self, test: ast.AST) -> tuple[str, str, str]:
        # Render the predicate's actual truth value. Do not rewrite a domain
        # status to an inverted business question (which reversed Yes/No).
        true_label, false_label = (("Sí", "No") if self.language == "es"
                                   else ("Yes", "No"))
        if isinstance(test, ast.Compare) and len(test.ops) == len(test.comparators) == 1:
            op = test.ops[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                left = expr_text(test.left, 32)
                right = expr_text(test.comparators[0], 32)
                if self.language == "es":
                    predicate = f"{left} {'es' if isinstance(op, ast.Eq) else 'es distinto de'} {right}"
                    return f"¿{predicate}?", true_label, false_label
                relation = "equal to" if isinstance(op, ast.Eq) else "different from"
                return f"Is {left} {relation} {right}?", true_label, false_label
        condition = expr_text(test)
        if self.language == "es":
            return f"¿{condition}?", true_label, false_label
        return f"{condition}?", true_label, false_label

    def _loop(self, stmt: ast.For | ast.AsyncFor | ast.While,
              prior: list[tuple[str, str]], current: Symbol, types: dict[str, str],
              stack: tuple[str, ...]) -> list[tuple[str, str]]:
        condition = f"More items in {expr_text(stmt.iter, 30)}?" if isinstance(stmt, (ast.For, ast.AsyncFor)) else f"{expr_text(stmt.test)}?"
        identifier = self._emit(condition, prior, current, stmt, kind="decision")[0][0]
        yes, no = (("Sí", "No") if self.language == "es" else ("Yes", "No"))
        tail = self._block(stmt.body, [(identifier, yes)], current, types.copy(), stack)
        assert self.graph is not None
        for end, _ in tail:
            self.graph.connect(end, identifier, "Next")
        if stmt.orelse:
            self.graph.warnings.append(f"loop-else approximated at {current.path}:{stmt.lineno}")
        return [(identifier, no)]

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
