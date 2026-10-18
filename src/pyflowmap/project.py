"""Safe source loading and a small Python symbol index (no execution/imports)."""

import ast
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from portable_tempdirs import temporary_directory

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "site-packages", ".tox", "build", "dist"}
MAX_FILES = 2500
MAX_FILE_BYTES = 2_000_000
MAX_ZIP_BYTES = 100_000_000


@dataclass
class Symbol:
    id: str
    name: str
    module: str
    path: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    owner: str = ""


@dataclass
class Module:
    name: str
    path: str
    tree: ast.Module
    imports: dict[str, str] = field(default_factory=dict)


class ProjectIndex:
    def __init__(self, root: Path, selected_file: Path | None = None):
        self.root = root.resolve()
        self.symbols: dict[str, Symbol] = {}
        self.modules: dict[str, Module] = {}
        self.classes: set[str] = set()
        self.class_nodes: dict[str, ast.ClassDef] = {}
        self.warnings: list[str] = []
        files = [selected_file] if selected_file else self._python_files()
        if not files:
            raise ValueError("No Python files found in the source")
        for path in files:
            if path is None or path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if path.stat().st_size > MAX_FILE_BYTES:
                self.warnings.append(f"Skipped oversized file: {rel}")
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
            except (SyntaxError, UnicodeError) as exc:
                self.warnings.append(f"Skipped unparsable file {rel}: {exc}")
                continue
            module = ".".join(Path(rel).with_suffix("").parts)
            if module.endswith(".__init__"):
                module = module.removesuffix(".__init__")
            record = Module(name=module, path=rel, tree=tree)
            self.modules[module] = record
            for stmt in tree.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    self._import(record, stmt)
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._add_function(record, stmt)
                if isinstance(stmt, ast.ClassDef):
                    self.classes.add(f"{module}:{stmt.name}")
                    self.class_nodes[f"{module}:{stmt.name}"] = stmt
                    for method in stmt.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            self._add_function(record, method, stmt.name)
        if not self.modules:
            raise ValueError("No parseable Python files found")

    def _python_files(self) -> list[Path]:
        found = []
        for path in sorted(self.root.rglob("*.py")):
            rel = path.relative_to(self.root)
            if any(p.startswith(".") or p in SKIP_DIRS for p in rel.parts[:-1]):
                continue
            if not path.is_symlink() and path.is_file():
                found.append(path)
            if len(found) > MAX_FILES:
                raise ValueError(f"Project exceeds {MAX_FILES} Python files")
        return found

    def _add_function(self, module: Module, node: ast.FunctionDef | ast.AsyncFunctionDef, owner: str = "") -> None:
        qualname = f"{owner}.{node.name}" if owner else node.name
        identifier = f"{module.name}:{qualname}"
        self.symbols[identifier] = Symbol(identifier, node.name, module.name, module.path, node, owner)
        self._add_nested_functions(module, node.body, qualname)

    def _add_nested_functions(self, module: Module, statements: list[ast.stmt], owner: str) -> None:
        """Index local functions under their lexical owner without crossing scopes."""
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_function(module, statement, owner)
                continue
            if isinstance(statement, ast.ClassDef):
                continue
            for child in ast.iter_child_nodes(statement):
                if isinstance(child, ast.stmt):
                    self._add_nested_functions(module, [child], owner)

    def _import(self, module: Module, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imports[alias.asname or alias.name.split(".")[0]] = alias.name
        else:
            # A single leading dot is relative to the current package.
            # Example: planning.coordinator `from .agents import Agent`.
            package = module.name.split(".")[:-1]
            if node.level:
                if node.level > len(package):
                    self.warnings.append(f"Unresolved relative import in {module.path}:{node.lineno}")
                    return
                prefix = package[:len(package) - node.level + 1]
                imported_module = ".".join([*prefix, *(node.module.split(".") if node.module else [])])
            else:
                imported_module = node.module or ""
            for alias in node.names:
                if node.module:
                    module.imports[alias.asname or alias.name] = f"{imported_module}:{alias.name}"
                else:
                    module.imports[alias.asname or alias.name] = imported_module + "." + alias.name

    def candidates(self, scope: str | None = None) -> list[Symbol]:
        if scope is None:
            return list(self.symbols.values())
        clean = scope.replace("\\", "/").strip("/")
        paths = (clean, clean + "/")
        result = [s for s in self.symbols.values() if s.path == paths[0] or s.path.startswith(paths[1])]
        if not result:
            raise ValueError(f"No functions or methods found under scope: {scope}")
        return result

    def entry(self, query: str | None, scope: str | None = None) -> Symbol:
        options = self.candidates(scope)
        if query:
            q = query.strip()
            matched = [s for s in options if s.id == q or s.id.endswith("." + q) or s.id.endswith(":" + q) or s.id.split(":", 1)[-1] == q or (":" in q and s.id.endswith(q))]
            if len(matched) == 1:
                return matched[0]
            if not matched:
                raise ValueError(f"Unknown entry '{q}'. Run `pyflowmap inspect` to list choices")
            raise ValueError(f"Ambiguous entry '{q}': {', '.join(s.id for s in matched[:12])}")
        mains = [s for s in options if s.name == "main" and not s.owner]
        if len(mains) == 1:
            return mains[0]
        public = [s for s in options if not s.name.startswith("_") and not s.name.startswith("test_")]
        if len(public) == 1:
            return public[0]
        raise ValueError("No unambiguous entry point. Choose --entry from `pyflowmap inspect`")

    def class_id(self, name: str, module: str) -> str | None:
        record = self.modules[module]
        imported = record.imports.get(name, "")
        match = [s for s in self.classes if s == f"{module}:{name}" or s == imported]
        return match[0] if len(match) == 1 else None

    def _method_targets(self, class_id: str, method: str, seen: set[str] | None = None) -> list[Symbol]:
        """Resolve a method through statically named, unambiguous base classes."""
        seen = seen or set()
        if class_id in seen:
            return []
        seen.add(class_id)
        direct = self.symbols.get(f"{class_id}.{method}")
        if direct:
            return [direct]
        module_name = class_id.split(":", 1)[0]
        class_node = self.class_nodes.get(class_id)
        if class_node is None:
            return []
        inherited = []
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                base_id = self.class_id(base.id, module_name)
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                imported = self.modules[module_name].imports.get(base.value.id)
                base_id = f"{imported}.{base.attr}" if imported and ":" in imported else None
                if imported and ":" not in imported:
                    base_id = f"{imported}:{base.attr}"
            else:
                base_id = None
            if base_id:
                inherited.extend(self._method_targets(base_id, method, seen))
        # Multiple independent base implementations are ambiguous without MRO modeling.
        unique = {symbol.id: symbol for symbol in inherited}
        return list(unique.values()) if len(unique) == 1 else []

    def instance_types(self, current: Symbol) -> dict[str, str]:
        """Conservatively infer default-instantiated `self.attribute` classes.

        A caller can inject a different implementation, so this is a default
        constructor hint, not a guarantee about runtime dispatch.
        """
        if not current.owner:
            return {}
        init = self.symbols.get(f"{current.module}:{current.owner}.__init__")
        if init is None:
            return {}
        inferred = {}
        for stmt in init.node.body:
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            candidate_calls = [n for n in ast.walk(stmt.value) if isinstance(n, ast.Call)]
            constructors = set()
            for call in candidate_calls:
                if isinstance(call.func, ast.Name):
                    found = self.class_id(call.func.id, init.module)
                    factory = self.resolve_call(call, init, {})
                    if found:
                        constructors.add(found)
                    elif factory:
                        for returned in ast.walk(factory.node):
                            if (isinstance(returned, ast.Return)
                                    and isinstance(returned.value, ast.Call)
                                    and isinstance(returned.value.func, ast.Name)):
                                returned_class = self.class_id(returned.value.func.id, factory.module)
                                if returned_class:
                                    constructors.add(returned_class)
            if len(constructors) != 1:
                continue
            for target in targets:
                if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                        and target.value.id == "self"):
                    inferred[f"self.{target.attr}"] = next(iter(constructors))
        return inferred

    def resolve_call(self, call: ast.Call, current: Symbol, types: dict[str, str]) -> Symbol | None:
        func = call.func
        candidates: list[str] = []
        record = self.modules[current.module]
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name)
                and func.value.func.id == "super" and current.owner
                and not func.value.args and not func.value.keywords):
            # Resolve no-argument super() only for a single statically named base.
            # Multiple inheritance/MRO and dynamic bases remain unresolved.
            owner_id = f"{current.module}:{current.owner}"
            owner_node = self.class_nodes.get(owner_id)
            if owner_node is not None and len(owner_node.bases) == 1:
                base = owner_node.bases[0]
                base_id = None
                if isinstance(base, ast.Name):
                    base_id = self.class_id(base.id, current.module)
                elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                    imported = record.imports.get(base.value.id)
                    if imported:
                        base_id = (f"{imported}.{base.attr}" if ":" in imported
                                   else f"{imported}:{base.attr}")
                if base_id:
                    inherited = self._method_targets(base_id, func.attr)
                    if len(inherited) == 1:
                        candidates = [inherited[0].id]
        if isinstance(func, ast.Name):
            # Search local lexical scopes from nearest to farthest before module globals.
            qualname = current.id.split(":", 1)[1]
            scopes = [".".join(qualname.split(".")[:index])
                      for index in range(len(qualname.split(".")), 0, -1)]
            candidates = [f"{current.module}:{scope}.{func.id}" for scope in scopes]
            candidates.append(f"{current.module}:{func.id}")
            imp = record.imports.get(func.id)
            if imp:
                candidates.append(imp)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            if base in types:
                candidates = [f"{types[base]}.{func.attr}"]
                inherited = self._method_targets(types[base], func.attr)
                candidates.extend(symbol.id for symbol in inherited)
            elif base in ("self", "cls") and current.owner:
                candidates = [f"{current.module}:{current.owner}.{func.attr}"]
                candidates.extend(symbol.id for symbol in self._method_targets(
                    f"{current.module}:{current.owner}", func.attr))
            elif f"{current.module}:{base}" in self.classes:
                candidates = [f"{current.module}:{base}.{func.attr}"]
            else:
                imported = record.imports.get(base)
                if imported:
                    if ":" in imported:
                        candidates = [f"{imported}.{func.attr}"]
                    else:
                        candidates = [f"{imported}:{func.attr}"]
        elif (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
              and isinstance(func.value.value, ast.Name) and func.value.value.id == "self"):
            cls = types.get(f"self.{func.value.attr}")
            if cls:
                candidates = [f"{cls}.{func.attr}"]
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call):
            # ClassName().method(...) without an intermediate local variable.
            called = func.value.func
            if isinstance(called, ast.Name):
                ctor = self.class_id(called.id, current.module)
                if ctor:
                    candidates.append(f"{ctor}.{func.attr}")
                    candidates.extend(symbol.id for symbol in self._method_targets(ctor, func.attr))
        for candidate in candidates:
            if candidate in self.symbols:
                return self.symbols[candidate]
            # Allow imports written without the leading src package, but never guess across ambiguities.
            suffix = candidate.split(":", 1)
            if len(suffix) == 2:
                matched = [s for s in self.symbols.values() if s.id.endswith("." + candidate) or (s.id.split(":")[0].endswith("." + suffix[0]) and s.id.endswith(":" + suffix[1]))]
                if len(matched) == 1:
                    return matched[0]
        return None

    def possible_call_targets(self, call: ast.Call, current: Symbol,
                              types: dict[str, str] | None = None) -> list[Symbol]:
        """Return candidates only when receiver or lexical scope narrows dispatch."""
        func = call.func
        types = types or {}
        if isinstance(func, ast.Name):
            return [symbol for symbol in self.symbols.values()
                    if symbol.name == func.id and symbol.module == current.module
                    and symbol.id != current.id]
        if not isinstance(func, ast.Attribute):
            return []
        classes: set[str] = set()
        receiver = func.value
        if isinstance(receiver, ast.Name) and receiver.id in types:
            classes.add(types[receiver.id])
        elif (isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name)
              and receiver.value.id == "self" and f"self.{receiver.attr}" in types):
            classes.add(types[f"self.{receiver.attr}"])
        else:
            constructors = []
            if isinstance(receiver, ast.Call):
                constructors = [receiver]
            elif isinstance(receiver, (ast.BoolOp, ast.IfExp)):
                constructors = [item for item in ast.walk(receiver) if isinstance(item, ast.Call)]
            for constructor in constructors:
                if isinstance(constructor.func, ast.Name):
                    resolved = self.class_id(constructor.func.id, current.module)
                    if resolved:
                        classes.add(resolved)
        return [self.symbols[f"{class_id}.{func.attr}"] for class_id in classes
                if f"{class_id}.{func.attr}" in self.symbols]


