"""Dedicated UML class-diagram exports; never reinterpret FlowGraph nodes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..output_paths import next_graph_directory
from ..project import load_project
from ..render import RenderError
from .classes import analyze_class_diagram, to_dot, to_mermaid


def generate_class_diagram(source: str, *, scope: str | None = None,
                           format: str = "mmd", output: str | None = None,
                           direction: str = "TD", renderer: str = "auto",
                           max_classes: int = 250) -> dict:
    """Static UML: declarations + certain local generalizations only."""
    if format not in ("mmd", "svg", "png", "images", "all"):
        raise ValueError("Unsupported UML class format")
    if renderer not in ("auto", "mermaid", "graphviz"):
        raise ValueError("renderer must be auto, mermaid or graphviz")
    with load_project(source) as project:
        diagram = analyze_class_diagram(project, scope, max_classes=max_classes)
    mmd = to_mermaid(diagram, direction)
    dot = to_dot(diagram, direction)
    target = (Path(output).expanduser() if output else
              next_graph_directory(Path.cwd() / "output_graphs"))
    if target.suffix.lower() in (".mmd", ".svg", ".png", ".json"):
        if format in ("images", "all"):
            raise ValueError("Use an output directory for --format all or images")
        base = target.with_suffix("")
    else:
        base = target / "uml_classes"
    base.parent.mkdir(parents=True, exist_ok=True)
    mmd_path = base.with_suffix(".mmd")
    json_path = base.with_suffix(".json")
    mmd_path.write_text(mmd, encoding="utf-8")
    json_path.write_text(json.dumps(diagram.to_dict(), indent=2, ensure_ascii=False)
                         + "\n", encoding="utf-8")
    paths = {"mmd": str(mmd_path.resolve()), "json": str(json_path.resolve())}
    backend = None
    extensions = (("svg", "png") if format in ("images", "all")
                  else (format,) if format in ("svg", "png") else ())
    for ext in extensions:
        destination = base.with_suffix("." + ext)
        use_mermaid = renderer == "mermaid"
        if use_mermaid:
            executable = shutil.which("mmdc")
            if not executable:
                raise RenderError("UML Mermaid rendering requires mmdc on PATH")
            command = [executable, "-i", str(mmd_path), "-o", str(destination)]
            input_text = None
            backend = "mermaid"
        else:
            executable = shutil.which("dot")
            if not executable:
                raise RenderError("UML Graphviz rendering requires dot on PATH")
            command = [executable, "-Gcharset=UTF-8", f"-T{ext}", "-o", str(destination)]
            input_text = dot
            backend = "graphviz"
        try:
            result = subprocess.run(command, input=input_text, text=True,
                                    capture_output=True, encoding="utf-8",
                                    timeout=90, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RenderError(f"UML rendering unavailable: {type(exc).__name__}") from exc
        if result.returncode or not destination.is_file() or not destination.stat().st_size:
            raise RenderError(f"UML {backend} rendering failed: {result.stderr[-400:]}")
        paths[ext] = str(destination.resolve())
    return {
        "diagram_type": "class", "uml_version": "2.5.1",
        "classes": len(diagram.classes),
        "generalizations": len(diagram.generalizations),
        "dependencies": len(diagram.dependencies),
        "renderer": backend, "semantic_provider": "disabled",
        "warnings": diagram.warnings, "files": paths,
        "mermaid": mmd,
    }
