"""Three independent visual/structural diagram banks, strictly offline.

Never import analyzed Python code or request an external semantic provider.
Create a new output directory; historical results are not modified.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from pyflowmap.output_paths import next_graph_directory
from pyflowmap.service import generate_diagram

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "benchmark" / "diagram-families"
FAMILIES = ("activity", "class", "package")
STYLES = ("modern", "strict")

CSS = """
:root{color-scheme:light;--ink:#152b43;--slate:#536d84;--line:#d8e3ee;--bg:#f3f7fb;--accent:#245f91}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif}
main{max-width:1350px;margin:auto;padding:30px 23px 65px}header{padding:32px 34px;background:#17324e;color:#fff;border-radius:16px}
h1{font-size:clamp(28px,4vw,42px);letter-spacing:-.04em;margin:6px 0 10px}p{margin:5px 0 10px}.muted{color:#a7c5df}
.stat{display:inline-block;border:1px solid #7893aa;border-radius:18px;padding:5px 12px;margin:9px 8px 0 0;font-size:12px}
nav{position:sticky;top:0;z-index:5;background:var(--bg);padding:17px 2px;display:flex;gap:12px;flex-wrap:wrap}
nav a{display:inline-block;padding:8px 15px;border:1px solid #c8d8e7;border-radius:12px;background:#fff;color:var(--ink);font-weight:750;text-decoration:none}
section{scroll-margin-top:82px;padding:20px 0}h2{font-size:24px;letter-spacing:-.025em;margin:0 0 6px}.hint{color:var(--slate);margin-bottom:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(295px,1fr));gap:20px}.card{background:#fff;border:1px solid var(--line);border-radius:15px;overflow:hidden;box-shadow:0 5px 16px #0c30450b}
.card h3{font-size:17px;margin:0}.card-head{padding:16px 18px 14px}.card-head p{font-size:12px;color:var(--slate);margin:5px 0 0}
.figure{background:linear-gradient(#fcfeff,#f1f6fb);min-height:165px;max-height:295px;overflow:auto;display:grid;place-items:center;padding:12px}
.figure a{display:flex;align-items:center;justify-content:center;min-height:145px;max-height:270px;max-width:100%}
.figure img{display:block;max-width:100%;max-height:260px;width:auto;height:auto}.links{padding:12px 18px;border-top:1px solid var(--line);display:flex;gap:12px;flex-wrap:wrap}
.links a{color:var(--accent);font-size:12px;font-weight:760;text-decoration:none}.tag{font-size:11px;font-weight:750;color:#22633e}
.notes{background:white;border:1px solid var(--line);padding:16px 24px;border-radius:13px;margin-top:24px;color:var(--slate);font-size:13px}
@media(max-width:600px){main{padding:12px}.cards{grid-template-columns:1fr}header{padding:24px}}
"""

def load_cases() -> list[dict]:
    data = json.loads((BANK / "cases.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported diagram family manifest schema")
    cases = data["cases"]
    ids = [(case["family"], case["id"]) for case in cases]
    if len(set(ids)) != len(ids) or not all(family in FAMILIES for family, _ in ids):
        raise ValueError("Duplicate or invalid family/case")
    return cases

def validate_activity(model: dict, expected: dict) -> None:
    nodes = model["nodes"]
    assert len(nodes) >= expected["min_nodes"]
    assert len(model["edges"]) >= expected["min_edges"]
    assert all(node["label_source"] == "deterministic" for node in nodes)
    assert any(node["kind"] == "initial" for node in nodes)
    assert any(node["kind"] == "final" for node in nodes)

def validate_classes(model: dict, expected: dict) -> None:
    assert model["diagram_type"] == "class" and model["uml_version"] == "2.5.1"
    assert len(model["classes"]) == expected["class_count"]
    assert {(edge["specific"], edge["general"]) for edge in model["generalizations"]} == {
        tuple(pair) for pair in expected["generalizations"]
    }
    assert {(edge["client"], edge["supplier"]) for edge in model["dependencies"]} == {
        tuple(pair) for pair in expected["dependencies"]
    }
    assert all(edge["location"] for edge in model["generalizations"])
    assert all(edge["evidence"] for edge in model["dependencies"])
    if expected.get("visibility"):
        by_name = {c["name"]: c for c in model["classes"]}
        for name, required in expected["visibility"].items():
            attributes = {a["name"]: a["visibility"] for a in by_name[name]["attributes"]}
            for attribute, symbol in required.items():
                assert attributes.get(attribute) == symbol
    for name in expected.get("abstract", []):
        assert next(c for c in model["classes"] if c["name"] == name)["abstract"]
    if expected.get("external_warning"):
        assert any("superclass" in warning for warning in model["warnings"])

def validate_packages(model: dict, expected: dict) -> None:
    assert model["diagram_type"] == "package" and model["uml_version"] == "2.5.1"
    assert [item["id"] for item in model["packages"]] == expected["packages"]
    assert {(edge["client"], edge["supplier"]) for edge in model["dependencies"]} == {
        tuple(pair) for pair in expected["dependencies"]
    }
    assert all(edge["evidence"] for edge in model["dependencies"])
    assert all(package["location"] for package in model["packages"])

def _files(files: dict, root: Path) -> dict:
    result = {}
    for kind, location in files.items():
        path = Path(location).resolve()
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing {kind} export")
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Export escaped its output directory")
        result[kind] = path.relative_to(root).as_posix()
    return result

def _card(row: dict) -> str:
    outputs = row["outputs"]
    image = escape(outputs["svg"], quote=True)
    links = " ".join(
        f'<a href="{escape(outputs[k], quote=True)}">{k.upper()} ↗</a>'
        for k in ("svg", "png", "json", "mmd", "dot") if k in outputs
    )
    title = escape(row["title"], quote=True)
    return (f'<article class="card"><div class="card-head"><h3>{title}</h3>'
            f'<p>{escape(row["case"])} · <span class="tag">PASS</span></p></div>'
            f'<div class="figure"><a href="{image}" title="Abrir SVG completo">'
            f'<img loading="lazy" src="{image}" alt="{title}"></a></div>'
            f'<div class="links">{links}</div></article>')

def build_index(rows: list[dict]) -> str:
    counts = Counter(row["family"] for row in rows)
    html = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="stylesheet" href="common/gallery.css">'
        '<title>PyFlowMap · Bancos visuales</title></head><body><main>'
        '<header><small>PyFlowMap · Solo AST · Sin inferencia</small>'
        '<h1>Diagramas verificables para las tres familias.</h1>'
        '<p class="muted">Casos independientes con oráculos estructurales.'
        ' No se ejecuta el proyecto analizado ni se utiliza Codex.</p>'
        f'<span class="stat">Actividad · {counts["activity"]}</span>'
        f'<span class="stat">Clases · {counts["class"]}</span>'
        f'<span class="stat">Paquetes · {counts["package"]}, dos estilos</span>'
        '<span class="stat">SVG · PNG · JSON · archivos editables</span></header>'
        '<nav aria-label="Navegación por familias"><a href="#activity">01 · Actividad</a>'
        '<a href="#class">02 · Clases</a><a href="#package">03 · Paquetes</a></nav>'
    )
    for family, title, description in (
        ("activity", "Actividad", "Decisiones, bucles, excepciones, generadores y llamadas."),
        ("class", "Clases UML", "Herencia, dependencias explícitas, visibilidad y clases aisladas."),
        ("package", "Paquetes UML", "Imports estáticos, ciclos, subpaquetes y estilos modern/strict."),
    ):
        items = "".join(_card(row) for row in rows if row["family"] == family)
        html += (f'<section id="{family}"><h2>{title}</h2><p class="hint">'
                 f'{description}</p><div class="cards">{items}</div></section>')
    return html + (
        '<div class="notes">Las relaciones UML se verifican con oráculos independientes.'
        ' Las clases o paquetes aislados se conservan: no inventamos conexiones.'
        ' Modern es un estilo visual alternativo; strict conserva la notación'
        ' tradicional de paquete. El banco original de 81 actividades sigue separado.'
        '</div></main></body></html>\n'
    )

def run_bank(output_parent: Path) -> dict:
    root = next_graph_directory(output_parent.expanduser().resolve())
    root.mkdir(parents=True, exist_ok=False)
    cases = load_cases()
    rows = []
    for case in cases:
        family, identifier = case["family"], case["id"]
        source = (BANK / case["source"]).resolve()
        if not source.is_relative_to((BANK / "fixtures").resolve()) or not source.is_dir():
            raise ValueError("Missing or unsafe fixture path")
        comparisons = []
        styles = STYLES if family == "package" else (None,)
        for style in styles:
            start = time.monotonic()
            opts = dict(source=str(source), diagram_type=family,
                        renderer="graphviz", format="all", semantic_provider="disabled",
                        output=str(root / family / identifier / (style or "diagram")))
            if family == "activity":
                opts.update(entry=case["entry"], max_nodes=30, max_depth=3)
            elif family == "package":
                opts.update(direction="LR", package_style=style)
            answer = generate_diagram(**opts)
            files = _files(answer["files"], root)
            model = json.loads((root / files["json"]).read_text(encoding="utf-8"))
            if family == "activity":
                validate_activity(model, case["expect"])
            elif family == "class":
                validate_classes(model, case["expect"])
            else:
                validate_packages(model, case["expect"])
                assert model["package_style"] == style
                comparisons.append({k: v for k, v in model.items() if k != "package_style"})
                dot = (root / files["dot"]).read_text(encoding="utf-8")
                assert ("shape=folder" in dot) if style == "modern" else ('SIDES="LTR"' in dot)
            rows.append({"family": family, "case": identifier, "style": style,
                         "title": case["title"] + (f" · {style}" if style else ""),
                         "status": "PASS", "outputs": files,
                         "elapsed_seconds": round(time.monotonic() - start, 2)})
        if family == "package":
            assert comparisons[0] == comparisons[1], f"Package models differ: {identifier}"
        print(f"{family}/{identifier}: PASS", flush=True)
    counts = Counter(row["family"] for row in rows)
    report = {
        "status": "PASS", "inference": "disabled", "source_execution": False,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": len(cases), "rendered": len(rows),
        "by_family": dict(counts), "rows": rows,
    }
    common = root / "common"
    common.mkdir()
    (common / "gallery.css").write_text(CSS, encoding="utf-8")
    (common / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / "index.html").write_text(build_index(rows), encoding="utf-8")
    (root / "README.md").write_text(
        "# Bancos UML y de actividad, sin inferencia\n\n"
        "Abre index.html para revisar los tres bancos de imágenes.\n"
        "activity/, class/, package/ y common/ contienen salidas independientes.\n"
        "Paquetes tiene estilos modern y strict con datos UML idénticos.\n"
        "Ninguna ejecución borra resultados anteriores.\n", encoding="utf-8"
    )
    return {"status": "PASS", "cases": len(cases),
            "renders": len(rows), "output": str(root), "inference": "disabled"}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Three independent offline diagram banks")
    parser.add_argument("--output-parent", type=Path, default=ROOT / "output_graphs")
    args = parser.parse_args(argv)
    print(json.dumps(run_bank(args.output_parent), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
