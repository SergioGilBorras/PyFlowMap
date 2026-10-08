"""Public application service used identically by CLI and MCP."""

import json
import re
from pathlib import Path

from .analysis import FlowBuilder, simplify
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
                     output: str | None = None, direction: str = "TD") -> dict:
    if format not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(sorted(FORMATS))}")
    with load_project(source) as project:
        symbol = project.entry(entry, scope)
        graph = simplify(FlowBuilder(project, max_depth=max_depth).build(symbol), max_nodes=max_nodes)
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
    for extension in (("svg", "png") if format == "all" else (format,)):
        if extension != "mmd":
            path = render(mmd_path, base.with_suffix("." + extension))
            paths[extension] = str(path.resolve())
    return {"entry": symbol.id, "mermaid": mermaid, "nodes": len(graph.nodes),
            "warnings": graph.warnings, "files": paths}
