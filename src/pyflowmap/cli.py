"""Command line entry point."""

import argparse
import json
import sys

from .render import RenderError
from .service import generate_diagram, inspect_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyflowmap", description="Python source → concise Mermaid workflow")
    cmds = parser.add_subparsers(dest="command", required=True)
    discover = cmds.add_parser("inspect", help="List candidate functions and methods")
    discover.add_argument("source", help="Local directory, .py file or ZIP")
    discover.add_argument("--scope", help="Relative subfolder or file")
    analyze = cmds.add_parser("analyze", help="Generate an activity diagram")
    analyze.add_argument("source", help="Local directory, .py file or ZIP")
    analyze.add_argument("--entry", help="Function/method, e.g. pipeline:Pipeline.run")
    analyze.add_argument("--scope", help="Relative subfolder or file")
    analyze.add_argument("--max-nodes", type=int, default=8)
    analyze.add_argument("--max-depth", type=int, default=2)
    analyze.add_argument("--direction", choices=["TD", "LR"], default="TD")
    analyze.add_argument("--diagram-type", default="activity", help="Diagram type (activity only in V1.1)")
    analyze.add_argument("--language", choices=["en", "es"], default="en")
    analyze.add_argument("--renderer", choices=["auto", "mermaid", "graphviz"], default="auto")
    analyze.add_argument("--format", choices=["mmd", "svg", "png", "all"], default="mmd")
    analyze.add_argument("--output", help="Output directory or diagram filename")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_project(args.source, scope=args.scope)
        else:
            result = generate_diagram(args.source, entry=args.entry, scope=args.scope,
                                      max_nodes=args.max_nodes, max_depth=args.max_depth,
                                      direction=args.direction, format=args.format, output=args.output,
                                      diagram_type=args.diagram_type, language=args.language,
                                      renderer=args.renderer)
            result.pop("mermaid")  # Mermaid is in the .mmd file; keep CLI output concise.
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RenderError) as exc:
        print(f"pyflowmap: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
