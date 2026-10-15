"""Command line entry point."""

import argparse
import json
import os
import sys

from . import __version__
from .render import RenderError
from .service import generate_diagram, inspect_project


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Keep command examples readable and include useful argument defaults."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pyflowmap",
        description="Generate static activity and UML class diagrams without executing code.",
        formatter_class=_HelpFormatter,
        epilog=(
            "Quick start:\n"
            "  pyflowmap inspect ./project\n"
            "  pyflowmap analyze ./project --entry app:main --format mmd\n"
            "  pyflowmap analyze ./project --entry app:main --view hierarchical "
            "--renderer graphviz --format all --output ./diagrams\n\n"
            "For more options:\n"
            "  pyflowmap inspect --help\n"
            "  pyflowmap analyze --help\n\n"
            "JSON and Mermaid sources are always saved. SVG/PNG need Graphviz "
            "or Mermaid CLI.\n"
            "Semantic inference is disabled unless explicitly enabled."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    cmds = parser.add_subparsers(dest="command", required=True)
    discover = cmds.add_parser(
        "inspect",
        help="Discover functions and methods available for analysis",
        description="List entry-point candidates without executing the source project.",
        formatter_class=_HelpFormatter,
        epilog=(
            "Examples:\n"
            "  pyflowmap inspect ./project\n"
            "  pyflowmap inspect ./project --scope src/package"
        ),
    )
    discover.add_argument("source", help="Python file, directory, or ZIP of Python files")
    discover.add_argument("--scope", help="Relative path used to limit entry-point discovery")

    analyze = cmds.add_parser(
        "analyze",
        help="Generate source-linked activity diagrams and related views",
        description="Analyze one Python entry point and export Mermaid, JSON, and optional images.",
        formatter_class=_HelpFormatter,
        epilog=(
            "Examples:\n"
            "  pyflowmap analyze ./project --entry app:main --format mmd\n"
            "  pyflowmap analyze ./project --entry app:main --renderer graphviz "
            "--format images --output ./diagrams\n"
            "  pyflowmap analyze ./project --entry app:main --view hierarchical "
            "--renderer graphviz --format all\n\n"
            "Views: detailed = control flow; overview = possible calls (not UML activity);\n"
            "       hierarchical = navigable summaries linked to detailed activities.\n"
            "A diagram shows possible static paths, not actual runtime outcomes.\n"
            "AI labels require an optional extra and explicit provider selection."
        ),
    )
    analyze.add_argument("source", help="Python file, project directory, or ZIP archive")
    analyze.add_argument(
        "--entry", help="Entry identifier from inspect, e.g. pipeline:Pipeline.run"
    )
    analyze.add_argument("--scope", help="Relative path limiting entry-point discovery")
    analyze.add_argument(
        "--max-nodes", type=int, default=8,
        help="Soft node budget; branches are preserved if simplifying would lose flow"
    )
    analyze.add_argument(
        "--max-depth", type=int, default=2,
        help="Maximum depth of expanded project-local calls"
    )
    analyze.add_argument("--direction", choices=["TD", "LR"], default="TD",
                         help="Diagram direction: top-down or left-to-right")
    analyze.add_argument("--diagram-type", choices=["activity", "class"], default="activity",
                         help="Diagram family: activity flow or static UML class declarations")
    analyze.add_argument("--max-classes", type=int, default=250,
                         help="UML class diagram maximum declarations (does not apply to activity)")
    analyze.add_argument("--language", choices=["en", "es"], default="en",
                         help="Language for deterministic activity labels")
    analyze.add_argument("--renderer", choices=["auto", "mermaid", "graphviz"],
                         default="auto", help="Optional SVG/PNG rendering backend")
    analyze.add_argument("--format", choices=["mmd", "svg", "png", "images", "all"],
                         default="mmd",
                         help="Output: mmd, one image, both images, or all formats")
    analyze.add_argument(
        "--view", choices=["detailed", "overview", "hierarchical"], default="detailed",
        help="Detailed flow, possible-call overview, or navigable hierarchical view"
    )
    analyze.add_argument("--output", help="Destination directory or single-format filename")
    analyze.add_argument(
        "--semantic-provider", choices=["disabled", "mock", "codex"],
        default=os.environ.get("PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER", "disabled"),
        help="Default disabled; opt in to Codex with PYFLOWMAP_DEFAULT_SEMANTIC_PROVIDER"
    )
    analyze.add_argument("--semantic-style", default="neutral",
                         help="Style requested from an optional semantic labeler")
    analyze.add_argument("--semantic-max-chars", type=int, default=70,
                         help="Maximum label length for optional semantic enrichment")
    analyze.add_argument("--semantic-reduction-attempts", type=int, default=1,
                         help="Reduction attempts for optional semantic labels")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_project(args.source, scope=args.scope)
        else:
            result = generate_diagram(args.source, entry=args.entry, scope=args.scope,
                                      max_nodes=args.max_nodes, max_depth=args.max_depth,
                                      direction=args.direction, format=args.format, output=args.output,
                                      diagram_type=args.diagram_type, language=args.language,
                                      renderer=args.renderer,
                                      semantic_provider=args.semantic_provider,
                                      semantic_style=args.semantic_style,
                                      semantic_max_chars=args.semantic_max_chars,
                                      semantic_reduction_attempts=args.semantic_reduction_attempts,
                                      view=args.view, max_classes=args.max_classes)
            result.pop("mermaid")  # Mermaid is in the .mmd file; keep CLI output concise.
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RenderError, RuntimeError) as exc:
        print(f"pyflowmap: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
