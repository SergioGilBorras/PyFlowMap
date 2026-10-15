"""UML 2.5.1 packages and dependencies supported by literal Python imports.

A Python package boundary is recognized only when an __init__.py file is
present in the scanned source. Namespace-package and runtime import machinery
are not guessed. The UML relation is Dependency, not PackageImport.
"""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from html import escape
from pathlib import PurePosixPath

from ..project import ProjectIndex


@dataclass(frozen=True)
class UmlPackage:
    id: str
    directory: str
    parent: str | None
    modules: tuple[str, ...]
    location: str


@dataclass(frozen=True)
class UmlPackageDependency:
    client: str
    supplier: str
    evidence: tuple[str, ...]


@dataclass
class PackageDiagram:
    packages: list[UmlPackage] = field(default_factory=list)
    dependencies: list[UmlPackageDependency] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "diagram_type": "package", "uml_version": "2.5.1",
            "packages": [asdict(node) for node in self.packages],
            "dependencies": [asdict(link) for link in self.dependencies],
            "warnings": list(self.warnings),
        }


def _parts(record_path: str, *, skip_src: bool) -> tuple[str, ...]:
    parts = PurePosixPath(record_path).parts
    if skip_src and parts[0] == "src":
        parts = parts[1:]
    return parts


def _candidate_modules(stmt: ast.Import | ast.ImportFrom, current_module: str,
                       current_package: str) -> list[str]:
    if isinstance(stmt, ast.Import):
        return [alias.name for alias in stmt.names]
    if stmt.level:
        pkg = current_package.split(".")
        if stmt.level > len(pkg):
            return []
        root = pkg[:len(pkg) - stmt.level + 1]
        prefix = ".".join([*root, *(stmt.module.split(".") if stmt.module else [])])
    else:
        prefix = stmt.module or ""
    # For from x import y, y may be a submodule or just a symbol exported by x.
    return [name for alias in stmt.names
            for name in (f"{prefix}.{alias.name}" if prefix else alias.name, prefix)]


def analyze_package_diagram(index: ProjectIndex, scope: str | None = None, *,
                            max_packages: int = 250) -> PackageDiagram:
    if not 1 <= max_packages <= 1000:
        raise ValueError("max_packages must be in 1..1000")
    records = list(index.modules.values())
    # Conventional src-layout is not itself an importable package unless it
    # has an __init__.py. Do not show it as a phantom UML package.
    skip_src = (not any(m.path == "src/__init__.py" for m in records)
                and any(m.path.startswith("src/") for m in records))
    pack: dict[str, str] = {}
    module_to_package: dict[str, str] = {}
    module_to_record = {}
    for record in records:
        parts = _parts(record.path, skip_src=skip_src)
        if not parts:
            continue
        mod = ".".join((*parts[:-1], parts[-1][:-3]))
        if parts[-1] == "__init__.py":
            mod = ".".join(parts[:-1])
            if mod:
                pack[mod] = record.path
        if mod:
            module_to_record[mod] = record
    if not pack:
        raise ValueError("No declared Python packages (__init__.py) found")
    visible = sorted(pack)
    if scope:
        clean = scope.replace("\\", "/").strip("/")
        visible = [key for key in visible if (
            pack[key] == clean or pack[key].startswith(clean + "/")
            or str(PurePosixPath(pack[key]).parent) == clean
        )]
    if not visible:
        raise ValueError("No packages found under the selected scope")
    if len(visible) > max_packages:
        raise ValueError(f"Package diagram has {len(visible)} packages (limit {max_packages}); narrow --scope")
    visible_set = set(visible)
    for module in module_to_record:
        # Match declared package by exact module name or enclosing namespace.
        ancestors = [p for p in pack if module == p or module.startswith(p + ".")]
        if ancestors:
            module_to_package[module] = max(ancestors, key=len)
    result = PackageDiagram(warnings=list(index.warnings))
    for name in visible:
        parent = name.rpartition(".")[0]
        modules = tuple(sorted(mod for mod, owner in module_to_package.items()
                               if owner == name))
        result.packages.append(UmlPackage(
            name, str(PurePosixPath(pack[name]).parent),
            parent if parent in visible_set else None, modules, pack[name],
        ))
    links: dict[tuple[str, str], set[str]] = {}
    for module, record in sorted(module_to_record.items()):
        client = module_to_package.get(module)
        if client not in visible_set:
            continue
        for stmt in ast.walk(record.tree):
            if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
                continue
            # Explicit import syntax is evidence of a static source dependency,
            # not proof that the code executed or the imported module loaded.
            for candidate in _candidate_modules(stmt, module, client):
                owner = module_to_package.get(candidate)
                if owner and owner in visible_set and owner != client:
                    links.setdefault((client, owner), set()).add(
                        f"{record.path}:{stmt.lineno}"
                    )
    result.dependencies = [UmlPackageDependency(a, b, tuple(sorted(loc)))
                           for (a, b), loc in sorted(links.items())]
    return result


def to_dot(diagram: PackageDiagram, direction: str = "TD") -> str:
    """Draw a UML package with its small tab at the upper-left, not a file icon."""
    if direction not in ("TD", "LR"):
        raise ValueError("direction must be TD or LR")
    nodes = {pkg.id: f"P{i + 1}" for i, pkg in enumerate(diagram.packages)}
    lines = [
        "digraph uml_packages {",
        ('  graph [bgcolor="white", pad=0.32, nodesep=1.0, ranksep=1.15, '
         'splines=polyline, outputorder=edgesfirst];'),
        f"  rankdir={'TB' if direction == 'TD' else 'LR'};",
        '  node [shape=plain, fontname="Helvetica", fontsize=14];',
        ('  edge [style=dashed, arrowhead=vee, color="#4A6079", '
         'penwidth=1.2, arrowsize=0.9];'),
    ]
    for package in diagram.packages:
        # Namespaced UML package names; no unproven package import stereotypes.
        name = escape(package.id.replace(".", "::"), quote=True)
        html = (
            '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0">'
            '<TR><TD BORDER="1" BGCOLOR="#E7EEF6" WIDTH="65" HEIGHT="12"></TD>'
            '<TD BORDER="0" WIDTH="85"></TD></TR>'
            '<TR><TD COLSPAN="2" BORDER="1" BGCOLOR="#F9FBFE" CELLPADDING="16">'
            f'<FONT FACE="Helvetica" COLOR="#1A3049" POINT-SIZE="14">{name}</FONT>'
            '</TD></TR></TABLE>'
        )
        tooltip = f"{package.id} ({package.location})"
        lines.append(f"  {nodes[package.id]} [label=<{html}>, "
                     f"tooltip={json.dumps(tooltip)}];")
    for dependency in diagram.dependencies:
        lines.append(f"  {nodes[dependency.client]} -> {nodes[dependency.supplier]};")
    lines.append("}")
    return "\n".join(lines) + "\n"
