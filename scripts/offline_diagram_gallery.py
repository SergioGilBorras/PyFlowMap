"""Produce three separate diagram families with no LLM, execution or cleanup."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from pyflowmap.output_paths import next_graph_directory
from pyflowmap.service import generate_diagram

ROOT = Path(__file__).resolve().parents[1]
DEMO_SOURCE = ROOT / "examples" / "uml_showcase"
DEMO_ENTRY = "reports.dashboard:main"

STYLE = """
:root{color-scheme:light;--ink:#17283e;--muted:#53697e;--line:#d9e3ee;--bg:#f2f6fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Arial,sans-serif}
main{max-width:1200px;margin:auto;padding:45px 25px 85px}
header{padding-bottom:25px;border-bottom:1px solid var(--line)}
.eyebrow{letter-spacing:.14em;color:#294c72;font-size:12px;font-weight:800;text-transform:uppercase}
h1{font-size:clamp(27px,4vw,42px);line-height:1.2;letter-spacing:-.03em;margin:8px 0}
.intro,.note{color:var(--muted);max-width:850px}.intro{margin-bottom:20px}
.pill{display:inline-block;border:1px solid #cbd8e6;border-radius:24px;background:white;padding:6px 12px;font-size:12px;font-weight:700;margin-right:8px}
article{margin:25px 0;background:white;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 10px 26px #1e35480a}
section{padding:20px 24px 10px;display:flex;gap:15px;flex-wrap:wrap;justify-content:space-between;align-items:center}
h2{font-size:20px;margin:0}.num{color:#7890a5;padding-right:12px;font-size:12px}
.type{font-size:11px;color:#345879;background:#eaf1f8;border-radius:16px;padding:6px 12px;font-weight:700}
figure{margin:0 16px;padding:15px 0 25px;display:flex;justify-content:center;align-items:center;min-height:220px}
figure img{display:block;max-width:100%;max-height:720px;width:auto;height:auto}
nav{display:flex;gap:18px;padding:15px 24px;border-top:1px solid var(--line);flex-wrap:wrap}
a{color:#22547f;text-decoration:none;font-weight:650;font-size:13px}a:hover{text-decoration:underline}
.note{font-size:13px}@media(max-width:600px){main{padding:20px 12px}section{padding:15px}nav{padding:15px}}
"""


def generate_gallery(source: str, entry: str, output_parent: str) -> dict:
    """Create a NEW date-stamped directory; never touch existing results."""
    root = next_graph_directory(Path(output_parent).expanduser().resolve())
    root.mkdir(parents=True, exist_ok=False)
    items = []
    for diagram_type, folder in (("activity", "activity"), ("class", "classes"),
                                 ("package", "packages")):
        kwargs = {
            "diagram_type": diagram_type, "format": "all",
            "renderer": "graphviz", "semantic_provider": "disabled",
            "output": str(root / folder),
        }
        if diagram_type == "activity":
            kwargs.update(entry=entry, max_nodes=28, max_depth=2)
        if kind == "package":
            kwargs["direction"] = "LR"
        result = generate_diagram(source, **kwargs)
        paths = {}
        for kind, location in result["files"].items():
            file = Path(location).resolve()
            if not file.is_file() or not file.is_relative_to(root.resolve()):
                raise ValueError("Unexpected gallery file outside its destination")
            paths[kind] = file.relative_to(root).as_posix()
        items.append({
            "type": diagram_type, "folder": folder, "files": paths,
            "warnings": result.get("warnings", []),
        })
    common = root / "common"
    common.mkdir()
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    manifest = {
        "version": 1, "generated_utc": generated, "inference": "none",
        "semantic_provider": "disabled", "diagrams": items,
    }
    (common / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (common / "gallery.css").write_text(STYLE, encoding="utf-8")
    names = [
        ("01", "Diagrama de actividad", "Flujo de control · análisis estático"),
        ("02", "Diagrama de clases", "UML 2.5.1 · declaraciones"),
        ("03", "Diagrama de paquetes", "UML 2.5.1 · dependencias"),
    ]
    cards = []
    for (number, title, info), item in zip(names, items, strict=True):
        image = escape(item["files"]["svg"], quote=True)
        downloads = " ".join(
            f'<a href="{escape(uri, quote=True)}">{escape(fmt.upper())} ↗</a>'
            for fmt, uri in item["files"].items()
            if fmt in ("svg", "png", "json", "mmd", "dot")
        )
        cards.append(
            f'<article><section><h2><span class="num">{number}</span>{title}</h2>'
            f'<span class="type">{info}</span></section>'
            f'<figure><img src="{image}" alt="{title}" loading="lazy"></figure>'
            f'<nav>{downloads}</nav></article>')
    page = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        '<link rel="stylesheet" href="common/gallery.css">'
        '<title>PyFlowMap · Galería UML</title></head><body><main>'
        '<header><span class="eyebrow">PyFlowMap · Galería offline</span>'
        '<h1>Tres perspectivas del mismo código.</h1>'
        '<p class="intro">Análisis estático de Python, sin ejecutar el proyecto ni '
        'emplear inferencia semántica. Relaciones UML solo con evidencia verificable.</p>'
        '<span class="pill">Sin Codex</span><span class="pill">3 diagramas</span>'
        '</header>' + "\n".join(cards) +
        '<p class="note">El diagrama de actividad representa rutas posibles, no una '
        'ejecución observada. Clases y paquetes representan subconjuntos de UML 2.5.1. '
        'Consulta los JSON para metadatos y advertencias.</p></main></body></html>\n'
    )
    (root / "index.html").write_text(page, encoding="utf-8")
    (root / "README.md").write_text(
        "# Galería PyFlowMap offline\n\n"
        "Un diagrama por carpeta: activity/, classes/, packages/.\n"
        "common/ almacena CSS y manifest.json. Abre index.html sin conexión.\n"
        "No se elimina ningún resultado anterior. Todo se genera con proveedor disabled.\n",
        encoding="utf-8")
    return {
        "status": "PASS", "semantic_provider": "disabled", "offline": True,
        "output": str(root), "types": [item["type"] for item in items],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Three offline diagram families in separate folders")
    parser.add_argument("--source", default=str(DEMO_SOURCE))
    parser.add_argument("--entry", help="Required for any custom --source")
    parser.add_argument("--output-parent", default=str(ROOT / "output_graphs"))
    args = parser.parse_args(argv)
    if args.entry is None and Path(args.source).resolve() != DEMO_SOURCE.resolve():
        parser.error("Provide --entry for a custom --source")
    result = generate_gallery(args.source, args.entry or DEMO_ENTRY, args.output_parent)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
