"""Public application service used identically by CLI and MCP."""

import ast
import json
import re
from html import escape
from pathlib import Path

from .diagrams.activity import analyze as analyze_activity
from .hierarchy import build_hierarchical_outline
from .mermaid import to_mermaid
from .output_paths import next_graph_directory
from .overview import function_overview
from .project import load_project
from .render import render
from .semantic import SemanticLabelProvider, enrich_activity_labels

FORMATS = {"mmd", "svg", "png", "images", "all", "dot"}


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
                     renderer: str = "auto",
                     label_provider: SemanticLabelProvider | None = None,
                     semantic_provider: str = "disabled", semantic_style: str = "neutral",
                     semantic_max_chars: int = 70,
                     semantic_reduction_attempts: int = 1,
                     view: str = "detailed", max_classes: int = 250,
                     max_packages: int = 250) -> dict:
    if format not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(sorted(FORMATS))}")
    if diagram_type not in ("activity", "class", "package"):
        raise ValueError(f"Unsupported diagram type '{diagram_type}'; supported: activity, class, package")
    if format == "dot" and diagram_type != "package":
        raise ValueError("--format dot is only available for UML package diagrams")
    if renderer not in ("auto", "mermaid", "graphviz"):
        raise ValueError("renderer must be auto, mermaid or graphviz")
    if view not in ("detailed", "overview", "hierarchical"):
        raise ValueError("view must be detailed, overview or hierarchical")
    if semantic_provider not in ("disabled", "mock", "codex"):
        raise ValueError("semantic_provider must be disabled, mock or codex")
    if label_provider is not None and semantic_provider != "disabled":
        raise ValueError("Use either an injected label_provider or semantic_provider, not both")
    if diagram_type == "package":
        if entry is not None:
            raise ValueError("Package diagrams describe a project/scope; omit --entry")
        if view != "detailed":
            raise ValueError("Package diagrams do not support activity --view options")
        if semantic_provider != "disabled" or label_provider is not None:
            raise ValueError("Package diagrams are deterministic; disable semantic labeling")
        from .uml.package_export import generate_package_diagram

        return generate_package_diagram(
            source, scope=scope, format=format, output=output,
            direction=direction, renderer=renderer, max_packages=max_packages,
        )
    if diagram_type == "class":
        if entry is not None:
            raise ValueError("Class diagrams describe a project/scope; omit --entry")
        if view != "detailed":
            raise ValueError("Class diagrams do not support activity --view options")
        if semantic_provider != "disabled" or label_provider is not None:
            raise ValueError("Class diagrams are deterministic; disable semantic labeling")
        from .uml.export import generate_class_diagram

        return generate_class_diagram(
            source, scope=scope, format=format, output=output,
            direction=direction, renderer=renderer, max_classes=max_classes,
        )
    # Lazy-loading the optional package guarantees ordinary analysis is offline.
    if semantic_provider != "disabled":
        from .semantic.p4_provider import P4SemanticLabelProvider

        label_provider = P4SemanticLabelProvider(
            provider=semantic_provider, max_chars=semantic_max_chars,
            style=semantic_style, reduction_attempts=semantic_reduction_attempts)
    with load_project(source) as project:
        symbol = project.entry(entry, scope)
        graph = analyze_activity(project, symbol, max_nodes=max_nodes, max_depth=max_depth,
                                 language=language)
        subdiagrams = []
        seen_subdiagrams = set()
        hierarchy_parent = None
        hierarchy_symbol = symbol
        if view == "hierarchical":
            candidates = []
            for node in graph.nodes.values():
                target = project.symbols.get(node.label_metadata.get("resolved_target", ""))
                calls = node.label_metadata.get("subprocess_calls", [])
                if target is not None and len(calls) >= 2:
                    top_level_decisions = sum(isinstance(stmt, ast.If)
                                              for stmt in target.node.body)
                    candidates.append((top_level_decisions, len(calls), node, target))
            if candidates:
                _, _, hierarchy_parent, hierarchy_symbol = max(
                    candidates, key=lambda item: (item[0], item[1], item[3].id))
        for parent in graph.nodes.values() if view in ("detailed", "hierarchical") else []:
            if view == "hierarchical" and parent is not hierarchy_parent:
                continue
            contained_calls = parent.label_metadata.get("subprocess_calls", [])
            target_id = parent.label_metadata.get("resolved_target")
            # A bounded subprocess with several statically observed calls gets
            # its own activity view. Its branch structure stays inside that
            # child diagram, so sibling calls are never presented as a sequence.
            if (view == "hierarchical" and target_id and len(contained_calls) >= 2
                    and target_id in project.symbols):
                target = project.symbols[target_id]
                slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", target_id).strip("_")[-70:]
                source_location = parent.locations[0] if parent.locations else ""
                detail_key = ("subprocess-detail", target_id)
                if detail_key not in seen_subdiagrams:
                    seen_subdiagrams.add(detail_key)
                    detail_id = f"{slug}-full-detail"
                    child = analyze_activity(project, target, max_nodes=35, max_depth=0,
                                             language=language)
                    subdiagrams.append({
                        "id": detail_id,
                        "call_expression": parent.label_metadata.get("call_expression", target_id),
                        "source_location": source_location,
                        "target_symbol": target_id,
                        "kind": "full-detail activity",
                        "graph": child,
                    })
            for call in parent.label_metadata.get("subprocess_calls", []):
                targets = call.get("targets", [])
                if call.get("resolution") != "possible" or len(targets) != 1:
                    continue
                target_id = targets[0]
                target = project.symbols.get(target_id)
                if target is None:
                    continue
                key = (call.get("location"), target_id)
                if key in seen_subdiagrams:
                    continue
                seen_subdiagrams.add(key)
                source_location = call.get("location", "source:0")
                line = source_location.rsplit(":", 1)[-1]
                slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", target_id).strip("_")[-70:]
                subdiagram_id = f"{slug}-line-{line}"
                child = analyze_activity(project, target, max_nodes=35, max_depth=0,
                                         language=language)
                call["subdiagram_id"] = subdiagram_id
                subdiagrams.append({
                    "id": subdiagram_id,
                    "call_expression": call.get("expression"),
                    "source_location": source_location,
                    "target_symbol": target_id,
                    "kind": "possible call target",
                    "graph": child,
                })
        if view == "hierarchical" and not subdiagrams:
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", hierarchy_symbol.id).strip("_")[-70:]
            detail_id = f"{slug}-full-detail"
            subdiagrams.append({
                "id": detail_id,
                "call_expression": hierarchy_symbol.name,
                "source_location": f"{hierarchy_symbol.path}:{hierarchy_symbol.node.lineno}",
                "target_symbol": hierarchy_symbol.id,
                "kind": "full-detail activity",
                "graph": analyze_activity(project, hierarchy_symbol, max_nodes=35,
                                          max_depth=0, language=language),
            })
        if view == "hierarchical":
            detailed_warnings = list(graph.warnings)
            graph = build_hierarchical_outline(hierarchy_symbol, language)
            graph.warnings = list(dict.fromkeys([*detailed_warnings, *graph.warnings]))
            graph.nodes[next(node.id for node in graph.nodes.values()
                             if node.kind == "final")].label_metadata.update({
                "hierarchy_root_symbol": hierarchy_symbol.id,
                "source_entry_symbol": symbol.id,
            })
        if label_provider is not None:
            enrich_activity_labels(graph, project, label_provider, language,
                                   strict=semantic_provider != "disabled")
    if view == "overview":
        graph = function_overview(graph)
    label = re.sub(r"[^a-zA-Z0-9_-]+", "_", symbol.id).strip("_")[:100] or "flow"
    target = (Path(output).expanduser() if output else
              next_graph_directory(Path.cwd() / "output_graphs"))
    # --output supports an explicit file when there is one output format, or a directory.
    if target.suffix.lower() in (".mmd", ".svg", ".png", ".json"):
        if format in ("all", "images"):
            raise ValueError("Use an output directory for --format all or images")
        base = target.with_suffix("")
    else:
        base = target / label
    base.parent.mkdir(parents=True, exist_ok=True)
    subdiagram_root = base.parent / f"{base.name}.subdiagrams"
    index_ref = f"{subdiagram_root.name}/index.html"
    if subdiagrams:
        for parent in graph.nodes.values():
            if (parent.label_metadata.get("subdiagram_id")
                    or any(call.get("subdiagram_id") for call in
                           parent.label_metadata.get("subprocess_calls", []))):
                parent.label_metadata["subdiagram_index"] = index_ref
        if view == "hierarchical":
            for node in graph.nodes.values():
                if node.kind == "final":
                    node.label_metadata["subdiagram_index"] = index_ref
    mermaid = to_mermaid(graph, direction=direction)
    mmd_path = base.with_suffix(".mmd")
    json_path = base.with_suffix(".json")
    mmd_path.write_text(mermaid, encoding="utf-8")
    json_path.write_text(json.dumps(graph.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = {"mmd": str(mmd_path.resolve()), "json": str(json_path.resolve())}
    backend = None
    for extension in (("svg", "png") if format in ("all", "images") else (format,)):
        if extension != "mmd":
            path, backend = render(mmd_path, base.with_suffix("." + extension), graph,
                                   renderer=renderer, direction=direction)
            paths[extension] = str(path.resolve())
    subdiagram_results = []
    if subdiagrams:
        subdiagram_root.mkdir(parents=True, exist_ok=True)
        index_rows = []
        for item in subdiagrams:
            child_base = subdiagram_root / item["id"]
            child_graph = item.pop("graph")
            child_mermaid = to_mermaid(child_graph, direction=direction)
            child_mmd = child_base.with_suffix(".mmd")
            child_json = child_base.with_suffix(".json")
            child_mmd.write_text(child_mermaid, encoding="utf-8")
            child_json.write_text(
                json.dumps(child_graph.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            child_files = {"mmd": str(child_mmd.resolve()), "json": str(child_json.resolve())}
            for extension in (("svg", "png") if format in ("all", "images") else (format,)):
                if extension == "mmd":
                    continue
                image_path, _ = render(child_mmd, child_base.with_suffix("." + extension),
                                       child_graph, renderer=renderer, direction=direction)
                child_files[extension] = str(image_path.resolve())
            subdiagram_results.append({key: value for key, value in item.items()})
            subdiagram_results[-1]["files"] = child_files
            available_images = ("svg", "png") if format in ("all", "images") else (
                (format,) if format in ("svg", "png") else ())
            links = []
            for extension in available_images:
                href = escape(f"{item['id']}.{extension}")
                links.append(f'<a href="{href}">{extension.upper()}</a>')
            for extension, title in (("json", "JSON"), ("mmd", "Mermaid")):
                href = escape(f"{item['id']}.{extension}")
                links.append(f'<a href="{href}">{title}</a>')
            index_rows.append(
                f"<li><strong>{escape(str(item.get('kind', 'subprocess')))}: "
                f"{escape(str(item.get('call_expression', 'call')))}</strong> at "
                f"<code>{escape(str(item.get('source_location', '')))}</code> targets "
                f"<code>{escape(str(item.get('target_symbol', '')))}</code> ? "
                f"{' ? '.join(links)}</li>"
            )
        parent_extension = ("svg" if format in ("all", "images", "svg") else
                            "png" if format == "png" else "mmd")
        parent_link = f"../{base.name}.{parent_extension}"
        index = ("<!doctype html><meta charset=\"utf-8\"><title>Activity subdiagrams</title>"
                 f"<h1>Activity subdiagrams</h1><p><a href=\"{parent_link}\">Return to main activity</a></p>"
                 "<p>Each diagram shows one possible target "
                 "independently. Their ordering does not imply execution order.</p><ul>" +
                 "\n".join(index_rows) + "</ul>\n")
        (subdiagram_root / "index.html").write_text(index, encoding="utf-8")
    result_type = ("process-summary" if view == "overview" else
                   "activity-hierarchy" if view == "hierarchical" else diagram_type)
    return {"entry": symbol.id, "hierarchy_root_symbol": (
                hierarchy_symbol.id if view == "hierarchical" else None),
            "diagram_type": result_type, "mermaid": mermaid,
            "nodes": sum(n.kind not in ("initial", "final") for n in graph.nodes.values()),
            "renderer": backend, "semantic_provider": semantic_provider,
            "warnings": graph.warnings, "files": paths, "subdiagrams": subdiagram_results}
