"""Conservative UML 2.5.1 class declarations from Python syntax alone.

Only declared classifiers, features and locally resolved generalizations are
modeled. No associations, multiplicities, ownership or runtime MRO is guessed.
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from html import escape

from ..project import ProjectIndex

MAX_CLASSES = 250


@dataclass(frozen=True)
class UmlFeature:
    name: str
    visibility: str
    type: str | None = None
    parameters: tuple[str, ...] = ()
    static: bool = False
    abstract: bool = False
    location: str = ""


@dataclass
class UmlClassifier:
    id: str
    name: str
    module: str
    path: str
    line: int
    abstract: bool = False
    attributes: list[UmlFeature] = field(default_factory=list)
    operations: list[UmlFeature] = field(default_factory=list)


@dataclass(frozen=True)
class UmlGeneralization:
    specific: str
    general: str
    location: str


@dataclass(frozen=True)
class UmlDependency:
    """A UML dependency grounded in an explicit declared type."""

    client: str
    supplier: str
    evidence: tuple[str, ...]


@dataclass
class ClassDiagram:
    classes: list[UmlClassifier] = field(default_factory=list)
    generalizations: list[UmlGeneralization] = field(default_factory=list)
    dependencies: list[UmlDependency] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "diagram_type": "class", "uml_version": "2.5.1",
            "classes": [asdict(item) for item in self.classes],
            "generalizations": [asdict(item) for item in self.generalizations],
            "dependencies": [asdict(item) for item in self.dependencies],
            "warnings": list(self.warnings),
        }


def _visibility(name: str) -> str:
    """Python conventions only: Python does not enforce UML visibility."""
    if name.startswith("__") and not name.endswith("__"):
        return "-"
    if name.startswith("_") and not name.startswith("__"):
        return "#"
    return "+"


def _annotation(expr: ast.expr | None) -> str | None:
    if expr is None:
        return None
    text = ast.unparse(expr).replace("\n", " ")
    return text[:95] if len(text) <= 95 else None


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ast.unparse(node)


def _class_features(node: ast.ClassDef, path: str) -> tuple[list[UmlFeature], list[UmlFeature], bool]:
    attrs: dict[str, UmlFeature] = {}
    operations: list[UmlFeature] = []
    abstract = any(_decorator_name(item).endswith("ABCMeta") for item in node.keywords)
    for base in node.bases:
        if isinstance(base, (ast.Name, ast.Attribute)) and ast.unparse(base) in ("ABC", "abc.ABC"):
            abstract = True
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            attrs[stmt.target.id] = UmlFeature(
                stmt.target.id, _visibility(stmt.target.id), _annotation(stmt.annotation),
                static=(_annotation(stmt.annotation) or "").startswith(("ClassVar[", "typing.ClassVar[")),
                location=f"{path}:{stmt.lineno}",
            )
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id not in attrs:
                    attrs[target.id] = UmlFeature(
                        target.id, _visibility(target.id), static=True,
                        location=f"{path}:{stmt.lineno}",
                    )
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = {_decorator_name(item) for item in stmt.decorator_list}
            is_static = bool(decorators & {"staticmethod", "classmethod", "builtins.staticmethod"})
            is_abstract = bool(decorators & {"abstractmethod", "abc.abstractmethod"})
            abstract |= is_abstract
            args = list(stmt.args.posonlyargs) + list(stmt.args.args)
            # Method receivers are conventions, not universally present.
            if args and args[0].arg in ("self", "cls") and not (
                "staticmethod" in decorators or "builtins.staticmethod" in decorators
            ):
                args = args[1:]
            params = [f"{a.arg}: {_annotation(a.annotation)}" if a.annotation else a.arg for a in args]
            if stmt.args.vararg:
                params.append("*" + stmt.args.vararg.arg)
            params.extend(f"{a.arg}: {_annotation(a.annotation)}" if a.annotation else a.arg
                          for a in stmt.args.kwonlyargs)
            if stmt.args.kwarg:
                params.append("**" + stmt.args.kwarg.arg)
            operations.append(UmlFeature(
                stmt.name, _visibility(stmt.name), _annotation(stmt.returns),
                tuple(params), is_static, is_abstract,
                f"{path}:{stmt.lineno}",
            ))
            if stmt.name == "__init__":
                # Direct constructor assignments are the only inferred instance
                # features. Conditional or nested writes are not guaranteed.
                for init in stmt.body:
                    targets = []
                    typ = None
                    if isinstance(init, ast.Assign):
                        targets = init.targets
                    elif isinstance(init, ast.AnnAssign):
                        targets = [init.target]
                        typ = _annotation(init.annotation)
                    for target in targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            previous = attrs.get(target.attr)
                            attrs[target.attr] = UmlFeature(
                                target.attr, _visibility(target.attr),
                                typ or (previous.type if previous else None),
                                location=f"{path}:{init.lineno}",
                            )
    return list(attrs.values()), operations, abstract


def _resolved_base(index: ProjectIndex, module: str, expr: ast.expr) -> str | None:
    record = index.modules[module]
    candidate = None
    if isinstance(expr, ast.Name):
        candidate = (f"{module}:{expr.id}" if f"{module}:{expr.id}" in index.classes
                     else record.imports.get(expr.id))
    elif isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        imp = record.imports.get(expr.value.id)
        if imp and ":" not in imp:
            candidate = f"{imp}:{expr.attr}"
    if candidate in index.classes:
        return candidate
    if not candidate or ":" not in candidate:
        return None
    # Project may be rooted above src/, while imports use a package prefix.
    # Accept only an unambiguous fully qualified suffix.
    matches = [identifier for identifier in index.classes
               if identifier == candidate or identifier.endswith("." + candidate)]
    return matches[0] if len(matches) == 1 else None


def _declared_type_dependencies(index: ProjectIndex, module: str,
                                node: ast.ClassDef) -> list[tuple[str, str]]:
    """Resolve only annotated types; never infer associations or ownership."""
    annotations: list[tuple[ast.expr, int]] = []
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign):
            annotations.append((statement.annotation, statement.lineno))
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = statement.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            if arg.annotation is not None:
                annotations.append((arg.annotation, arg.lineno))
        for arg in (args.vararg, args.kwarg):
            if arg is not None and arg.annotation is not None:
                annotations.append((arg.annotation, arg.lineno))
        if statement.returns is not None:
            annotations.append((statement.returns, statement.lineno))
        if statement.name == "__init__":
            for init in statement.body:
                if isinstance(init, ast.AnnAssign):
                    annotations.append((init.annotation, init.lineno))
    found: set[tuple[str, str]] = set()
    for annotation, line in annotations:
        for expr in ast.walk(annotation):
            if isinstance(expr, (ast.Name, ast.Attribute)):
                target = _resolved_base(index, module, expr)
                if target:
                    found.add((target, str(line)))
    return sorted(found)


def analyze_class_diagram(index: ProjectIndex, scope: str | None = None, *
                          max_classes: int = MAX_CLASSES) -> ClassDiagram:
    if not 1 <= max_classes <= 1000:
        raise ValueError("max_classes must be in 1..1000")
    selected = sorted(index.class_nodes)
    if scope:
        clean = scope.replace("\\", "/").strip("/")
        selected = [key for key in selected if (
            index.modules[key.split(":", 1)[0]].path == clean
            or index.modules[key.split(":", 1)[0]].path.startswith(clean + "/")
        )]
    if not selected:
        raise ValueError("No class declarations found under the selected source/scope")
    if len(selected) > max_classes:
        raise ValueError(f"Class diagram contains {len(selected)} classes (limit {max_classes}); narrow --scope")
    result = ClassDiagram(warnings=list(index.warnings))
    ids = set(selected)
    dependencies: dict[tuple[str, str], set[str]] = {}
    for identifier in selected:
        module, name = identifier.split(":", 1)
        record = index.modules[module]
        node = index.class_nodes[identifier]
        attrs, operations, abstract = _class_features(node, record.path)
        result.classes.append(UmlClassifier(identifier, name, module, record.path,
                                            node.lineno, abstract, attrs, operations))
        for supplier, line in _declared_type_dependencies(index, module, node):
            if supplier in ids and supplier != identifier:
                dependencies.setdefault((identifier, supplier), set()).add(
                    f"{record.path}:{line}"
                )
        for base in node.bases:
            parent = _resolved_base(index, module, base)
            if parent in ids and parent != identifier:
                result.generalizations.append(UmlGeneralization(
                    identifier, parent, f"{record.path}:{base.lineno}",
                ))
            elif ast.unparse(base) != "object":
                result.warnings.append(
                    f"Unmodeled external, dynamic or out-of-scope superclass at "
                    f"{record.path}:{base.lineno}"
                )
    inherited = {(edge.specific, edge.general) for edge in result.generalizations}
    result.dependencies = [
        UmlDependency(client, supplier, tuple(sorted(evidence)))
        for (client, supplier), evidence in sorted(dependencies.items())
        if (client, supplier) not in inherited
    ]
    return result


def _safe_member(text: str, length: int = 120) -> str:
    """Restrict Mermaid member text; keep raw source in JSON for audit."""
    text = re.sub(r"[^\w\s.:,*()\[\]|+\-/]", "", text.replace("\n", " "))
    return text[:length]


def _feature_text(feature: UmlFeature, is_operation: bool) -> str:
    name = feature.visibility + feature.name
    if is_operation:
        name += "(" + ", ".join(feature.parameters) + ")"
    if feature.type:
        name += ": " + feature.type
    return name


def to_mermaid(diagram: ClassDiagram, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    by_id = {c.id: f"C{i + 1}" for i, c in enumerate(diagram.classes)}
    lines = ["classDiagram", f"direction {direction}"]
    for cls in diagram.classes:
        key = by_id[cls.id]
        # Labels use a unique qualified name; Mermaid identifiers remain safe.
        title = _safe_member(f"{cls.module}.{cls.name}")
        lines.append(f'    class {key}["{title}"] {{')
        for attribute in cls.attributes:
            lines.append("        " + _safe_member(_feature_text(attribute, False))
                         + ("$" if attribute.static else ""))
        for operation in cls.operations:
            text = _safe_member(_feature_text(operation, True))
            lines.append("        " + text + ("*" if operation.abstract else "")
                         + ("$" if operation.static else ""))
        lines.append("    }")
    for edge in diagram.generalizations:
        lines.append(f"    {by_id[edge.general]} <|-- {by_id[edge.specific]}")
    for edge in diagram.dependencies:
        lines.append(f"    {by_id[edge.client]} ..> {by_id[edge.supplier]} : «use»")
    return "\n".join(lines) + "\n"


def to_dot(diagram: ClassDiagram, direction: str = "TD") -> str:
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    by_id = {c.id: f"C{i + 1}" for i, c in enumerate(diagram.classes)}
    lines = ["digraph uml_classes {", "  graph [bgcolor=white, pad=0.28, nodesep=0.9, ranksep=1.05, outputorder=edgesfirst];",
             f"  rankdir={'TB' if direction == 'TD' else 'LR'};",
             '  node [shape=plain, fontname="Helvetica", fontsize=12];',
             '  edge [color="#3D5269", penwidth=1.15];']
    for cls in diagram.classes:
        def cell(value: str, *, align: str = "LEFT") -> str:
            return (f'<TR><TD ALIGN="{align}" CELLPADDING="8">'
                    + value + "</TD></TR>")
        namespace = escape(cls.module.replace(".", "::"), quote=True)
        caption = escape(cls.name, quote=True)
        if cls.abstract:
            caption = f"<I>{caption}</I>"
        title = ('<TR><TD ALIGN="CENTER" BGCOLOR="#EAF0F8" CELLPADDING="10">'
                 f'<FONT COLOR="#657A94" FACE="Helvetica" POINT-SIZE="10">{namespace}</FONT>'
                 '<BR/>'
                 f'<FONT COLOR="#172A43" FACE="Helvetica" POINT-SIZE="15"><B>{caption}</B></FONT>'
                 "</TD></TR>")
        def lines_for(values: list[UmlFeature], is_op: bool) -> str:
            if not values:
                return cell("&#160;")
            snippets = []
            for value in values:
                txt = escape(_feature_text(value, is_op), quote=True)
                if value.abstract:
                    txt = f"<I>{txt}</I>"
                if value.static:
                    txt = f"<U>{txt}</U>"
                snippets.append(txt)
            return cell('<BR ALIGN="LEFT"/>'.join(snippets))
        body = (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" '
                f'BGCOLOR="white" COLOR="#52677F">{title}'
                f'<HR/>{lines_for(cls.attributes, False)}'
                f'<HR/>{lines_for(cls.operations, True)}</TABLE>')
        tip = escape(f"{cls.module}.{cls.name} ({cls.path}:{cls.line})", quote=True)
        lines.append(f'  {by_id[cls.id]} [label=<{body}>, tooltip="{tip}"];')
    for edge in diagram.generalizations:
        # Rank superclasses above subclasses, with the open UML triangle
        # pointing to the superclass at the tail of Graphviz's layout edge.
        lines.append(f"  {by_id[edge.general]} -> {by_id[edge.specific]} "
                     "[dir=back, arrowtail=empty, arrowsize=1.1];")
    for edge in diagram.dependencies:
        lines.append(f"  {by_id[edge.client]} -> {by_id[edge.supplier]} "
                     '[style=dashed, arrowhead=vee, color="#7289A1", '
                     'fontcolor="#516A83", fontsize=10, label="«use»", '
                     'arrowsize=0.8, constraint=false];')
    lines.append("}")
    return "\n".join(lines) + "\n"
