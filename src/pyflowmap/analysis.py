"""Conservative static activity-flow extraction and topology-safe contraction."""

import ast
from collections import Counter

from .diagrams.labeling import describe_symbol, describe_unresolved, words
from .models import Edge, FlowGraph
from .project import ProjectIndex, Symbol

# ``super()`` is a dispatch construct rather than an independently meaningful
# operation when used as a method receiver. Other calls are kept visible: even
# familiar builtins and methods can invoke user-defined protocols or have side
# effects, so suppressing them would silently assert purity.
NOISE = {"super"}
MAX_FLOW_STEPS = 5000


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


def _json_literal(value):
    """Preserve literal values in metadata without leaking non-JSON Python objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, complex):
        return {"type": "complex", "real": value.real, "imag": value.imag}
    if isinstance(value, (tuple, list, set, frozenset)):
        items = [_json_literal(item) for item in value]
        return {"type": type(value).__name__, "items": items} if isinstance(
            value, (set, frozenset)) else items
    if isinstance(value, dict):
        return {str(key): _json_literal(item) for key, item in value.items()}
    return {"type": type(value).__name__, "repr": repr(value)}


def _is_literal(expression: ast.AST) -> bool:
    try:
        ast.literal_eval(expression)
        return True
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False


def _statement_call_sites(statement: ast.stmt, *, defer_annotations: bool = False
                          ) -> list[dict[str, str]]:
    """List calls evaluated while a declaration executes, excluding deferred bodies."""
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            calls.append(node)
            self.generic_visit(node)

        def _visit_definition_expressions(self, node):
            expressions = list(node.decorator_list)
            args = node.args
            expressions.extend(args.defaults)
            expressions.extend(item for item in args.kw_defaults if item is not None)
            if not defer_annotations:
                expressions.extend(arg.annotation for arg in
                                   [*args.posonlyargs, *args.args, *args.kwonlyargs]
                                   if arg.annotation is not None)
                if args.vararg and args.vararg.annotation:
                    expressions.append(args.vararg.annotation)
                if args.kwarg and args.kwarg.annotation:
                    expressions.append(args.kwarg.annotation)
                if node.returns is not None:
                    expressions.append(node.returns)
            for expression in expressions:
                self.visit(expression)

        def visit_FunctionDef(self, node):
            self._visit_definition_expressions(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            for expression in [*node.args.defaults,
                               *(item for item in node.args.kw_defaults if item is not None)]:
                self.visit(expression)

    visitor = Visitor()
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        visitor._visit_definition_expressions(statement)
    else:
        # A class body executes during class creation. Nested function bodies are
        # deferred by the visitor, while their decorators/defaults still execute.
        visitor.visit(statement)
    return [
        {"expression": ast.unparse(call), "line": str(call.lineno)}
        for call in sorted(calls, key=lambda item: (item.lineno, item.col_offset))
    ]


def contained_call_sites(symbol: Symbol, index: ProjectIndex,
                         types: dict[str, str]) -> list[dict[str, str]]:
    """Summarize project-local calls when expanding a callee is bounded."""
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is symbol.node:
                self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            return

        def visit_Call(self, node):
            calls.append(node)
            self.generic_visit(node)

    Visitor().visit(symbol.node)
    output = []
    for call in sorted(calls, key=lambda node: (node.lineno, node.col_offset)):
        if call_name(call).split(".")[-1] in NOISE:
            continue
        target = index.resolve_call(call, symbol, types)
        candidates = [target] if target else index.possible_call_targets(call, symbol, types)
        candidates = [candidate for candidate in candidates if candidate is not None]
        if not candidates:
            continue
        output.append({
            "expression": call_name(call),
            "location": f"{symbol.path}:{call.lineno}",
            "targets": [candidate.id for candidate in candidates],
            "label": display_call(call, candidates[0]),
            "resolution": "possible" if target is None or (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Attribute)
                and isinstance(call.func.value.value, ast.Name)
                and call.func.value.value.id == "self") else "resolved",
        })
    return output


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
        self._loop_frames: list[dict[str, list[tuple[str, str]]]] = []
        self._branch_depth = 0
        self._expanded_symbols: set[str] = set()
        self._pending_cleanup_depth = 0

    def build(self, entry: Symbol) -> FlowGraph:
        self.graph = FlowGraph(entry=entry.id, warnings=list(self.index.warnings))
        self.total_steps = 0
        self._return_frames = [[]]
        self._exception_tails = []
        self._loop_frames = []
        self._branch_depth = 0
        self._expanded_symbols = {entry.id}
        self._pending_cleanup_depth = 0
        start = self.graph.add("", "initial")
        if entry.node.decorator_list:
            self.graph.nodes[start].label_metadata.update({
                "entry_decorators": [ast.unparse(item) for item in entry.node.decorator_list],
                "decorator_locations": [f"{entry.path}:{item.lineno}"
                                        for item in entry.node.decorator_list],
                "decorator_may_replace_callable": True,
            })
            self.graph.warnings.append(
                f"Entry callable may be transformed by decorators at {entry.path}:"
                f"{entry.node.lineno}; wrapper behavior is not executed statically")
        tails = self._block(entry.node.body, [(start, "")], entry,
                            self.index.instance_types(entry), (entry.id,))
        if len(self.graph.nodes) == 1:
            tails = self._emit(words(entry.name), tails, entry, entry.node)
            self.graph.warnings.append("No significant calls; represented the entry as one activity")
        returned = self._return_frames.pop()
        direct_results = [(source, label) for source, label in returned
                          if self.graph.nodes[source].kind == "result"]
        shared_returns = [(source, label) for source, label in returned
                          if self.graph.nodes[source].kind != "result"]
        for source, edge_label in shared_returns:
            pending = self.graph.nodes[source].label_metadata
            expression = pending.get("return_expression", "unknown")
            result_label = (f"Devolver {expression}" if self.language == "es"
                            else f"Return {expression}")
            result = self._emit(result_label, [(source, edge_label)], entry,
                                entry.node, kind="result")[0][0]
            metadata = self.graph.nodes[result].label_metadata
            metadata.update({key: pending[key] for key in
                             ("control_transfer", "return_expression", "return_value",
                              "return_value_known") if key in pending})
            if pending.get("pending_control_transfer") == "return":
                metadata["control_transfer"] = "return"
            if pending.get("return_source_locations"):
                metadata["return_source_locations"] = pending["return_source_locations"]
                self.graph.nodes[result].locations = list(dict.fromkeys(
                    pending["return_source_locations"] + self.graph.nodes[result].locations))
            metadata["significant_control_flow"] = True
            direct_results.append((result, ""))
        end = self.graph.add("", "final")
        for source, label in tails + direct_results:
            self.graph.connect(source, end, label)
        for source, label in self._exception_tails:
            origin = self.graph.nodes[source]
            if origin.label_metadata.get("control_transfer") == "raise":
                origin.label_metadata["exception_route"] = "propagated"
                # The source activity already says what is raised and carries
                # exception_route=propagated. An extra repeated edge label at a
                # shared final node obscures all exits in dense diagrams.
                self.graph.connect(source, end, label)
                continue
            if origin.label_metadata.get("exception_route") == "propagated":
                self.graph.connect(source, end, label)
                continue
            propagated = self.graph.add(
                "Propagate exception" if self.language == "en" else "Propagar excepción",
                "activity", origin.symbols[0] if origin.symbols else entry.id,
                origin.locations[0] if origin.locations else f"{entry.path}:{entry.node.lineno}")
            self.graph.connect(source, propagated, label or self._may_raise())
            self.graph.nodes[propagated].label_metadata.update({
                "exception_route": "propagated",
                "control_transfer": "raise",
                "exception_origin_node": source,
                "exception_origin": origin.label_metadata.get("exception_origin", "unknown"),
                "exception_type_expression": origin.label_metadata.get("exception_type_expression"),
                "significant_control_flow": True,
            })
            self.graph.connect(propagated, end)
        return self.graph

    def _may_raise(self) -> str:
        return "Puede lanzar" if self.language == "es" else "May raise"

    def _aggregate_runtime_exceptions(
            self, pending: list[tuple[str, str]], current: Symbol) -> list[tuple[str, str]]:
        """Join unknown exception alternatives before cleanup, retaining their origins."""
        assert self.graph is not None
        eligible = [item for item in pending
                    if self.graph.nodes[item[0]].label_metadata.get("exception_route") == "may_raise"
                    and self.graph.nodes[item[0]].label_metadata.get("exception_dispatch")
                    == "runtime-dependent"]
        if len(eligible) < 2:
            return pending
        first = self.graph.nodes[eligible[0][0]]
        label = ("Excepción posible durante el bloque" if self.language == "es"
                 else "Possible exception during block")
        joined = self.graph.add(label, "activity", current.id,
                                first.locations[0] if first.locations else None)
        source_records = []
        locations = []
        for source_id, edge_label in eligible:
            source = self.graph.nodes[source_id]
            self.graph.connect(source_id, joined, edge_label or self._may_raise())
            source_records.append({
                "node_id": source_id,
                "call_expression": source.label_metadata.get("call_expression"),
                "async_event": source.label_metadata.get("async_event"),
                "exception_origin": source.label_metadata.get("exception_origin"),
                "locations": list(source.locations),
            })
            locations.extend(source.locations)
        self.graph.nodes[joined].locations = list(dict.fromkeys(locations))
        self.graph.nodes[joined].label_metadata.update({
            "control_transfer": "raise",
            "exception_route": "raised",
            "exception_origin": "aggregated_unknown",
            "exception_dispatch": "runtime-dependent",
            "exception_sources": source_records,
            "significant_control_flow": True,
        })
        location = (first.locations[0] if first.locations
                    else f"{current.path}:{current.node.lineno}")
        warning = (f"Unknown exception alternatives grouped before context cleanup at "
                   f"{location}; source nodes are retained in metadata")
        if warning not in self.graph.warnings:
            self.graph.warnings.append(warning)
        eligible_ids = {source for source, _ in eligible}
        return [item for item in pending if item[0] not in eligible_ids] + [(joined, "")]

    @staticmethod
    def _callee_body_info(target: Symbol, status: str,
                          contained: list[dict] | None = None,
                          reason: str | None = None) -> dict:
        start = getattr(target.node, "lineno", 1)
        stop = getattr(target.node, "end_lineno", start)
        return {
            "status": status,
            "symbol": target.id,
            "source_locations": [f"{target.path}:{start}-{stop}"],
            "contained_call_sites": contained or [],
            "limits": [reason] if reason else [],
        }

    def _emit(self, label: str, prior: list[tuple[str, str]], current: Symbol,
              node: ast.AST, kind: str = "activity", symbol: Symbol | None = None) -> list[tuple[str, str]]:
        assert self.graph is not None
        self.total_steps += 1
        if self.total_steps > MAX_FLOW_STEPS:
            raise ValueError(f"Flow is too large (>{MAX_FLOW_STEPS} steps). Choose a narrower entry point")
        origin = symbol or current
        # A resolved call activity names its target symbol but belongs to the
        # caller's source location. Never combine a target path with caller lines.
        location = f"{current.path}:{getattr(node, 'lineno', current.node.lineno)}"
        key = self.graph.add(label, kind, origin.id, location)
        for source, edge_label in prior:
            self.graph.connect(source, key, edge_label)
        return [(key, "")]

    def _summarize_statement(self, stmt: ast.stmt,
                             prior: list[tuple[str, str]], current: Symbol,
                             *, label: str, scope: str,
                             calls: list[dict[str, str]] | None = None,
                             possible_exception: bool = False) -> list[tuple[str, str]]:
        """Keep an explicit, source-linked activity for effects not expanded here."""
        assert self.graph is not None
        summary = self._emit(label, prior, current, stmt)
        node = self.graph.nodes[summary[0][0]]
        node.label_metadata.update({
            "statement_kind": type(stmt).__name__,
            "statement_summary": "summarized",
            "summary_scope": scope,
            "source_location": f"{current.path}:{stmt.lineno}",
            "contained_call_sites": calls or [],
            "significant_state_change": True,
        })
        if possible_exception:
            node.label_metadata.update({
                "possible_exception": True,
                "exception_route": "may_raise",
                "exception_dispatch": "runtime-dependent",
                "significant_control_flow": True,
            })
            self._exception_tails.append((node.id, self._may_raise()))
        return summary

    def _scope_warning(self, message: str) -> None:
        assert self.graph is not None
        if message not in self.graph.warnings:
            self.graph.warnings.append(message)

    def _future_annotations(self, current: Symbol) -> bool:
        module = self.index.modules.get(current.module)
        if module is None:
            return False
        return any(
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
            and any(alias.name == "annotations" for alias in statement.names)
            for statement in module.tree.body
        )

    def _infer_constructor(self, call: ast.Call, current: Symbol) -> str | None:
        if not isinstance(call.func, ast.Name):
            return None
        return self.index.class_id(call.func.id, current.module)

    def _inlineable(self, target: Symbol) -> bool:
        """Only inline orchestrators, not ordinary implementation-detail methods."""
        if target.name in {"from_dict", "to_dict", "validate", "__post_init__"}:
            return False
        if self._deferred_body_reason(target):
            # Calling a generator creates a lazy iterator; calling an async
            # function creates a coroutine. Their bodies do not execute at the
            # call expression itself.
            return False
        significant_calls = {
            (call_name(call), call.lineno)
            for stmt in target.node.body
            for call in ast.walk(stmt)
            if isinstance(call, ast.Call)
            and call_name(call).split(".")[-1] not in NOISE
        }
        return len(significant_calls) >= 2

    @staticmethod
    def _deferred_body_reason(target: Symbol) -> str | None:
        if isinstance(target.node, ast.AsyncFunctionDef):
            return "Coroutine/async-generator body is deferred until it is awaited or iterated"

        class YieldVisitor(ast.NodeVisitor):
            found = False

            def visit_Yield(self, node):
                self.found = True

            visit_YieldFrom = visit_Yield

            def visit_FunctionDef(self, node):
                if node is target.node:
                    self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Lambda(self, node):
                return

        visitor = YieldVisitor()
        visitor.visit(target.node)
        if visitor.found:
            return "Generator body is deferred until iteration or explicit resumption"
        return None

    def _call(self, call: ast.Call, prior: list[tuple[str, str]], current: Symbol,
              types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        name = call_name(call).split(".")[-1]
        if name in NOISE:
            return prior
        target = self.index.resolve_call(call, current, types)
        possible = self.index.possible_call_targets(call, current, types) if target is None else []
        dynamic_receiver = (isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Attribute)
                            and isinstance(call.func.value.value, ast.Name)
                            and call.func.value.value.id == "self"
                            and "self." + call.func.value.attr in types)
        current_scope = current.id.split(":", 1)[1]
        nested_scope = bool(target and (target.owner == current_scope
                                        or current_scope.startswith(target.owner + ".")))
        decorated = bool(target and target.node.decorator_list)
        if (target and not dynamic_receiver and target.id not in stack
                and target.id not in self._expanded_symbols
                and len(stack) - 1 < self.max_depth and self._inlineable(target)
                and not decorated):
            invocation = self._emit(display_call(call, target, self.language), prior,
                                    current, call)
            assert self.graph is not None
            self.graph.nodes[invocation[0][0]].label_metadata.update({
                "call_resolution": "resolved",
                "call_expression": call_name(call),
                "caller_symbol": current.id,
                "resolved_target": target.id,
                "possible_targets": [target.id],
                "significant_call": True,
                "callee_body": self._callee_body_info(
                    target, "expanded", reason="Static body statements are expanded at this call site"),
                "possible_exception": True,
                "exception_route": "may_raise",
                "exception_dispatch": "runtime-dependent",
            })
            self._exception_tails.append((invocation[0][0], self._may_raise()))
            self._return_frames.append([])
            target_types = types.copy() if nested_scope else self.index.instance_types(target)
            self._expanded_symbols.add(target.id)
            caller_loops = self._loop_frames
            self._loop_frames = []
            try:
                end = self._block(target.node.body, invocation, target, target_types,
                                  stack + (target.id,))
            finally:
                self._loop_frames = caller_loops
            return end + self._return_frames.pop()
        if target:
            label = display_call(call, target, self.language)
            resolution = "possible" if dynamic_receiver or decorated else "resolved"
        else:
            source_call = call_name(call)
            args = ast.unparse(call.args[0]) if call.args else ""
            label = (f"Call {source_call}({args})" if self.language == "en"
                     else f"Invocar {source_call}({args})")
            resolution = "possible" if possible else "unresolved"
        tails = self._emit(label, prior, current, call, symbol=target)
        assert self.graph is not None
        node = self.graph.nodes[tails[0][0]]
        contained = contained_call_sites(target, self.index, types) if target else []
        if contained:
            collaborators = [item for item in contained
                             if item["expression"].startswith("self.")]
            cross_module = [item for item in contained
                            if any(candidate.split(":", 1)[0] != target.module
                                   for candidate in item["targets"])]
            visible_calls = collaborators or cross_module or contained
            labels = list(dict.fromkeys(
                f"{item['label']} ({item['location'].rsplit(':', 1)[-1]})"
                for item in visible_calls))
            heading = "Possible internal calls: " if self.language == "en" else "Llamadas internas posibles: "
            shown_labels = labels[:6]
            remaining = max(0, len(labels) - len(shown_labels))
            node.label += "\n" + heading + "; ".join(shown_labels)
            if remaining:
                node.label += (f"; +{remaining} more in graph metadata" if self.language == "en"
                               else f"; +{remaining} más en los metadatos del grafo")
            node.label_metadata.update({
                "contained_calls_displayed": len(shown_labels),
                "contained_calls_omitted_from_label": remaining,
            })
            warning = (f"Subprocess {target.id} is resolved; its activity label displays possible internal calls and "
                       "metadata retains their targets and source locations. Their branch conditions and execution "
                       "order are summarized and depend on runtime data")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
            if remaining:
                self._scope_warning(
                    f"Subprocess {target.id} label displays {len(shown_labels)} of {len(labels)} possible internal calls; "
                    "the rest remain available with source locations in graph metadata")
        node.label_metadata.update({
            "call_resolution": resolution,
            "call_resolution_explanation": (
                f"The expression is shown; project-local candidates are possible but the runtime receiver may select another target: "
                f"{', '.join(candidate.id for candidate in possible) or target.id if target else 'none'}"
                if resolution == "possible" else
                ("The expression is shown, but no project-local callable target was resolved; "
                 "its implementation and effects are unavailable statically"
                 if resolution == "unresolved" else
                 f"The AST/index resolves this call to {target.id}; runtime effects and exceptions remain possible.")),
            "call_expression": call_name(call),
            "caller_symbol": current.id,
            "resolved_target": target.id if target and resolution == "resolved" else None,
            "possible_targets": ([target.id] if target and resolution == "possible"
                                 else [candidate.id for candidate in possible]),
            "significant_call": True,
            "subprocess_calls": contained,
            "possible_exception": True,
            "exception_route": "may_raise",
            "exception_dispatch": "runtime-dependent",
        })
        self._exception_tails.append((tails[0][0], self._may_raise()))
        if target:
            if decorated or dynamic_receiver:
                body_status = "referenced"
                body_limit = ("Decorator or dynamic receiver may change runtime dispatch; indexed body is only a candidate"
                              if decorated or dynamic_receiver else "")
            else:
                body_status = "summarized"
                body_limit = ("Contained calls are a syntactic inventory; branch order and runtime behavior are not expanded"
                              if contained else
                              "Target body is not expanded at the configured depth or expansion boundary")
            node.label_metadata["callee_body"] = self._callee_body_info(
                target, body_status, contained, body_limit)
        if decorated:
            node.label_metadata["decorators"] = [ast.unparse(item) for item in target.node.decorator_list]
            node.label_metadata["decorator_locations"] = [
                f"{target.path}:{item.lineno}" for item in target.node.decorator_list]
            node.label_metadata["decorator_may_replace_callable"] = True
            warning = (f"Decorated call behavior may differ from the indexed function body at "
                       f"{current.path}:{call.lineno}; wrapper dispatch is not executed")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
        deferred_reason = self._deferred_body_reason(target) if target else None
        if deferred_reason:
            node.label_metadata["callee_body"]["execution_policy"] = "deferred"
            node.label_metadata["callee_body"]["limits"].append(deferred_reason)
            warning = (f"Call at {current.path}:{call.lineno} creates a deferred generator/coroutine; "
                       "its body is not expanded as immediate call execution")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
        return tails

    def _expression(self, expr: ast.AST | None, prior: list[tuple[str, str]],
                    current: Symbol, types: dict[str, str],
                    stack: tuple[str, ...]) -> list[tuple[str, str]]:
        """Emit significant calls in expression evaluation order and retain ternary branches."""
        if expr is None:
            return prior
        if isinstance(expr, ast.NamedExpr):
            prior = self._expression(expr.value, prior, current, types, stack)
            target = ast.unparse(expr.target)
            label = (f"Assign expression target {target}" if self.language == "en"
                     else f"Asignar destino de expresión {target}")
            prior = self._emit(label, prior, current, expr)
            assert self.graph is not None
            self.graph.nodes[prior[0][0]].label_metadata.update({
                "significant_state_change": True,
                "assignment": ast.unparse(expr),
                "named_expression": True,
            })
            return prior
        if isinstance(expr, (ast.Yield, ast.YieldFrom)):
            delegated = isinstance(expr, ast.YieldFrom)
            value = expr.value
            prior = self._expression(value, prior, current, types, stack)
            label = (("Delegar iteración de generador" if delegated else "Ceder valor del generador")
                     if self.language == "es" else
                     ("Delegate to subiterator" if delegated else "Yield value"))
            yielded = self._emit(label, prior, current, expr)[0][0]
            assert self.graph is not None
            event = "yield_from" if delegated else "yield"
            self.graph.nodes[yielded].label_metadata.update({
                "generator_event": event,
                "generator_expression": ast.unparse(value) if value is not None else None,
                "suspension": True,
                "resume_value_becomes_expression_result": delegated,
                "possible_close": True,
                "significant_control_flow": True,
            })
            resumed = self.graph.add(
                "Reanudar generador" if self.language == "es" else "Resume generator", "activity")
            self.graph.connect(yielded, resumed, "Reanudar" if self.language == "es" else "Resume")
            self.graph.nodes[resumed].locations = list(self.graph.nodes[yielded].locations)
            self.graph.nodes[resumed].label_metadata.update({
                "generator_event": "resume", "resumes": yielded,
                "significant_control_flow": True,
            })
            closed = self.graph.add(
                "Inyectar GeneratorExit al cerrar" if self.language == "es"
                else "Inject GeneratorExit on close", "activity")
            self.graph.connect(yielded, closed, "Cerrar" if self.language == "es" else "Close")
            self.graph.nodes[closed].locations = list(self.graph.nodes[yielded].locations)
            asynchronous = isinstance(current.node, ast.AsyncFunctionDef)
            self.graph.nodes[closed].label_metadata.update({
                "generator_event": "close",
                "generator_close_kind": "async" if asynchronous else "sync",
                "close_operation": "aclose" if asynchronous else "close",
                "exception_type": "GeneratorExit",
                "exception_route": "injected",
                "exception_origin": "generator_close",
                "control_transfer": "raise",
                "possible_exception_types": ["GeneratorExit"],
                "delegation_close_forwarding_possible": delegated,
                "generator_cleanup_expanded": "routed through enclosing try/except/finally",
                "significant_control_flow": True,
            })
            # Closing a suspended generator injects GeneratorExit at the yield
            # point. Let the enclosing try machinery route it through handlers
            # and finally suites just like any other pending exception.
            self._exception_tails.append((closed, ""))
            warning = (f"Generator {event} at {current.path}:{expr.lineno} is represented; "
                       "close injects GeneratorExit and follows represented lexical cleanup, but "
                       "send/throw inputs, iteration count, dynamic handlers and cleanup outcomes "
                       "cannot be determined statically; yielding again during close may raise RuntimeError")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
            return [(resumed, "")]
        if isinstance(expr, ast.Await):
            prior = self._expression(expr.value, prior, current, types, stack)
            label = "Esperar resultado asíncrono" if self.language == "es" else "Await result"
            awaited = self._emit(label, prior, current, expr)[0][0]
            assert self.graph is not None
            self.graph.nodes[awaited].label_metadata.update({
                "async_event": "await", "suspension": True,
                "awaited_expression": ast.unparse(expr.value), "possible_exception": True,
                "exception_route": "may_raise",
                "exception_dispatch": "runtime-dependent",
            })
            resumed = self._emit("Reanudar tras await" if self.language == "es"
                                 else "Resume after await", [(awaited, "Resume")],
                                 current, expr)[0][0]
            self.graph.nodes[resumed].label_metadata.update({
                "async_event": "await_resume", "resumes": awaited,
            })
            self._exception_tails.append((awaited, self._may_raise()))
            warning = (f"Await at {current.path}:{expr.lineno} represents suspension and a possible resume; "
                       "the awaitable result, scheduling order and exception type depend on runtime behavior")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
            return [ (resumed, "") ]
        if isinstance(expr, ast.IfExp):
            yes_paths, no_paths = self._condition_paths(expr.test, prior, current, types, stack)
            return (self._expression(expr.body, yes_paths, current, types.copy(), stack)
                    + self._expression(expr.orelse, no_paths, current, types.copy(), stack))
        if isinstance(expr, ast.BoolOp):
            tails = prior
            exits: list[tuple[str, str]] = []
            is_and = isinstance(expr.op, ast.And)
            for operand in expr.values[:-1]:
                tails = self._expression(operand, tails, current, types, stack)
                truth = f"Is {expr_text(operand)} truthy?"
                decision = self._emit(truth, tails, current, operand, kind="decision")[0][0]
                yes, no = (("Yes", "No") if self.language == "en" else ("Sí", "No"))
                exits.append((decision, no if is_and else yes))
                tails = [(decision, yes if is_and else no)]
            return exits + self._expression(expr.values[-1], tails, current, types, stack)
        if isinstance(expr, ast.Call):
            prior = self._expression(expr.func, prior, current, types, stack)
            for arg in expr.args:
                prior = self._expression(arg, prior, current, types, stack)
            for keyword in expr.keywords:
                prior = self._expression(keyword.value, prior, current, types, stack)
            return self._call(expr, prior, current, types, stack)
        if isinstance(expr, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            is_generator = isinstance(expr, ast.GeneratorExp)
            generators = expr.generators
            immediate = [ast.unparse(generators[0].iter)] if generators else []
            # Python evaluates the outermost iterable when the comprehension is
            # created. For generator expressions, the remaining work is deferred;
            # eager comprehensions summarize their per-item work below.
            if immediate:
                prior = self._expression(generators[0].iter, prior, current, types, stack)
            kind = ("generator expression" if isinstance(expr, ast.GeneratorExp)
                    else "comprehension")
            label = (f"Evaluate {kind}" if self.language == "en" else
                     "Evaluar expresión generadora" if isinstance(expr, ast.GeneratorExp)
                     else "Evaluar comprensión")
            tails = self._emit(label, prior, current, expr)
            assert self.graph is not None
            call_nodes = sorted(
                (item for item in ast.walk(expr) if isinstance(item, ast.Call)),
                key=lambda item: (item.lineno, item.col_offset),
            )
            immediate_call_ids = ({id(item) for item in ast.walk(generators[0].iter)
                                   if isinstance(item, ast.Call)} if generators else set())
            contained_calls = [{
                "expression": call_name(item),
                "location": f"{current.path}:{item.lineno}",
                "evaluation_phase": ("immediate" if id(item) in immediate_call_ids else
                                     "deferred" if is_generator else "per_iteration"),
                "role": ("filter" if any(item in ast.walk(condition)
                                          for generator in generators for condition in generator.ifs)
                         else "iterable" if any(item in ast.walk(generator.iter)
                                                for generator in generators)
                         else "result_expression"),
            } for item in call_nodes]
            call_groups = {}
            for role in ("filter", "iterable", "result_expression"):
                expressions = list(dict.fromkeys(
                    item["expression"] for item in contained_calls
                    if item["evaluation_phase"] != "immediate" and item["role"] == role))
                if expressions:
                    call_groups[role] = expressions
            shown_groups = {role: expressions[:4]
                            for role, expressions in call_groups.items()}
            hidden_call_count = sum(len(expressions) - len(shown_groups[role])
                                    for role, expressions in call_groups.items())
            if shown_groups:
                group_labels = [f"{role} [{', '.join(expressions)}]"
                                for role, expressions in shown_groups.items()]
                call_heading = ("Deferred per-item calls by role: " if is_generator
                                else "Per-item calls by role: ")
                if self.language == "es":
                    call_heading = ("Llamadas diferidas por elemento y tipo: " if is_generator
                                    else "Llamadas por elemento y tipo: ")
                self.graph.nodes[tails[0][0]].label += "\n" + call_heading + "; ".join(group_labels)
                if hidden_call_count:
                    self.graph.nodes[tails[0][0]].label += (
                        f"; +{hidden_call_count} more in graph metadata" if self.language == "en"
                        else f"; +{hidden_call_count} más en los metadatos del grafo")
            self.graph.nodes[tails[0][0]].label_metadata.update({
                "expression_summary": True,
                "significant_control_flow": True,
                "expression": ast.unparse(expr),
                "comprehension_kind": ("generator" if is_generator else
                                        "dictionary" if isinstance(expr, ast.DictComp) else
                                        "set" if isinstance(expr, ast.SetComp) else "list"),
                "evaluation_policy": "lazy" if is_generator else "eager",
                "body_execution": "deferred until iteration" if is_generator else "during construction",
                "immediate_expressions": immediate,
                "deferred_expressions": ([ast.unparse(expr.elt)] if is_generator else []),
                "iterables": [ast.unparse(item.iter) for item in generators],
                "targets": [ast.unparse(item.target) for item in generators],
                "filters": [ast.unparse(condition) for item in generators
                            for condition in item.ifs],
                "result_expressions": ([ast.unparse(expr.key), ast.unparse(expr.value)]
                                       if isinstance(expr, ast.DictComp) else
                                       [ast.unparse(expr.elt)]),
                "contained_call_expressions": list(dict.fromkeys(
                    call_name(item) for item in call_nodes
                )),
                "contained_calls": contained_calls,
                "contained_calls_displayed": sum(len(items) for items in shown_groups.values()),
                "contained_calls_omitted_from_label": hidden_call_count,
                "deferred_exception_behavior": ("iteration_time" if is_generator else None),
                "possible_exception": not is_generator,
                "exception_route": "may_raise" if not is_generator else None,
                "exception_dispatch": "runtime-dependent" if not is_generator else None,
                "iteration_order": [
                    {"target": ast.unparse(generator.target),
                     "iterable": ast.unparse(generator.iter),
                     "filters": [ast.unparse(condition) for condition in generator.ifs]}
                    for generator in generators
                ],
            })
            warning = ("Comprehension expression, filters and known per-item call names are retained in the visible, "
                       "source-located summary; the outer iterable is evaluated separately, while iteration count "
                       "and per-item short-circuit outcomes depend on runtime data")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
            if is_generator:
                deferred_warning = (
                    f"Generator-expression body exceptions are deferred until iteration at "
                    f"{current.path}:{expr.lineno}; the iteration site is outside this expression"
                )
                if deferred_warning not in self.graph.warnings:
                    self.graph.warnings.append(deferred_warning)
            else:
                self._exception_tails.append((tails[0][0], self._may_raise()))
            return tails
        if isinstance(expr, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            return prior
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr):
                prior = self._expression(child, prior, current, types, stack)
        return prior

    def _block(self, statements: list[ast.stmt], prior: list[tuple[str, str]],
               current: Symbol, types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # The body is deferred until a call. Preserve the definition-time
                # operation and any expressions evaluated for decorators/defaults.
                calls = _statement_call_sites(
                    stmt, defer_annotations=self._future_annotations(current))
                label = (f"Define function {stmt.name} (body deferred)"
                         if self.language == "en" else
                         f"Definir función {stmt.name} (cuerpo diferido)")
                prior = self._summarize_statement(
                    stmt, prior, current, label=label,
                    scope="function body is deferred; decorator/default/annotation expressions are listed, not expanded",
                    calls=calls,
                    possible_exception=bool(calls),
                )
                if calls:
                    summary_node = self.graph.nodes[prior[0][0]]
                    preview = ", ".join(item["expression"] for item in calls[:4])
                    remainder = len(calls) - min(4, len(calls))
                    summary_node.label += f"\nDefinition-time call syntax: {preview}"
                    if remainder:
                        summary_node.label += f"; +{remainder} more in graph metadata"
                    summary_node.label_metadata["definition_calls_displayed"] = min(4, len(calls))
                    summary_node.label_metadata["definition_calls_omitted_from_label"] = remainder
                    self._scope_warning(
                        f"Function definition at {current.path}:{stmt.lineno} is summarized; "
                        "its body is deferred and definition-time calls are listed with source lines, "
                        "but decorator and annotation evaluation details are not expanded")
                continue
            elif isinstance(stmt, ast.ClassDef):
                calls = _statement_call_sites(
                    stmt, defer_annotations=self._future_annotations(current))
                label = (f"Define class {stmt.name} (class body summarized)"
                         if self.language == "en" else
                         f"Definir clase {stmt.name} (cuerpo resumido)")
                prior = self._summarize_statement(
                    stmt, prior, current, label=label,
                    scope="class body executes during definition; its internal branches are summarized",
                    calls=calls, possible_exception=True,
                )
                if calls:
                    summary_node = self.graph.nodes[prior[0][0]]
                    preview = ", ".join(item["expression"] for item in calls[:4])
                    remainder = len(calls) - min(4, len(calls))
                    summary_node.label += f"\nClass-definition call syntax: {preview}"
                    if remainder:
                        summary_node.label += f"; +{remainder} more in graph metadata"
                    summary_node.label_metadata["definition_calls_displayed"] = min(4, len(calls))
                    summary_node.label_metadata["definition_calls_omitted_from_label"] = remainder
                self._scope_warning(
                    f"Class definition at {current.path}:{stmt.lineno} is summarized; "
                    "base/decorator evaluation, class-body paths and metaclass effects may execute, "
                    "but their runtime order and outcomes are not expanded")
                continue
            elif isinstance(stmt, (ast.Pass, ast.Global, ast.Nonlocal)):
                # These statements create no independent runtime action in the body.
                continue
            if isinstance(stmt, ast.If):
                prior = self._branch(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                prior = self._loop(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                prior = self._with(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.Try, ast.TryStar)):
                prior = self._try(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                value = stmt.value
                ctor = self._infer_constructor(value, current) if isinstance(value, ast.Call) else None
                prior = self._expression(value, prior, current, types, stack)
                names = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                # Target expressions can call functions or evaluate indexes.
                # Python evaluates the RHS before resolving assignment targets.
                for target in names:
                    if not isinstance(target, ast.Name):
                        prior = self._expression(target, prior, current, types, stack)
                if ctor:
                    for item in names:
                        if isinstance(item, ast.Name):
                            types[item.id] = ctor
                unpacking = (isinstance(stmt, ast.Assign) and any(
                    isinstance(target, (ast.Tuple, ast.List)) for target in stmt.targets))
                if value is not None or isinstance(stmt, (ast.AnnAssign, ast.NamedExpr)):
                    targets = ", ".join(ast.unparse(item) for item in names)
                    label = (f"Unpack and assign {targets}" if unpacking else f"Set {targets}")
                    if self.language == "es":
                        label = (f"Desempaquetar y asignar {targets}" if unpacking
                                 else f"Asignar {targets}")
                    if isinstance(stmt, ast.AnnAssign) and value is None:
                        label = (f"Annotate {targets}" if self.language == "en"
                                 else f"Anotar {targets}")
                    prior = self._emit(label, prior, current, stmt)
                    assert self.graph is not None
                    assignment_node = self.graph.nodes[prior[0][0]]
                    assignment_node.label_metadata.update({
                        "significant_state_change": True,
                        "assignment": ast.unparse(stmt),
                    })
                    if isinstance(stmt, ast.AnnAssign) and value is None:
                        assignment_node.label_metadata.update({
                            "annotation_only": True,
                            "binding_effect": "annotation-only; target is not assigned",
                        })
                    if unpacking:
                        assignment_node.label_metadata.update({
                            "unpacking_assignment": True,
                            "possible_exception": True,
                            "possible_exception_types": [
                                "TypeError", "ValueError", "iterator-raised"],
                            "exception_route": "may_raise",
                            "exception_origin": "assignment_unpacking",
                            "exception_dispatch": "runtime-dependent",
                            "significant_control_flow": True,
                        })
                        self._exception_tails.append((prior[0][0], self._may_raise()))
            elif isinstance(stmt, ast.Assert):
                assert self.graph is not None
                enabled = self._emit(
                    "Are assertions enabled (__debug__)?" if self.language == "en"
                    else "¿Están activas las aserciones (__debug__)?",
                    prior, current, stmt, kind="decision")[0][0]
                self.graph.nodes[enabled].label_metadata.update({
                    "assertion": True, "optimization_sensitive": True,
                    "optimization_mode": "unknown", "significant_control_flow": True,
                    "message_evaluation": "failure path only",
                })
                success, failure = self._condition_paths(
                    stmt.test, [(enabled, "Yes" if self.language == "en" else "Sí")],
                    current, types, stack)
                if stmt.msg is not None:
                    failure = self._expression(stmt.msg, failure, current, types, stack)
                exception = self._emit(
                    "Raise AssertionError" if self.language == "en"
                    else "Lanzar AssertionError", failure, current, stmt)[0][0]
                self.graph.nodes[exception].label_metadata.update({
                    "exception_type": "AssertionError", "control_transfer": "raise",
                    "significant_control_flow": True,
                })
                self._exception_tails.append((exception, ""))
                # With -O/-OO, Python removes the assert including test and message evaluation.
                # The disabled branch must bypass the test; use a distinct bypass activity.
                bypass = self._emit("Assertions removed by optimization" if self.language == "en"
                                    else "Aserciones eliminadas al optimizar",
                                    [(enabled, "No")], current, stmt)[0][0]
                self.graph.nodes[bypass].label_metadata.update({
                    "assertion_optimized_away": True, "significant_control_flow": True,
                })
                self.graph.warnings.append(
                    f"Assert behavior depends on Python optimization mode at {current.path}:{stmt.lineno}")
                prior = success + [(bypass, "")]
            elif isinstance(stmt, (ast.Expr, ast.Return, ast.AugAssign)):
                value = getattr(stmt, "value", None)
                if isinstance(stmt, ast.AugAssign):
                    # Augmented assignment resolves/loads its target before the
                    # RHS and evaluates the target only once.
                    prior = self._expression(stmt.target, prior, current, types, stack)
                    prior = self._expression(value, prior, current, types, stack)
                is_result_constructor = (isinstance(stmt, ast.Return) and isinstance(value, ast.Call)
                                         and self.index.class_id(call_name(value).split(".")[-1],
                                                                 current.module))
                if not isinstance(stmt, ast.AugAssign) and not is_result_constructor:
                    prior = self._expression(value, prior, current, types, stack)
                if isinstance(stmt, ast.Return):
                    # An inlined callee returns to its caller, not the overall
                    # activity final. Each call has its own return frame.
                    expression = ast.unparse(value) if value is not None else "None"
                    pending_cleanup = self._pending_cleanup_depth > 0
                    label = ((f"Evaluate return value {expression}" if self.language == "en"
                              else f"Evaluar valor devuelto {expression}") if pending_cleanup else
                             (f"Return {expression}" if self.language == "en"
                              else f"Devolver {expression}"))
                    returned = self._emit(label, prior, current, stmt,
                                          kind="activity" if pending_cleanup else "result")
                    assert self.graph is not None
                    metadata = self.graph.nodes[returned[0][0]].label_metadata
                    metadata.update({
                        ("pending_control_transfer" if pending_cleanup else "control_transfer"): "return",
                        "return_expression": expression,
                        "return_source_locations": [f"{current.path}:{stmt.lineno}"],
                        "return_value_known": value is None or _is_literal(value),
                        "significant_control_flow": True,
                    })
                    if value is None or _is_literal(value):
                        metadata["return_value"] = _json_literal(
                            None if value is None else ast.literal_eval(value))
                    self._return_frames[-1].extend(returned)
                    return []
                if isinstance(stmt, ast.AugAssign):
                    label = f"Update {ast.unparse(stmt.target)}" if self.language == "en" else f"Actualizar {ast.unparse(stmt.target)}"
                    prior = self._emit(label, prior, current, stmt)
                    assert self.graph is not None
                    self.graph.nodes[prior[0][0]].label_metadata.update({
                        "significant_state_change": True,
                        "assignment": ast.unparse(stmt),
                    })
            elif isinstance(stmt, (ast.Break, ast.Continue)):
                if self._loop_frames:
                    outcome = "break" if isinstance(stmt, ast.Break) else "continue"
                    if self.language == "es":
                        label = "Salir del bucle" if outcome == "break" else "Continuar con la siguiente iteración"
                    else:
                        label = "Break loop" if outcome == "break" else "Continue to next iteration"
                    transfer = self._emit(label, prior, current, stmt)[0][0]
                    assert self.graph is not None
                    self.graph.nodes[transfer].label_metadata.update({
                        "control_transfer": outcome,
                        "significant_control_flow": True,
                    })
                    self._loop_frames[-1][outcome].append((transfer, ""))
                    return []
                assert self.graph is not None
                self.graph.warnings.append(
                    f"{type(stmt).__name__.lower()} outside modeled loop at {current.path}:{stmt.lineno}"
                )
                return []
            elif isinstance(stmt, ast.Raise):
                prior = self._expression(stmt.exc, prior, current, types, stack)
                if stmt.cause:
                    prior = self._expression(stmt.cause, prior, current, types, stack)
                exception = expr_text(stmt.exc, 64) if stmt.exc else "current exception"
                label = (f"Raise {exception}" if self.language == "en"
                         else f"Lanzar {exception}")
                failure = self._emit(label, prior, current, stmt)
                assert self.graph is not None
                self.graph.nodes[failure[0][0]].label_metadata.update({
                    "significant_control_flow": True,
                    "control_transfer": "raise",
                    "exception_route": "raised",
                    "exception_expression": ast.unparse(stmt.exc) if stmt.exc else None,
                })
                self._exception_tails.extend(failure)
                return []
            elif isinstance(stmt, ast.Match):
                prior = self._match(stmt, prior, current, types, stack)
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                try:
                    expression = ast.unparse(stmt)
                except (TypeError, ValueError):
                    expression = type(stmt).__name__
                label = (f"Import {expression}" if self.language == "en"
                         else f"Importar {expression}")
                prior = self._summarize_statement(
                    stmt, prior, current, label=label,
                    scope="module initialization and import hooks are not executed or expanded",
                    possible_exception=True,
                )
                self._scope_warning(
                    f"Import at {current.path}:{stmt.lineno} is represented; module initialization, "
                    "import hooks and the resolved module implementation are runtime-dependent")
            elif isinstance(stmt, ast.Delete):
                for target in stmt.targets:
                    prior = self._expression(target, prior, current, types, stack)
                try:
                    expression = ast.unparse(stmt)
                except (TypeError, ValueError):
                    expression = "delete target"
                label = (f"Delete target: {expression[4:]}" if self.language == "en"
                         else f"Eliminar destino: {expression[4:]}")
                prior = self._summarize_statement(
                    stmt, prior, current, label=label,
                    scope="target expression calls are represented; target validity and protocol effects are runtime-dependent",
                    possible_exception=True,
                )
                self._scope_warning(
                    f"Delete at {current.path}:{stmt.lineno} is represented; whether the target exists "
                    "and whether its protocol raises cannot be determined statically")
            else:
                try:
                    expression = ast.unparse(stmt)
                except (TypeError, ValueError):
                    expression = type(stmt).__name__
                source = expression[:180] + ("…" if len(expression) > 180 else "")
                label = (f"Summarize {type(stmt).__name__}: {source}" if self.language == "en"
                         else f"Resumir {type(stmt).__name__}: {source}")
                contained_calls = _statement_call_sites(stmt)
                for call_site in contained_calls:
                    call_site["evaluation"] = "unknown"
                prior = self._summarize_statement(
                    stmt, prior, current, label=label,
                    scope="statement retained as an opaque activity; its internal effects are not modeled",
                    calls=contained_calls, possible_exception=True,
                )
                self._scope_warning(
                    f"Unsupported statement {type(stmt).__name__} at {current.path}:{stmt.lineno} "
                    "is retained as a summarized activity; its internal control flow and effects are unknown")
        return prior

    def _with(self, stmt: ast.With | ast.AsyncWith,
              prior: list[tuple[str, str]], current: Symbol,
              types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        """Model context-manager entry, body, and reverse-order exits conservatively."""
        asynchronous = isinstance(stmt, ast.AsyncWith)
        is_es = self.language == "es"
        enter_label = "Entrar en gestor de contexto" if is_es else "Enter context manager"
        exit_label = "Salir del gestor de contexto" if is_es else "Exit context manager"

        def nested(item_index: int, incoming: list[tuple[str, str]]) -> tuple[list, ...]:
            if item_index == len(stmt.items):
                self._pending_cleanup_depth += 1
                try:
                    return self._block_outcomes(stmt.body, incoming, current, types.copy(), stack)
                finally:
                    self._pending_cleanup_depth -= 1

            item = stmt.items[item_index]
            exception_start = len(self._exception_tails)
            evaluated = self._expression(item.context_expr, incoming, current, types, stack)
            expression_raises = self._exception_tails[exception_start:]
            del self._exception_tails[exception_start:]
            enter = self._emit(enter_label, evaluated, current, item.context_expr)[0][0]
            assert self.graph is not None
            self.graph.nodes[enter].label_metadata.update({
                "context_manager_phase": "enter",
                "context_expression": ast.unparse(item.context_expr),
                "async": asynchronous,
                "context_manager_method": "__aenter__" if asynchronous else "__enter__",
                "possible_exception": True,
                "exception_route": "may_raise",
                "exception_origin": "context_enter",
                "may_suspend": asynchronous,
                "significant_control_flow": True,
            })
            entered_question = ("Did context-manager entry succeed?" if not is_es
                                else "¿Terminó bien la entrada al gestor?")
            entered_decision = self._emit(entered_question, [(enter, "")], current,
                                          item.context_expr, kind="decision")[0][0]
            yes, no = (("Sí", "No") if is_es else ("Yes", "No"))
            self.graph.nodes[entered_decision].label_metadata.update({
                "context_manager_entry": True,
                "context_expression": ast.unparse(item.context_expr),
                "transfer_outcomes": {yes: "body_entered", no: "entry_exception"},
                "significant_control_flow": True,
            })
            entry_failure = self._emit(
                "Context-manager entry raises" if not is_es else
                "La entrada al gestor lanza una excepción",
                [(entered_decision, no)], current, item.context_expr)[0][0]
            self.graph.nodes[entry_failure].label_metadata.update({
                "control_transfer": "raise",
                "exception_route": "raised",
                "exception_origin": "context_enter",
                "context_expression": ast.unparse(item.context_expr),
                "significant_control_flow": True,
            })
            if item.optional_vars is not None:
                bind = self._emit(
                    (f"Asignar {ast.unparse(item.optional_vars)}" if is_es
                     else f"Bind {ast.unparse(item.optional_vars)}"),
                    [(entered_decision, yes)], current, item.optional_vars)
                self.graph.nodes[bind[0][0]].label_metadata.update({
                    "context_manager_binding": ast.unparse(item.optional_vars),
                    "significant_state_change": True,
                })
                entered = bind
                binding_failures = []
                if isinstance(item.optional_vars, (ast.Tuple, ast.List,
                                                    ast.Attribute, ast.Subscript)):
                    binding = self.graph.nodes[bind[0][0]]
                    binding.label_metadata.update({
                        "unpacking_assignment": isinstance(item.optional_vars,
                                                            (ast.Tuple, ast.List)),
                        "possible_exception": True,
                        "possible_exception_types": ["TypeError", "ValueError",
                                                     "iterator-raised"],
                        "exception_route": "may_raise",
                        "exception_origin": "context_manager_target_assignment",
                        "exception_dispatch": "runtime-dependent",
                        "significant_control_flow": True,
                    })
                    binding_failures.append((bind[0][0], self._may_raise()))
            else:
                entered = [(entered_decision, yes)]
                binding_failures = []

            normal, returned, raised, broke, continued = nested(item_index + 1, entered)
            # Assignment to a with-target happens after successful entry. If it
            # fails, the newly entered manager still receives its exit call.
            raised.extend(binding_failures)
            raised = self._aggregate_runtime_exceptions(raised, current)
            outputs = [[], [], [], [], []]
            for outcome_index, pending in enumerate((normal, returned, raised, broke, continued)):
                for source, edge_label in pending:
                    if outcome_index == 1:
                        return_node = self.graph.nodes[source]
                        if return_node.label_metadata.get("pending_control_transfer") == "return":
                            return_node.label = (
                                f"Evaluate return value {return_node.label_metadata['return_expression']}"
                                if not is_es else
                                f"Evaluar valor devuelto {return_node.label_metadata['return_expression']}")
                            return_node.kind = "activity"
                    exited = self._emit(exit_label, [(source, edge_label)], current,
                                        item.context_expr)[0][0]
                    exit_node = self.graph.nodes[exited]
                    exit_node.label_metadata.update({
                        "context_manager_phase": "exit",
                        "context_expression": ast.unparse(item.context_expr),
                        "async": asynchronous,
                        "context_manager_method": "__aexit__" if asynchronous else "__exit__",
                        "pending_outcome": ("normal", "return", "raise", "break", "continue")[outcome_index],
                        "possible_exception": True,
                        "exception_route": ("pending_exception" if outcome_index == 2
                                            else "pending_transfer"),
                        "significant_control_flow": True,
                    })
                    exit_failure = self._emit(
                        "Context-manager exit raises" if not is_es else
                        "La salida del gestor lanza una excepción",
                        [(exited, self._may_raise())], current, item.context_expr)[0][0]
                    self.graph.nodes[exit_failure].label_metadata.update({
                        "control_transfer": "raise",
                        "exception_route": "raised",
                        "exception_origin": "context_exit",
                        "overrides_pending_outcome": (
                            "normal", "return", "raise", "break", "continue")[outcome_index],
                        "context_expression": ast.unparse(item.context_expr),
                        "significant_control_flow": True,
                    })
                    outputs[2].append((exit_failure, ""))
                    if outcome_index == 1:
                        origin_metadata = self.graph.nodes[source].label_metadata
                        for key in ("pending_control_transfer", "return_expression", "return_value",
                                    "return_source_locations",
                                    "return_value_known"):
                            if key in origin_metadata:
                                exit_node.label_metadata[key] = origin_metadata[key]
                    if outcome_index == 2:
                        question = ("¿El gestor suprime la excepción?" if is_es
                                    else "Does the context manager suppress the exception?")
                        decision = self._emit(question, [(exited, "")], current,
                                              item.context_expr, kind="decision")[0][0]
                        self.graph.nodes[decision].label_metadata.update({
                            "context_manager_suppression": "unknown",
                            "context_expression": ast.unparse(item.context_expr),
                            "transfer_outcomes": {
                                ("Sí" if is_es else "Yes"): "exception_suppressed",
                                "No": "exception_propagated",
                            },
                        })
                        yes, no = (("Sí", "No") if is_es else ("Yes", "No"))
                        outputs[0].append((decision, yes))
                        outputs[2].append((decision, no))
                    else:
                        if outcome_index == 1 and item_index == 0:
                            expression = self.graph.nodes[source].label_metadata.get(
                                "return_expression", "unknown")
                            completed = self._emit(
                                (f"Return {expression}" if not is_es else f"Devolver {expression}"),
                                [(exited, "")], current, item.context_expr, kind="result")[0][0]
                            self.graph.nodes[completed].locations = list(dict.fromkeys(
                                self.graph.nodes[source].label_metadata.get(
                                    "return_source_locations", self.graph.nodes[source].locations)
                                + self.graph.nodes[source].locations))
                            self.graph.nodes[completed].label_metadata.update({
                                "significant_control_flow": True,
                                "return_after_context_exit": True,
                                "control_transfer": "return",
                                "pending_control_transfer": "return",
                                **{key: self.graph.nodes[source].label_metadata[key]
                                   for key in ("return_expression", "return_value",
                                               "return_source_locations",
                                               "return_value_known")
                                   if key in self.graph.nodes[source].label_metadata},
                            })
                            outputs[outcome_index].append((completed, ""))
                        else:
                            outputs[outcome_index].append((exited, ""))

            # If this manager's enter protocol fails, its own exit is not called.
            outputs[2].append((entry_failure, ""))
            # A later context expression is evaluated after earlier managers have
            # entered. Its exception unwinds those managers, but does not call the
            # exit method of the manager whose expression failed.
            outputs[2].extend(expression_raises)

            warning = (f"Context manager entry, body and exit are represented at "
                       f"{current.path}:{getattr(item.context_expr, 'lineno', stmt.lineno)}; "
                       "possible suppression behavior is dynamic, and whether __exit__/__aexit__ "
                       "suppresses or replaces an exception cannot be determined statically")
            if warning not in self.graph.warnings:
                self.graph.warnings.append(warning)
            return tuple(outputs)

        normal, returned, raised, broke, continued = nested(0, prior)
        self._return_frames[-1].extend(returned)
        self._exception_tails.extend(raised)
        if self._loop_frames:
            self._loop_frames[-1]["break"].extend(broke)
            self._loop_frames[-1]["continue"].extend(continued)
        return normal

    def _branch(self, stmt: ast.If, prior: list[tuple[str, str]], current: Symbol,
                types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        yes_paths, no_paths = self._condition_paths(stmt.test, prior, current, types, stack)
        self._branch_depth += 1
        try:
            yes = self._block(stmt.body, yes_paths, current, types.copy(), stack)
            no = (self._block(stmt.orelse, no_paths, current, types.copy(), stack)
                  if stmt.orelse else no_paths)
        finally:
            self._branch_depth -= 1
        return yes + no

    def _condition_paths(self, test: ast.AST, prior: list[tuple[str, str]],
                         current: Symbol, types: dict[str, str], stack: tuple[str, ...]
                         ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Return truthy/falsy exits while evaluating every operand exactly once."""
        if isinstance(test, ast.BoolOp):
            is_and = isinstance(test.op, ast.And)
            continuing = prior
            short_circuit: list[tuple[str, str]] = []
            for operand in test.values:
                yes_paths, no_paths = self._condition_paths(
                    operand, continuing, current, types.copy(), stack)
                if is_and:
                    short_circuit.extend(no_paths)
                    continuing = yes_paths
                else:
                    short_circuit.extend(yes_paths)
                    continuing = no_paths
            return (continuing, short_circuit) if is_and else (short_circuit, continuing)

        evaluated = self._expression(test, prior, current, types, stack)
        condition, yes_label, no_label = self._describe_condition(test)
        decision = self._emit(condition, evaluated, current, test, kind="decision")[0][0]
        assert self.graph is not None
        self.graph.nodes[decision].label_metadata["source_expression"] = ast.unparse(test)
        return [(decision, yes_label)], [(decision, no_label)]

    @staticmethod
    def _match_pattern_is_irrefutable(pattern: ast.pattern) -> bool:
        """Return whether a pattern accepts every subject value."""
        if isinstance(pattern, ast.MatchAs):
            return pattern.pattern is None or FlowBuilder._match_pattern_is_irrefutable(
                pattern.pattern)
        if isinstance(pattern, ast.MatchOr):
            return any(FlowBuilder._match_pattern_is_irrefutable(item)
                       for item in pattern.patterns)
        return False

    @staticmethod
    def _match_pattern_captures(pattern: ast.pattern) -> list[str]:
        captures: list[str] = []
        for node in ast.walk(pattern):
            if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                captures.append(node.name)
            elif isinstance(node, ast.MatchMapping) and node.rest:
                captures.append(node.rest)
        return list(dict.fromkeys(captures))

    def _match(self, stmt: ast.Match, prior: list[tuple[str, str]], current: Symbol,
               types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        """Model ordered structural pattern selection without evaluating patterns."""
        assert self.graph is not None
        is_es = self.language == "es"
        evaluated = self._expression(stmt.subject, prior, current, types, stack)
        subject_label = "Evaluar sujeto de match" if is_es else "Evaluate match subject"
        subject = self._emit(subject_label, evaluated, current, stmt.subject)[0][0]
        self.graph.nodes[subject].label_metadata.update({
            "match_subject": ast.unparse(stmt.subject),
            "significant_control_flow": True,
            "evaluation_count": 1,
        })
        next_case = [(subject, "")]
        exits: list[tuple[str, str]] = []
        yes_label, no_label = (("S\u00ed", "No") if is_es else ("Yes", "No"))
        for index, case in enumerate(stmt.cases):
            pattern = case.pattern
            try:
                pattern_text = ast.unparse(pattern)
            except (TypeError, ValueError):
                pattern_text = type(pattern).__name__
            irrefutable = self._match_pattern_is_irrefutable(pattern)
            label = (f"Does pattern {pattern_text} match?" if not is_es
                     else f"\u00bfCoincide el patr\u00f3n {pattern_text}?")
            selection = self._emit(label, next_case, current, pattern, kind="decision")[0][0]
            selection_node = self.graph.nodes[selection]
            selection_node.label_metadata.update({
                "match_case_index": index,
                "match_pattern": pattern_text,
                "pattern_kind": type(pattern).__name__,
                "pattern_irrefutable": irrefutable,
                "pattern_alternatives": ([ast.unparse(item) for item in pattern.patterns]
                                          if isinstance(pattern, ast.MatchOr) else []),
                "significant_control_flow": True,
            })
            selected = [(selection, yes_label)]
            next_case = [] if irrefutable else [(selection, no_label)]
            if not irrefutable:
                self.graph.warnings.append(
                    f"Pattern matching is data-dependent at {current.path}:{pattern.lineno}; "
                    "both match and no-match paths are represented"
                )
            captures = self._match_pattern_captures(pattern)
            if captures:
                binding_label = ("Bind pattern captures: " if not is_es
                                 else "Asignar capturas del patr\u00f3n: ") + ", ".join(captures)
                selected = self._emit(binding_label, selected, current, pattern)
                self.graph.nodes[selected[0][0]].label_metadata.update({
                    "pattern_captures": captures,
                    "pattern_capture_case_index": index,
                    "significant_state_change": True,
                })

            if case.guard is not None:
                before_guard = set(self.graph.nodes)
                selected, guard_failed = self._condition_paths(
                    case.guard, selected, current, types.copy(), stack)
                for node_id in set(self.graph.nodes) - before_guard:
                    node = self.graph.nodes[node_id]
                    if node.kind == "decision":
                        node.label_metadata["match_guard_case_index"] = index
                next_case.extend(guard_failed)
                self.graph.warnings.append(
                    f"Match guard at {current.path}:{case.guard.lineno} is represented after pattern captures; "
                    "a true guard enters this case body, a false guard proceeds to the next case, "
                    "and the outcome depends on runtime data")

            normal, returned, raised, broke, continued = self._block_outcomes(
                case.body, selected, current, types.copy(), stack)
            exits.extend(normal)
            self._return_frames[-1].extend(returned)
            self._exception_tails.extend(raised)
            if self._loop_frames:
                self._loop_frames[-1]["break"].extend(broke)
                self._loop_frames[-1]["continue"].extend(continued)
            elif broke or continued:
                self.graph.warnings.append(
                    f"Loop control in match case has no enclosing loop at "
                    f"{current.path}:{pattern.lineno}"
                )
            if irrefutable and case.guard is None:
                break
        exits.extend(next_case)
        return exits

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
        is_for = isinstance(stmt, (ast.For, ast.AsyncFor))
        is_es = self.language == "es"
        yes_label, no_label = (("S\u00ed", "No") if is_es else ("Yes", "No"))
        if is_for:
            # The iterable is evaluated once; the iterator decision repeats.
            prior = self._expression(stmt.iter, prior, current, types, stack)
            condition = (f"\u00bfQuedan elementos en {expr_text(stmt.iter, 30)}?" if is_es
                         else f"More items in {expr_text(stmt.iter, 30)}?")
            identifier = self._emit(condition, prior, current, stmt, kind="decision")[0][0]
            assert self.graph is not None
            self.graph.nodes[identifier].label_metadata.update({
                "loop_kind": "async-for" if isinstance(stmt, ast.AsyncFor) else "for",
                "loop_target": ast.unparse(stmt.target),
                "possible_exception": True,
                "exception_route": "may_raise",
                "exception_origin": "async_iterator" if isinstance(stmt, ast.AsyncFor) else "iterator",
                "exception_dispatch": "runtime-dependent",
            })
            self._exception_tails.append((identifier, self._may_raise()))
            iterator_warning = (
                f"Iterator advancement and normal exhaustion are separate outcomes at {current.path}:{stmt.lineno}; "
                "an exception is possible, but its type and the number of iterations cannot be determined statically"
            )
            if iterator_warning not in self.graph.warnings:
                self.graph.warnings.append(iterator_warning)
            bind_label = (f"Asignar objetivo {ast.unparse(stmt.target)}" if is_es
                          else f"Bind loop target {ast.unparse(stmt.target)}")
            iteration = self._emit(bind_label, [(identifier, yes_label)], current,
                                   stmt.target)[0][0]
            self.graph.nodes[iteration].label_metadata.update({
                "loop_target": ast.unparse(stmt.target),
                "significant_state_change": True,
            })
            if isinstance(stmt.target, (ast.Tuple, ast.List)):
                self.graph.nodes[iteration].label_metadata.update({
                    "unpacking_assignment": True,
                    "possible_exception": True,
                    "possible_exception_types": ["TypeError", "ValueError", "iterator-raised"],
                    "exception_route": "may_raise",
                    "exception_origin": "loop_target_unpacking",
                    "exception_dispatch": "runtime-dependent",
                    "significant_control_flow": True,
                })
                self._exception_tails.append((iteration, self._may_raise()))
            body_entry = [(iteration, "")]
            exhausted = [(identifier, no_label)]
        else:
            header_label = "Evaluate while condition" if not is_es else "Evaluar condición del while"
            identifier = self._emit(header_label, prior, current, stmt.test)[0][0]
            assert self.graph is not None
            self.graph.nodes[identifier].label_metadata["loop_kind"] = "while"
            body_entry, exhausted = self._condition_paths(
                stmt.test, [(identifier, "")], current, types, stack)

        self._branch_depth += 1
        frame = {"break": [], "continue": []}
        self._loop_frames.append(frame)
        try:
            tail = self._block(stmt.body, body_entry, current, types.copy(), stack)
        finally:
            self._branch_depth -= 1
            self._loop_frames.pop()
        assert self.graph is not None
        for end, label in tail + frame["continue"]:
            if identifier:
                self.graph.connect(end, identifier, label or "Next")
        if stmt.orelse:
            # Exhaustion / a false while condition enters else; break bypasses it.
            self._branch_depth += 1
            try:
                exhausted = self._block(stmt.orelse, exhausted, current, types.copy(), stack)
            finally:
                self._branch_depth -= 1
        return [*exhausted, *frame["break"]]

    def _block_outcomes(self, statements: list[ast.stmt], prior: list[tuple[str, str]],
                        current: Symbol, types: dict[str, str], stack: tuple[str, ...]
                        ) -> tuple[list[tuple[str, str]], ...]:
        """Capture every non-normal exit while analyzing a structured block."""
        self._return_frames.append([])
        exception_start = len(self._exception_tails)
        loop = self._loop_frames[-1] if self._loop_frames else None
        break_start = len(loop["break"]) if loop else 0
        continue_start = len(loop["continue"]) if loop else 0
        normal = self._block(statements, prior, current, types, stack)
        returned = self._return_frames.pop()
        raised = self._exception_tails[exception_start:]
        del self._exception_tails[exception_start:]
        broke = loop["break"][break_start:] if loop else []
        continued = loop["continue"][continue_start:] if loop else []
        if loop:
            del loop["break"][break_start:]
            del loop["continue"][continue_start:]
        return normal, returned, raised, broke, continued

    def _try_star(self, stmt: ast.TryStar, prior: list[tuple[str, str]], current: Symbol,
                  types: dict[str, str], stack: tuple[str, ...]
                  ) -> tuple[list[tuple[str, str]], list[tuple[str, str]],
                             list[tuple[str, str]], list[tuple[str, str]],
                             list[tuple[str, str]]]:
        """Model ordered except* subgroup matching; each clause may handle a part."""
        assert self.graph is not None
        is_es = self.language == "es"
        yes, no = (("Sí", "No") if is_es else ("Yes", "No"))
        body, returned, body_raised, broke, continued = self._block_outcomes(
            stmt.body, prior, current, types.copy(), stack)
        raised: list[tuple[str, str]] = []
        if stmt.orelse:
            normal, else_returns, else_raises, else_breaks, else_continues = self._block_outcomes(
                stmt.orelse, body, current, types.copy(), stack)
            returned.extend(else_returns)
            raised.extend(else_raises)
            broke.extend(else_breaks)
            continued.extend(else_continues)
        else:
            normal = body

        incoming: list[tuple[str, str]] = list(body_raised)
        self.graph.warnings.append(
            f"except* subgroup dispatch at {current.path}:{stmt.lineno} is data- and type-dependent; "
            "handlers are tested in source order, multiple handlers may run on distinct subgroups, "
            "handler-raised exceptions and any unhandled remainder propagate through cleanup")
        for index, handler in enumerate(stmt.handlers):
            try:
                handler_name = ast.unparse(handler.type) if handler.type is not None else "exception"
            except (TypeError, ValueError):
                handler_name = "exception"
            dispatch_label = (f"Does the remaining subgroup match {handler_name}?" if not is_es
                              else f"¿El subgrupo restante coincide con {handler_name}?")
            dispatch = self._emit(dispatch_label, incoming, current, handler,
                                  kind="decision")[0][0]
            self.graph.nodes[dispatch].label_metadata.update({
                "exception_dispatch": "except_star_ordered",
                "except_star_handler_index": index,
                "exception_type_expression": handler_name,
                "dispatch_scope": "remaining exception subgroup",
                "possible_multiple_handlers": True,
                "significant_control_flow": True,
            })
            handler_label = (f"Capturar subgrupo {handler_name}" if is_es
                             else f"Handle matching subgroup {handler_name}")
            handler_entry = self._emit(handler_label, [(dispatch, yes)], current, handler)
            self.graph.nodes[handler_entry[0][0]].label_metadata.update({
                "exception_route": "caught_subgroup",
                "exception_type_expression": handler_name,
                "exception_dispatch": "except_star_ordered",
                "except_star_handler_index": index,
                "significant_control_flow": True,
            })
            (handler_normal, handler_returns, handler_raises,
             handler_breaks, handler_continues) = self._block_outcomes(
                handler.body, handler_entry, current, types.copy(), stack)
            returned.extend(handler_returns)
            raised.extend(handler_raises)
            broke.extend(handler_breaks)
            continued.extend(handler_continues)
            # A normally completed handler continues dispatch against the
            # remaining subgroup. The No edge retains the subgroup unchanged.
            incoming = [(dispatch, no), *handler_normal]

        remainder_question = ("¿Queda un subgrupo de excepción sin manejar?" if is_es
                             else "Does an unhandled exception subgroup remain?")
        remainder = self._emit(remainder_question, incoming, current, stmt,
                               kind="decision")[0][0]
        self.graph.nodes[remainder].label_metadata.update({
            "exception_dispatch": "except_star_remainder",
            "exception_route": "runtime-dependent",
            "exception_handlers": [ast.unparse(item.type) for item in stmt.handlers],
            "significant_control_flow": True,
        })
        propagated = self._emit(
            "Propagate remaining exception subgroup" if not is_es
            else "Propagar subgrupo de excepción restante",
            [(remainder, yes)], current, stmt)[0][0]
        self.graph.nodes[propagated].label_metadata.update({
            "control_transfer": "raise",
            "exception_route": "propagated_subgroup",
            "exception_origin": "except_star_remainder",
            "exception_dispatch": "runtime-dependent",
            "significant_control_flow": True,
        })
        normal.extend([(remainder, no)])
        raised.append((propagated, ""))
        return normal, returned, raised, broke, continued

    def _try(self, stmt: ast.Try | ast.TryStar, prior: list[tuple[str, str]], current: Symbol,
             types: dict[str, str], stack: tuple[str, ...]) -> list[tuple[str, str]]:
        if stmt.finalbody:
            self._pending_cleanup_depth += 1
        returned: list[tuple[str, str]] = []
        raised: list[tuple[str, str]] = []
        broke: list[tuple[str, str]] = []
        continued: list[tuple[str, str]] = []
        if isinstance(stmt, ast.TryStar):
            normal, returned, raised, broke, continued = self._try_star(
                stmt, prior, current, types, stack)
        elif stmt.handlers:
            assert self.graph is not None
            approximation = "except handler dispatch is approximated"
            detail = ("the try-success route and declared handlers are represented, but exception "
                      "occurrence, type matching and handler selection cannot be determined statically")
            self.graph.warnings.append(
                f"{approximation} at {current.path}:{stmt.lineno}; {detail}")
            body, body_returns, body_raises, body_breaks, body_continues = self._block_outcomes(
                stmt.body, prior, current, types.copy(), stack)
            returned.extend(body_returns)
            broke.extend(body_breaks)
            continued.extend(body_continues)
            # `else` runs only after the try body completes normally. Exceptions
            # raised by the else block are not caught by this try's handlers.
            if stmt.orelse:
                normal, else_returns, else_raises, else_breaks, else_continues = self._block_outcomes(
                    stmt.orelse, body, current, types.copy(), stack)
                returned.extend(else_returns)
                raised.extend(else_raises)
                broke.extend(else_breaks)
                continued.extend(else_continues)
            else:
                normal = body

            dispatch_question = ("¿Qué tipo de excepción se produjo?" if self.language == "es"
                                 else "Which exception type occurred?")
            dispatch_prior = list(body_raises)
            dispatch = self._emit(dispatch_question, dispatch_prior, current, stmt,
                                  kind="decision")[0][0]
            self.graph.nodes[dispatch].label_metadata.update({
                "exception_dispatch": "runtime-dependent",
                "exception_handlers": [ast.unparse(handler.type) if handler.type else None
                                       for handler in stmt.handlers],
                "significant_control_flow": True,
            })
            has_catch_all = any(handler.type is None for handler in stmt.handlers)
            for handler in stmt.handlers:
                if handler.type is None:
                    handler_name = "cualquier excepción" if self.language == "es" else "any exception"
                else:
                    try:
                        handler_name = ast.unparse(handler.type)
                    except (TypeError, ValueError):
                        handler_name = "exception type"
                handler_label = handler_name
                handler_action = (f"Capturar {handler_name}" if self.language == "es"
                                  else f"Handle {handler_name}")
                handler_prior = self._emit(
                    handler_action, [(dispatch, handler_label)], current, handler)
                self.graph.nodes[handler_prior[0][0]].label_metadata.update({
                    "exception_route": "caught",
                    "exception_type_expression": handler_name,
                    "exception_dispatch": "runtime-dependent",
                    "significant_control_flow": True,
                })
                (handler_normal, handler_returns, handler_raises,
                 handler_breaks, handler_continues) = self._block_outcomes(
                    handler.body, handler_prior, current, types.copy(), stack)
                normal.extend(handler_normal)
                returned.extend(handler_returns)
                raised.extend(handler_raises)
                broke.extend(handler_breaks)
                continued.extend(handler_continues)

            if not has_catch_all:
                unhandled_label = "Sin coincidencia" if self.language == "es" else "Unhandled"
                unhandled = self._emit("Excepción no capturada" if self.language == "es"
                                       else "Unhandled exception",
                                       [(dispatch, unhandled_label)], current, stmt)
                self.graph.nodes[unhandled[0][0]].label_metadata.update({
                    "control_transfer": "raise",
                    "exception_route": "propagated",
                    "exception_dispatch": "runtime-dependent",
                    "significant_control_flow": True,
                })
                raised.extend(unhandled)
        else:
            normal, returned, raised, broke, continued = self._block_outcomes(
                stmt.body + stmt.orelse, prior, current, types.copy(), stack)

        if stmt.finalbody:
            self._pending_cleanup_depth -= 1
            normal_after: list[tuple[str, str]] = []
            returned_after: list[tuple[str, str]] = []
            raised_after: list[tuple[str, str]] = []
            broke_after: list[tuple[str, str]] = []
            continued_after: list[tuple[str, str]] = []
            pending_exits = (
                (normal, "normal"), (returned, "return"), (raised, "raise"),
                (broke, "break"), (continued, "continue"),
            )
            for pending, kind in pending_exits:
                if not pending:
                    continue
                # A cleanup body reached by distinct returns must not merge their
                # pending values. Analyze each return transfer independently so a
                # shared cleanup tail cannot inherit only the first value.
                incoming_groups = ([[item] for item in pending] if kind == "return"
                                   else [pending])
                for incoming in incoming_groups:
                    (final_normal, final_returns, final_raises,
                     final_breaks, final_continues) = self._block_outcomes(
                        stmt.finalbody, incoming, current, types.copy(), stack)
                    if kind == "normal":
                        normal_after.extend(final_normal)
                    elif kind == "return":
                        for tail_id, tail_label in final_normal:
                            self.graph.nodes[tail_id].label_metadata.update(
                                self.graph.nodes[incoming[0][0]].label_metadata)
                            returned_after.append((tail_id, tail_label))
                    elif kind == "raise":
                        raised_after.extend(final_normal)
                    elif kind == "break":
                        broke_after.extend(final_normal)
                    else:
                        continued_after.extend(final_normal)
                    # Any abrupt completion in finally overrides the pending outcome.
                    returned_after.extend(final_returns)
                    raised_after.extend(final_raises)
                    broke_after.extend(final_breaks)
                    continued_after.extend(final_continues)
            normal, returned, raised = normal_after, returned_after, raised_after
            broke, continued = broke_after, continued_after

        self._return_frames[-1].extend(returned)
        self._exception_tails.extend(raised)
        if self._loop_frames:
            self._loop_frames[-1]["break"].extend(broke)
            self._loop_frames[-1]["continue"].extend(continued)
        return normal


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
                    and incoming[b.id] == 1 and not edge.label
                    and not a.label_metadata.get("significant_call")
                    and not b.label_metadata.get("significant_call")
                    and not a.label_metadata.get("significant_control_flow")
                    and not b.label_metadata.get("significant_control_flow")
                    and not a.label_metadata.get("significant_state_change")
                    and not b.label_metadata.get("significant_state_change")):
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
