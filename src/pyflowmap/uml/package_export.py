"""Faithful UML package shape and dependency exports using Graphviz DOT."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..output_paths import next_graph_directory
from ..project import load_project
from ..render import RenderError
from .packages import analyze_package_diagram, to_dot


def generate_package_diagram(source: str, *, scope: str | None = None,
                             format: str = "all", output: str | None = None,
                             direction: str = "TD", renderer: str = "auto",
                             max_packages: int = 250,
                             package_style: str = "modern") -> dict:
    if format not in ("dot", "svg", "png", "images", "all"):
        raise ValueError("UML package diagrams require --format dot, svg, png, images or all; Mermaid cannot express package notation faithfully")
    if renderer not in ("auto", "graphviz"):
        raise ValueError("UML packages require Graphviz; Mermaid does not offer UML package shapes")
    if package_style not in ("modern", "strict"):
        raise ValueError("package style must be modern or strict")
    with load_project(source) as project:
        diagram = analyze_package_diagram(project, scope, max_packages=max_packages)
    dot = to_dot(diagram, direction, style=package_style)
    target = (Path(output).expanduser() if output else
              next_graph_directory(Path.cwd() / "output_graphs"))
    if target.suffix.lower() in (".dot", ".svg", ".png", ".json"):
        if format in ("all", "images"):
            raise ValueError("Use an output directory for --format all or images")
        base = target.with_suffix("")
    else:
        base = target / "uml_packages"
    base.parent.mkdir(parents=True, exist_ok=True)
    dot_path = base.with_suffix(".dot")
    json_path = base.with_suffix(".json")
    dot_path.write_text(dot, encoding="utf-8")
    json_path.write_text(json.dumps({**diagram.to_dict(), "package_style": package_style},
                                   indent=2, ensure_ascii=False)
                         + "\n", encoding="utf-8")
    paths = {"dot": str(dot_path.resolve()), "json": str(json_path.resolve())}
    extensions = (("svg", "png") if format in ("images", "all") else
                  (format,) if format in ("svg", "png") else ())
    for ext in extensions:
        executable = shutil.which("dot")
        if not executable:
            raise RenderError("UML package rendering requires Graphviz dot")
        path = base.with_suffix("." + ext)
        try:
            completed = subprocess.run(
                [executable, "-Gcharset=UTF-8", f"-T{ext}", "-o", str(path)],
                input=dot, text=True, encoding="utf-8", capture_output=True,
                check=False, timeout=90,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RenderError(f"UML package rendering unavailable ({type(exc).__name__})") from exc
        if completed.returncode or not path.is_file() or not path.stat().st_size:
            raise RenderError(f"UML package Graphviz render failed: {completed.stderr[-400:]}")
        paths[ext] = str(path.resolve())
    return {
        "diagram_type": "package", "uml_version": "2.5.1",
        "package_style": package_style,
        "packages": len(diagram.packages), "dependencies": len(diagram.dependencies),
        "renderer": "graphviz" if extensions else None,
        "semantic_provider": "disabled", "warnings": diagram.warnings,
        "files": paths, "mermaid": None,
    }