@contextmanager
def load_project(source: str | Path) -> Iterator[ProjectIndex]:
    """Load a local directory, .py file, or ZIP; never import or run source code."""
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Source does not exist: {path}")
    if path.is_dir():
        yield ProjectIndex(path)
    elif path.is_file() and path.suffix == ".py":
        yield ProjectIndex(path.parent, selected_file=path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        temp_parent = Path(os.environ.get("PYFLOWMAP_TEMP_ROOT", tempfile.gettempdir())).expanduser().resolve()
        if not temp_parent.is_dir():
            raise ValueError(f"Temporary directory parent does not exist: {temp_parent}")
        with temporary_directory("pyflowmap-zip", parent=temp_parent) as directory:
            root = Path(directory)
            total = 0
            count = 0
            with ZipFile(path) as archive:
                for item in archive.infolist():
                    name = PurePosixPath(item.filename)
                    if item.is_dir():
                        continue
                    if name.is_absolute() or ".." in name.parts or "\\" in item.filename:
                        raise ValueError("Unsafe path in ZIP archive")
                    mode = item.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise ValueError("Symlinks in ZIP archives are not permitted")
                    if name.suffix != ".py":
                        continue
                    count += 1
                    total += item.file_size
                    if count > MAX_FILES or item.file_size > MAX_FILE_BYTES or total > MAX_ZIP_BYTES:
                        raise ValueError("ZIP archive exceeds configured source limits")
                    target = root.joinpath(*name.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as src, target.open("wb") as out:
                        # Stream with strict per-file length check.
                        size = 0
                        while chunk := src.read(65536):
                            size += len(chunk)
                            if size > MAX_FILE_BYTES:
                                raise ValueError("ZIP entry exceeds configured source limits")
                            out.write(chunk)
            yield ProjectIndex(root)
    else:
        raise ValueError("Source must be a Python file, a local directory, or a ZIP archive")
