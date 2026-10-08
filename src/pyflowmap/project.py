"""Safe source loading and a small Python symbol index (no execution/imports)."""

import ast
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Iterator
from zipfile import ZipFile

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

    def _import(self, module: Module, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imports[alias.asname or alias.name.split(".")[0]] = alias.name
        elif node.level == 0 and node.module:
            for alias in node.names:
                module.imports[alias.asname or alias.name] = f"{node.module}:{alias.name}"
        # Relative imports and dynamically imported symbols remain unresolved.

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
        match = [s for s in self.classes if s == f"{module}:{name}" or s == imported or s.endswith(":" + name) and imported and s.endswith(imported)]
        return match[0] if len(match) == 1 else None

    def resolve_call(self, call: ast.Call, current: Symbol, types: dict[str, str]) -> Symbol | None:
        func = call.func
        candidates: list[str] = []
        record = self.modules[current.module]
        if isinstance(func, ast.Name):
            candidates = [f"{current.module}:{func.id}"]
            imp = record.imports.get(func.id)
            if imp:
                candidates.append(imp)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            if base in types:
                candidates = [f"{types[base]}.{func.attr}"]
            elif base in ("self", "cls") and current.owner:
                candidates = [f"{current.module}:{current.owner}.{func.attr}"]
            elif f"{current.module}:{base}" in self.classes:
                candidates = [f"{current.module}:{base}.{func.attr}"]
            else:
                imported = record.imports.get(base)
                if imported:
                    if ":" in imported:
                        candidates = [f"{imported}.{func.attr}"]
                    else:
                        candidates = [f"{imported}:{func.attr}"]
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call):
            # ClassName().method(...) without an intermediate local variable.
            called = func.value.func
            if isinstance(called, ast.Name):
                ctor = self.class_id(called.id, current.module)
                if ctor:
                    candidates.append(f"{ctor}.{func.attr}")
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
        with tempfile.TemporaryDirectory(prefix="pyflowmap-") as directory:
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
