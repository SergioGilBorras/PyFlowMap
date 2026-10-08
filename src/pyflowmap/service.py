"""Public application service used identically by CLI and MCP."""

import json
import re
from pathlib import Path

from .diagrams.activity import analyze as analyze_activity
from .mermaid import to_mermaid
from .project import load_project
from .render import render

FORMATS = {"mmd", "svg", "png", "all"}


def inspect_project(source: str, scope: str | None = None) -> dict:
    with load_project(source) as project:
        return {
            "source": str(Path(source).expanduser().resolve()),
            "symbols": [
                {"id": s.id, "kind": "method" if s.owner else "function", "file": s.path, "line": s.node.lineno}
                for s in project.candidates(scope)
            ],
            "warnings": project.warnings,
        }


def generate_diagram(source: str, *, entry: str | None = None, scope: str | None = None,
                     max_nodes: int = 8, max_depth: int = 2, format: str = "mmd",
                     output: str | None = None, direction: str = "TD",
                     diagram_type: str = "activity", language: str = "en",
                     renderer: str = "auto") -> dict:
    if format not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(sorted(FORMATS))}")
    if diagram_type != "activity":
        raise ValueError(f"Unsupported diagram type '{diagram_type}'; supported: activity")
    if renderer not in ("auto", "mermaid", "graphviz"):
        raise ValueError("renderer must be auto, mermaid or graphviz")
    with load_project(source) as project:
        symbol = project.entry(entry, scope)
        graph = analyze_activity(project, symbol, max_nodes=max_nodes, max_depth=max_depth,
                                 language=language)
    mermaid = to_mermaid(graph, direction=direction)
    label = re.sub(r"[^a-zA-Z0-9_-]+", "_", symbol.id).strip("_")[:100] or "flow"
    target = Path(output).expanduser() if output else Path.cwd() / "pyflowmap-output"
    # --output supports an explicit file when there is one output format, or a directory.
    if target.suffix.lower() in (".mmd", ".svg", ".png", ".json"):
        if format == "all":
            raise ValueError("Use an output directory for --format all")
        base = target.with_suffix("")
    else:
        base = target / label
    base.parent.mkdir(parents=True, exist_ok=True)
    mmd_path = base.with_suffix(".mmd")
    json_path = base.with_suffix(".json")
    mmd_path.write_text(mermaid, encoding="utf-8")
    json_path.write_text(json.dumps(graph.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = {"mmd": str(mmd_path.resolve()), "json": str(json_path.resolve())}
    backend = None
    for extension in (("svg", "png") if format == "all" else (format,)):
        if extension != "mmd":
            path, backend = render(mmd_path, base.with_suffix("." + extension), graph,
                                   renderer=renderer, direction=direction)
            paths[extension] = str(path.resolve())
    return {"entry": symbol.id, "diagram_type": diagram_type, "mermaid": mermaid,
            "nodes": sum(n.kind not in ("initial", "final") for n in graph.nodes.values()),
            "renderer": backend, "warnings": graph.warnings, "files": paths}
