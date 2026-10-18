"""Local stdio MCP server with explicit workspace boundary."""

import os
from pathlib import Path

from .output_paths import next_graph_directory
from .service import generate_diagram as _generate_diagram
from .service import inspect_project as _inspect_project


def _allowed(path: str) -> str:
    """Only inspect/write within PYFLOWMAP_ALLOWED_ROOTS (defaults to current working dir)."""
    resolved = Path(path).expanduser().resolve()
    raw = os.environ.get("PYFLOWMAP_ALLOWED_ROOTS")
    roots = [Path(part).expanduser().resolve() for part in raw.split(os.pathsep) if part] if raw else [Path.cwd().resolve()]
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError(f"Path is outside allowed workspace roots: {resolved}")
    return str(resolved)


def inspect_project(project_path: str, scope: str | None = None) -> dict:
    """List available Python functions/methods and their source positions."""
    return _inspect_project(_allowed(project_path), scope)


def generate_diagram(project_path: str, entry_point: str | None = None,
                     scope: str | None = None, max_nodes: int = 8, max_depth: int = 2,
                     format: str = "mmd", output_path: str | None = None,
                     language: str = "en", renderer: str = "auto",
                     diagram_type: str = "activity",
                     semantic_provider: str | None = None, semantic_style: str = "neutral",
                     semantic_max_chars: int = 70,
                     semantic_reduction_attempts: int = 1,
                     view: str = "detailed") -> dict:
    """Generate a simplified activity diagram with optional semantic labels."""
    src = _allowed(project_path)
    default_output = next_graph_directory(Path.cwd() / "output_graphs")
    destination = _allowed(output_path) if output_path else _allowed(str(default_output))
    return _generate_diagram(src, entry=entry_point, scope=scope, max_nodes=max_nodes,
                             max_depth=max_depth, format=format, output=destination,
                             language=language, renderer=renderer, diagram_type=diagram_type,
                             semantic_provider=(semantic_provider or os.environ.get(
                                 "PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER", "disabled")),
                             semantic_style=semantic_style,
                             semantic_max_chars=semantic_max_chars,
                             semantic_reduction_attempts=semantic_reduction_attempts,
                             view=view)


def generate_activity_diagram(project_path: str, entry_point: str | None = None,
                              scope: str | None = None, max_nodes: int = 8,
                              format: str = "mmd", output_path: str | None = None,
                              language: str = "en", renderer: str = "auto",
                              semantic_provider: str | None = None, semantic_style: str = "neutral",
                              semantic_max_chars: int = 70,
                              semantic_reduction_attempts: int = 1,
                              view: str = "detailed") -> dict:
    """MCP shortcut for UML-inspired activity diagrams."""
    return generate_diagram(project_path, entry_point=entry_point, scope=scope,
                            max_nodes=max_nodes, format=format, output_path=output_path,
                            language=language, renderer=renderer,
                            semantic_provider=semantic_provider, semantic_style=semantic_style,
                            semantic_max_chars=semantic_max_chars,
                            semantic_reduction_attempts=semantic_reduction_attempts,
                            view=view)


def make_server():
    try:
        from mcp.server.mcpserver import MCPServer  # MCP Python SDK v2
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as MCPServer  # MCP Python SDK v1
        except ImportError as exc:
            raise RuntimeError("Install MCP support with `pip install 'pyflowmap[mcp]'`") from exc
    mcp = MCPServer("PyFlowMap")
    mcp.tool()(inspect_project)
    mcp.tool()(generate_diagram)
    mcp.tool()(generate_activity_diagram)
    return mcp


def main() -> None:
    make_server().run(transport="stdio")


if __name__ == "__main__":
    main()
